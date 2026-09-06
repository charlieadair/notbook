from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import Settings
from app.inference.base import InferenceAdapter
from app.services.bounded import BoundedTimeoutError, run_with_timeout

# ~500–800 token-ish windows (≈4 chars/token) with overlap.
CHUNK_CHARS = 2400
CHUNK_OVERLAP = 400

# Whole-doc concatenation for PDFs. Markers are visible to the LLM so it can
# respect page structure; we map each grounded span back to a page via offsets.
PAGE_MARKER_FMT = "--- page {n} ---"
PAGE_MARKER_RE = re.compile(r"\n*--- page \d+ ---\n*")
_WS_RE = re.compile(r"\s+")

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You slice study source text into coherent retrieval units. "
    "Return JSON only. Do not invent facts, paraphrase, or summarize."
)


def chunk_text(
    text: str,
    *,
    page: int | None = None,
    region: str | None = None,
    order_start: int = 0,
    char_offset: int = 0,
) -> list[tuple[str, dict[str, Any]]]:
    """Split text into overlapping windows. Locator always includes order."""
    text = text.replace("\r\n", "\n")
    if not text.strip():
        return []

    chunks: list[tuple[str, dict[str, Any]]] = []
    start = 0
    n = len(text)
    order = order_start

    while start < n:
        end = min(start + CHUNK_CHARS, n)
        if end < n:
            window = text[start:end]
            break_at = window.rfind("\n\n")
            if break_at < CHUNK_CHARS // 3:
                break_at = window.rfind("\n")
            if break_at < CHUNK_CHARS // 3:
                break_at = window.rfind(" ")
            if break_at >= CHUNK_CHARS // 3:
                end = start + break_at

        piece = text[start:end].strip()
        if piece:
            locator: dict[str, Any] = {
                "char_start": char_offset + start,
                "char_end": char_offset + end,
                "order": order,
            }
            if page is not None:
                locator["page"] = page
            if region is not None:
                locator["region"] = region
            chunks.append((piece, locator))
            order += 1

        if end >= n:
            break
        nxt = end - CHUNK_OVERLAP
        start = nxt if nxt > start else end

    return chunks


def heuristic_chunk_document(
    *,
    text: str | None = None,
    pages: list[tuple[int, str]] | None = None,
    region: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Existing per-page / windowed fallback. PDF stays page-local for locators."""
    if pages is not None:
        pieces: list[tuple[str, dict[str, Any]]] = []
        order = 0
        for page_no, page_text in pages:
            page_chunks = chunk_text(page_text, page=page_no, order_start=order)
            pieces.extend(page_chunks)
            order += len(page_chunks)
        return pieces
    return chunk_text(text or "", region=region, order_start=0)


def join_pdf_pages(pages: list[tuple[int, str]]) -> tuple[str, list[tuple[int, int, int]]]:
    """Concatenate page texts with markers. Spans are (page, content_start, content_end)."""
    parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for index, (page_no, page_text) in enumerate(pages):
        marker = PAGE_MARKER_FMT.format(n=page_no)
        prefix = f"{marker}\n\n" if index == 0 else f"\n\n{marker}\n\n"
        parts.append(prefix)
        cursor += len(prefix)
        start = cursor
        parts.append(page_text)
        cursor += len(page_text)
        spans.append((page_no, start, cursor))
    return "".join(parts), spans


def page_for_offset(spans: list[tuple[int, int, int]], offset: int) -> int | None:
    """Best-effort page from a char offset into the marked whole-doc string."""
    if not spans:
        return None
    for page_no, start, end in spans:
        if start <= offset < end:
            return page_no
    for page_no, start, _end in spans:
        if offset < start:
            return page_no
    return spans[-1][0]


def split_budget_segments(text: str, max_chars: int) -> list[tuple[int, str]]:
    """Sequential non-overlapping segments of the whole doc. No invented overlap."""
    text = text.replace("\r\n", "\n")
    if max_chars <= 0:
        return [(0, text)] if text.strip() else []
    if len(text) <= max_chars:
        return [(0, text)] if text.strip() else []

    segments: list[tuple[int, str]] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = text[start:end]
            break_at = window.rfind("\n\n")
            if break_at < max_chars // 3:
                break_at = window.rfind("\n")
            if break_at < max_chars // 3:
                break_at = window.rfind(" ")
            if break_at >= max_chars // 3:
                end = start + break_at
        piece = text[start:end]
        if piece.strip():
            segments.append((start, piece))
        start = end if end > start else start + max_chars
    return segments


def parse_llm_slices(raw: str) -> list[dict[str, Any]]:
    """Parse a JSON list of {text, char_start?, char_end?} from a model completion."""
    payload = _load_json_payload(raw)
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in ("slices", "chunks", "units"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
        if rows is None:
            raise ValueError("JSON object has no slices list")
    else:
        raise ValueError("JSON is not a slice list or object")

    slices: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        slice_row: dict[str, Any] = {"text": text}
        if "char_start" in item:
            slice_row["char_start"] = item["char_start"]
        if "char_end" in item:
            slice_row["char_end"] = item["char_end"]
        slices.append(slice_row)
    if not slices:
        raise ValueError("no usable slices in model JSON")
    return slices


def ground_slice(
    source: str,
    slice_text: str,
    *,
    char_start: Any = None,
    char_end: Any = None,
    search_from: int = 0,
) -> tuple[str, int, int] | None:
    """Return (source substring, start, end) if the slice is tightly grounded."""
    raw = (slice_text or "").strip()
    if not raw:
        return None
    source = source.replace("\r\n", "\n")

    hinted = _hinted_span(source, raw, char_start, char_end)
    if hinted is not None:
        start, end = hinted
        return _canonical_slice(source, start, end)

    idx = source.find(raw, search_from)
    if idx < 0 and search_from:
        idx = source.find(raw)
    if idx >= 0:
        return _canonical_slice(source, idx, idx + len(raw))

    stripped = raw.strip()
    idx = source.find(stripped, search_from)
    if idx < 0 and search_from:
        idx = source.find(stripped)
    if idx >= 0:
        return _canonical_slice(source, idx, idx + len(stripped))

    return _normalized_span(source, raw, search_from)


def llm_chunk_document(
    inference: InferenceAdapter,
    settings: Settings,
    *,
    text: str | None = None,
    pages: list[tuple[int, str]] | None = None,
    region: str | None = None,
) -> list[tuple[str, dict[str, Any]]] | None:
    """Ask the adapter to slice the whole document. None means caller should fall back."""
    page_spans: list[tuple[int, int, int]] | None = None
    if pages is not None:
        source, page_spans = join_pdf_pages(pages)
    else:
        source = (text or "").replace("\r\n", "\n")
    if not source.strip():
        return None

    max_chars = settings.llm_chunk_max_chars
    max_slices = settings.llm_chunk_max_slices
    segments = split_budget_segments(source, max_chars)
    if not segments:
        return None

    pieces: list[tuple[str, dict[str, Any]]] = []
    search_from = 0
    for _offset, segment in segments:
        if len(pieces) >= max_slices:
            break
        raw_slices = _complete_slices(inference, segment, settings)
        if raw_slices is None:
            return None
        grounded = _ground_raw_slices(
            source,
            raw_slices,
            page_spans=page_spans,
            region=region,
            order_start=len(pieces),
            search_from=search_from,
            remaining=max_slices - len(pieces),
        )
        if not grounded:
            return None
        pieces.extend(grounded)
        search_from = grounded[-1][1].get("char_end") or search_from
    return pieces or None


def chunk_extracted_document(
    inference: InferenceAdapter,
    settings: Settings,
    *,
    text: str | None = None,
    pages: list[tuple[int, str]] | None = None,
    region: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Prefer LLM slices when configured; hard-fallback to heuristic windows."""
    if settings.uses_llm_chunking(inference.name):
        pieces = llm_chunk_document(
            inference,
            settings,
            text=text,
            pages=pages,
            region=region,
        )
        if pieces:
            logger.info("LLM semantic chunking produced %s slices", len(pieces))
            return pieces
        logger.warning("LLM chunking failed, empty, or ungrounded; falling back to heuristic windows")
    elif (inference.name or "").strip().lower() == "stub":
        logger.info("Stub inference adapter; using heuristic chunk windows")
    return heuristic_chunk_document(text=text, pages=pages, region=region)


def _user_prompt(source: str, max_slices: int) -> str:
    return (
        "Slice the following source into ordered study units.\n\n"
        "Return a JSON object:\n"
        '{"slices": [{"text": "<verbatim excerpt>", "char_start": 0, "char_end": 10}]}\n\n'
        "Rules:\n"
        "- Cover the source in reading order without adding facts.\n"
        "- Each slice is one coherent section or idea, typically a few hundred "
        "to about 2000 characters.\n"
        "- Copy text from the source. Do not paraphrase, summarize, or invent.\n"
        "- Optional char_start / char_end are 0-based offsets into this source "
        "(end exclusive).\n"
        f"- Return at most {max_slices} slices.\n"
        '- Page markers look like "--- page N ---". Do not include them as facts; '
        "you may split at those markers.\n\n"
        "SOURCE:\n"
        f"{source}"
    )


def _complete_slices(
    inference: InferenceAdapter,
    source: str,
    settings: Settings,
) -> list[dict[str, Any]] | None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(source, settings.llm_chunk_max_slices)},
    ]
    timeout = settings.llm_chunk_timeout_seconds
    try:
        raw = run_with_timeout(
            inference.complete,
            messages,
            timeout=timeout,
            temperature=0,
        )
    except BoundedTimeoutError:
        logger.warning("LLM chunking timed out after %.1fs", timeout)
        return None
    except Exception:
        logger.exception("LLM chunking complete() failed")
        return None
    if raw is None or not str(raw).strip():
        logger.warning("LLM chunking returned an empty completion")
        return None
    try:
        return parse_llm_slices(str(raw))
    except Exception as exc:
        logger.warning("LLM chunking JSON parse failed: %s", exc)
        return None


def _ground_raw_slices(
    source: str,
    raw_slices: list[dict[str, Any]],
    *,
    page_spans: list[tuple[int, int, int]] | None,
    region: str | None,
    order_start: int,
    search_from: int,
    remaining: int,
) -> list[tuple[str, dict[str, Any]]]:
    pieces: list[tuple[str, dict[str, Any]]] = []
    dropped = 0
    cursor = search_from
    for item in raw_slices:
        if len(pieces) >= remaining:
            break
        grounded = ground_slice(
            source,
            item.get("text", ""),
            char_start=item.get("char_start"),
            char_end=item.get("char_end"),
            search_from=cursor,
        )
        if grounded is None:
            dropped += 1
            continue
        text, start, end = grounded
        text = _strip_page_markers(text)
        if not text:
            dropped += 1
            continue
        locator: dict[str, Any] = {
            "char_start": start,
            "char_end": end,
            "order": order_start + len(pieces),
        }
        if page_spans is not None:
            page = page_for_offset(page_spans, start)
            if page is not None:
                locator["page"] = page
        if region is not None:
            locator["region"] = region
        pieces.append((text, locator))
        cursor = end
    if dropped:
        logger.info("Dropped %s invented or ungrounded LLM slices", dropped)
    return pieces


def _canonical_slice(source: str, start: int, end: int) -> tuple[str, int, int] | None:
    if start < 0 or end > len(source) or start >= end:
        return None
    piece = source[start:end].strip()
    if not piece:
        return None
    # Re-trim so locator points at the stored text, not surrounding whitespace.
    window = source[start:end]
    rel = window.find(piece)
    if rel < 0:
        return None
    start = start + rel
    end = start + len(piece)
    return piece, start, end


def _hinted_span(
    source: str,
    raw: str,
    char_start: Any,
    char_end: Any,
) -> tuple[int, int] | None:
    if char_start is None or char_end is None:
        return None
    try:
        start = int(char_start)
        end = int(char_end)
    except (TypeError, ValueError):
        return None
    if start < 0 or end > len(source) or start >= end:
        return None
    excerpt = source[start:end]
    if excerpt == raw or excerpt.strip() == raw or _norm(excerpt) == _norm(raw):
        return start, end
    return None


def _normalized_span(source: str, raw: str, search_from: int) -> tuple[str, int, int] | None:
    src_norm, index = _norm_index(source)
    needle = _norm(raw)
    if not needle or not src_norm:
        return None
    from_norm = 0
    if search_from > 0:
        for i, src_i in enumerate(index):
            if src_i >= search_from:
                from_norm = i
                break
        else:
            from_norm = len(src_norm)
    nidx = src_norm.find(needle, from_norm)
    if nidx < 0 and from_norm:
        nidx = src_norm.find(needle)
    if nidx < 0:
        return None
    start = index[nidx]
    end = index[nidx + len(needle) - 1] + 1
    return _canonical_slice(source, start, end)


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text.strip())


def _norm_index(source: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index: list[int] = []
    prev_space = True
    for i, ch in enumerate(source):
        if ch.isspace():
            if not prev_space and chars:
                chars.append(" ")
                index.append(i)
            prev_space = True
            continue
        chars.append(ch)
        index.append(i)
        prev_space = False
    if chars and chars[-1] == " ":
        chars.pop()
        index.pop()
    return "".join(chars), index


def _strip_page_markers(text: str) -> str:
    return PAGE_MARKER_RE.sub("\n\n", text).strip()


def _load_json_payload(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    decoder = json.JSONDecoder()
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON object or array in completion")
    idx = min(starts)
    try:
        payload, _end = decoder.raw_decode(text[idx:])
    except json.JSONDecodeError as exc:
        raise ValueError("no JSON object or array in completion") from exc
    return payload
