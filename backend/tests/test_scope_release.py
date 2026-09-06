from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_unified_sources_post_and_scope_chunk_path(client, notebook_id):
    paste = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"filename": "review.txt", "text": "Cauchy-Schwarz holds in inner product spaces."},
    )
    assert paste.status_code == 201, paste.text
    assert paste.json()["type"] == "paste"
    assert paste.json()["extract_status"] == "ok"

    chunks = client.get(f"/api/v1/sources/{paste.json()['id']}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()
    assert "Cauchy-Schwarz" in chunks.json()[0]["text"]


def test_empty_notebook_and_empty_query_retrieve(client, notebook_id):
    empty = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "spectral theorem", "top_k": 8},
    )
    assert empty.status_code == 200
    assert empty.json()["chunks"] == []

    blank = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "", "top_k": 8},
    )
    assert blank.status_code == 200
    assert blank.json()["chunks"] == []


def test_pdf_paste_image_listed_with_honest_status(client, notebook_id):
    pdf = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/pdf")},
    )
    assert pdf.status_code == 201, pdf.text
    assert pdf.json()["type"] == "pdf"
    assert pdf.json()["extract_status"] == "ok"
    assert pdf.json()["chunk_count"] >= 1

    paste = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={
            "filename": "notes.txt",
            "text": "Partial pivoting yields PA = LU.",
        },
    )
    assert paste.status_code == 201
    assert paste.json()["extract_status"] == "ok"

    image = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={
            "file": (
                "handwritten_scan.png",
                (FIXTURES / "handwritten_scan.png").read_bytes(),
                "image/png",
            )
        },
    )
    assert image.status_code == 201, image.text
    assert image.json()["type"] == "image"
    # Tesseract may be missing: failed/empty is honest, not silent success.
    assert image.json()["extract_status"] in {"ok", "failed"}
    image_chunks = client.get(f"/api/v1/sources/{image.json()['id']}/chunks")
    assert image_chunks.status_code == 200
    if image.json()["extract_status"] == "failed":
        assert image.json()["chunk_count"] == 0
        assert image.json()["error"]
        assert image_chunks.json() == []
    else:
        assert image.json()["chunk_count"] >= 1
        assert image_chunks.json()

    listed = client.get(f"/api/v1/notebooks/{notebook_id}/sources")
    assert listed.status_code == 200
    rows = listed.json()
    types = {row["type"] for row in rows}
    assert types == {"pdf", "paste", "image"}
    assert all("extract_status" in row and "chunk_count" in row for row in rows)

    pdf_chunks = client.get(f"/api/v1/sources/{pdf.json()['id']}/chunks")
    paste_chunks = client.get(f"/api/v1/sources/{paste.json()['id']}/chunks")
    assert pdf_chunks.json()
    assert "spectral theorem" in pdf_chunks.json()[0]["text"].lower()
    assert paste_chunks.json()
    assert "PA = LU" in paste_chunks.json()[0]["text"]
    assert pdf_chunks.json()[0]["locator"].get("page") == 1

    detail = client.get(f"/api/v1/chunks/{pdf_chunks.json()[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["text"]
    assert detail.json()["locator"]

    retrieved = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "spectral theorem", "top_k": 8},
    )
    assert retrieved.status_code == 200
    hits = retrieved.json()["chunks"]
    assert hits
    assert all(h["id"] and h["score"] > 0 for h in hits)


def test_retrieve_callable_same_shape_as_http(client, app, notebook_id):
    client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"text": "The spectral theorem diagonalizes a real symmetric matrix."},
    )
    hits = app.state.retrieve(notebook_id, "spectral theorem", 8)
    assert hits
    first = hits[0]
    assert set(first) == {
        "id",
        "source_id",
        "text",
        "locator",
        "score",
        "source_filename",
    }
    assert first["id"] and first["source_id"] and first["text"]
    assert first["locator"] is not None
    assert first["score"] > 0
    assert first["source_filename"]

    http = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "spectral theorem", "top_k": 8},
    )
    assert http.status_code == 200
    assert http.json()["chunks"] == hits
    assert app.state.study_logic_mounted is True

    topics = client.get(f"/api/v1/notebooks/{notebook_id}/topics")
    assert topics.status_code == 200
    assert topics.json() == []
