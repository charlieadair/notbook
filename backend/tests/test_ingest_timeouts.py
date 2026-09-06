import threading
import time
from pathlib import Path

from tests.helpers import build_simple_pdf

from app.services import ingest as ingest_service

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _hang_until(event: threading.Event, hold: float = 30.0):
    def _fn(*_args, **_kwargs):
        event.wait(timeout=hold)
        raise RuntimeError("hang was not cancelled by timeout")

    return _fn


def test_hanging_embed_upload_returns_chunks_without_vectors(client, notebook_id, app, monkeypatch):
    release = threading.Event()
    app.state.settings.embed_timeout_seconds = 0.4
    monkeypatch.setattr(app.state.inference, "embed", _hang_until(release))

    start = time.monotonic()
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={
            "filename": "review.txt",
            "text": "Cauchy-Schwarz inequality holds in any inner product space.",
        },
    )
    elapsed = time.monotonic() - start
    release.set()

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["extract_status"] == "ok"
    assert body["chunk_count"] >= 1
    assert body["error"] is None
    assert elapsed < 3.0

    listed = client.get(f"/api/v1/notebooks/{notebook_id}/sources")
    assert listed.json()[0]["extract_status"] == "ok"
    assert listed.json()[0]["chunk_count"] >= 1

    retrieved = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "Cauchy-Schwarz inner product", "top_k": 8},
    )
    assert retrieved.status_code == 200
    hits = retrieved.json()["chunks"]
    assert hits
    assert any("Cauchy-Schwarz" in h["text"] for h in hits)


def test_slow_pdf_extract_fails_within_timeout(client, notebook_id, app, monkeypatch):
    release = threading.Event()
    app.state.settings.pdf_extract_timeout_seconds = 0.4
    monkeypatch.setattr(ingest_service, "extract_pdf_pages", _hang_until(release))

    start = time.monotonic()
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={"file": ("notes.pdf", build_simple_pdf("Eigenvalues"), "application/pdf")},
    )
    elapsed = time.monotonic() - start
    release.set()

    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["extract_status"] == "failed"
    assert body["chunk_count"] == 0
    assert body["error"]
    assert "timed out" in body["error"].lower()
    assert elapsed < 3.0

    listed = client.get(f"/api/v1/notebooks/{notebook_id}/sources")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == body["id"]
    assert listed.json()[0]["extract_status"] == "failed"
    assert listed.json()[0]["error"]
    chunks = client.get(f"/api/v1/sources/{body['id']}/chunks")
    assert chunks.status_code == 200
    assert chunks.json() == []


def test_pypdf_exception_marks_source_failed(client, notebook_id, monkeypatch):
    def boom(*_args, **_kwargs):
        raise ValueError("PDF could not be opened: xref broken")

    monkeypatch.setattr(ingest_service, "extract_pdf_pages", boom)
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={"file": ("broken.pdf", build_simple_pdf("x"), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["extract_status"] == "failed"
    assert body["chunk_count"] == 0
    assert "xref" in body["error"].lower() or "could not be opened" in body["error"].lower()


def test_fixture_pdf_still_extracts_ok(client, notebook_id):
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["extract_status"] == "ok"
    assert upload.json()["chunk_count"] >= 1
