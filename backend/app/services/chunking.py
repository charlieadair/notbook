from __future__ import annotations

from typing import Any

# ~500–800 token-ish windows (≈4 chars/token) with overlap.
CHUNK_CHARS = 2400
CHUNK_OVERLAP = 400


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
