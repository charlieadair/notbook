import io
import uuid

from PIL import Image

from app.services import ingest as ingest_service


def test_paste_ingest_source_ok_chunks_and_get_by_id(client, notebook_id):
    pasted = (
        "Cauchy-Schwarz inequality: for vectors u and v, "
        "|<u,v>| <= ||u|| ||v|| in any inner product space."
    )
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/paste",
        json={"filename": "review.txt", "text": pasted},
    )
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["extract_status"] == "ok"
    assert source["type"] == "paste"
    assert source["chunk_count"] >= 1
    uuid.UUID(source["id"])

    listed = client.get(f"/api/v1/notebooks/{notebook_id}/sources")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["extract_status"] == "ok"
    assert rows[0]["chunk_count"] >= 1

    chunks = client.get(
        f"/api/v1/notebooks/{notebook_id}/sources/{source['id']}/chunks"
    )
    assert chunks.status_code == 200
    items = chunks.json()
    assert len(items) >= 1
    chunk_id = items[0]["id"]
    uuid.UUID(chunk_id)
    assert "Cauchy-Schwarz" in items[0]["text"]

    detail = client.get(f"/api/v1/chunks/{chunk_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == chunk_id
    assert body["source"]["filename"] == "review.txt"
    assert body["source"]["type"] == "paste"
    assert "Cauchy-Schwarz" in body["text"]


def test_markdown_upload_searchable_via_retrieve(client, notebook_id):
    markdown = (
        "# Spectral theorem\n\n"
        "A real symmetric matrix is orthogonally diagonalizable.\n"
        "Eigenvalue decomposition is the computational form of that fact.\n"
    )
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/upload",
        files={"file": ("spectral.md", markdown.encode("utf-8"), "text/markdown")},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["extract_status"] == "ok"
    assert upload.json()["chunk_count"] >= 1

    retrieved = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "spectral theorem orthogonal", "top_k": 8},
    )
    assert retrieved.status_code == 200, retrieved.text
    hits = retrieved.json()["chunks"]
    assert hits, "expected at least one retrieved chunk"
    assert any("symmetric matrix" in h["text"] or "spectral" in h["text"].lower() for h in hits)
    for hit in hits:
        uuid.UUID(hit["id"])
        assert "source_id" in hit
        assert "locator" in hit
        assert "score" in hit


def _png_bytes() -> bytes:
    image = Image.new("RGB", (24, 24), color=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_image_ingest_mocked_ocr_creates_chunks(client, notebook_id, monkeypatch):
    monkeypatch.setattr(
        ingest_service,
        "ocr_image",
        lambda _path: "Handwritten notes: Gram-Schmidt orthogonalization.",
    )
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/upload",
        files={"file": ("notes.png", _png_bytes(), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["type"] == "image"
    assert body["extract_status"] == "ok"
    assert body["chunk_count"] >= 1

    chunks = client.get(
        f"/api/v1/notebooks/{notebook_id}/sources/{body['id']}/chunks"
    )
    assert chunks.status_code == 200
    assert "Gram-Schmidt" in chunks.json()[0]["text"]
    assert chunks.json()[0]["locator"].get("region") == "full"


def test_failed_ocr_still_creates_source(client, notebook_id, monkeypatch):
    def boom(_path):
        raise RuntimeError("tesseract not installed")

    monkeypatch.setattr(ingest_service, "ocr_image", boom)
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/upload",
        files={"file": ("scan.jpg", _png_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["extract_status"] == "failed"
    assert body["chunk_count"] == 0
    assert body["error"]
    assert "tesseract" in body["error"].lower()

    listed = client.get(f"/api/v1/notebooks/{notebook_id}/sources")
    assert listed.json()[0]["extract_status"] == "failed"
    assert listed.json()[0]["chunk_count"] == 0
