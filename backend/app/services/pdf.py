from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 200
DEFAULT_MAX_CHARS = 500_000


def extract_pdf_pages(
    path: Path,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[tuple[int, str]]:
    """Return (1-based page number, text) for each page.

    Stops at ``max_pages`` / ``max_chars`` so a huge or malformed PDF cannot
    expand extract indefinitely. Per-page pypdf failures are skipped; a hang
    inside ``PdfReader`` / ``extract_text`` must be bounded by the caller.
    """
    try:
        reader = PdfReader(str(path), strict=False)
    except Exception as exc:
        raise ValueError(f"PDF could not be opened: {exc}") from exc

    pages: list[tuple[int, str]] = []
    total_chars = 0
    try:
        page_list = reader.pages
    except Exception as exc:
        raise ValueError(f"PDF page tree could not be read: {exc}") from exc

    for i, page in enumerate(page_list, start=1):
        if i > max_pages:
            logger.info("PDF extract stopped at page limit (%s) for %s", max_pages, path.name)
            break
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:
            logger.warning("pypdf failed on page %s of %s: %s", i, path.name, exc)
            extracted = ""
        remaining = max_chars - total_chars
        if remaining <= 0:
            logger.info("PDF extract stopped at char limit (%s) for %s", max_chars, path.name)
            break
        if len(extracted) > remaining:
            extracted = extracted[:remaining]
            pages.append((i, extracted))
            logger.info("PDF extract truncated at char limit (%s) for %s", max_chars, path.name)
            break
        pages.append((i, extracted))
        total_chars += len(extracted)
    return pages
