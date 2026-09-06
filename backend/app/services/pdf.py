from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """Return (1-based page number, text) for each page."""
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        pages.append((i, extracted))
    return pages
