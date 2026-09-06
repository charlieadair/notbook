import uuid

from tests.helpers import build_simple_pdf


def test_retrieve_returns_stable_chunk_ids(client, notebook_id):
    client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/paste",
        json={
            "text": (
                "LU factorization writes A = LU with L lower triangular "
                "and U upper triangular. Partial pivoting yields PA = LU."
            )
        },
    )
    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "LU factorization pivoting", "top_k": 5},
    )
    assert response.status_code == 200
    chunks = response.json()["chunks"]
    assert chunks
    ids = [c["id"] for c in chunks]
    for chunk_id in ids:
        uuid.UUID(chunk_id)
        detail = client.get(f"/api/v1/chunks/{chunk_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == chunk_id


def test_pdf_ingest_then_retrieve(client, notebook_id):
    pdf = build_simple_pdf("Eigenvalues and eigenvectors in linear algebra")
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/upload",
        files={"file": ("notes.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["type"] == "pdf"
    assert upload.json()["extract_status"] == "ok"
    assert upload.json()["chunk_count"] >= 1

    chunks = client.get(
        f"/api/v1/notebooks/{notebook_id}/sources/{upload.json()['id']}/chunks"
    )
    assert chunks.status_code == 200
    assert chunks.json()[0]["locator"].get("page") == 1

    retrieved = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "eigenvalues eigenvectors", "top_k": 8},
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["chunks"]
    assert any("Eigenvalues" in c["text"] for c in retrieved.json()["chunks"])
