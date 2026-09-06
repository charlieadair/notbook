from pathlib import Path

from app.services.pdf import extract_pdf_pages
from tests.helpers import build_simple_pdf


def test_extract_pdf_pages_respects_max_chars(tmp_path: Path):
    pdf = tmp_path / "long.pdf"
    pdf.write_bytes(build_simple_pdf("Eigenvalue " * 40))
    pages = extract_pdf_pages(pdf, max_pages=10, max_chars=24)
    assert pages
    assert pages[0][0] == 1
    assert len(pages[0][1]) <= 24


def test_extract_pdf_pages_rejects_unreadable_file(tmp_path: Path):
    junk = tmp_path / "not.pdf"
    junk.write_bytes(b"this is not a pdf")
    try:
        extract_pdf_pages(junk)
    except ValueError as exc:
        assert "could not be opened" in str(exc).lower() or "pdf" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for invalid PDF")
