import uuid

from tests.helpers import build_simple_pdf


def test_sample_chunks_empty_notebook(client, notebook_id):
    response = client.get(f"/api/v1/notebooks/{notebook_id}/chunks")
    assert response.status_code == 200
    assert response.json() == []


def test_sample_chunks_missing_notebook(client):
    missing = client.get("/api/v1/notebooks/00000000-0000-0000-0000-000000000000/chunks")
    assert missing.status_code == 404


def test_sample_chunks_recent_without_scores(client, notebook_id):
    client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={"file": ("old.pdf", build_simple_pdf("Eigenvalues live in the characteristic polynomial."), "application/pdf")},
    )
    paste = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={
            "filename": "notes.txt",
            "text": "The spectral theorem: a real symmetric matrix is orthogonally diagonalizable.",
        },
    )
    assert paste.status_code == 201

    listed = client.get(f"/api/v1/notebooks/{notebook_id}/chunks?limit=32")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 2
    for row in rows:
        assert set(row) == {"id", "source_id", "text", "locator", "source_filename"}
        assert "score" not in row
        uuid.UUID(row["id"])
        assert row["text"]
        assert row["locator"] is not None
        assert row["source_filename"]

    # Recent sources first — paste was ingested after the PDF.
    assert rows[0]["source_filename"] == "notes.txt"
    assert "spectral theorem" in rows[0]["text"].lower()

    limited = client.get(f"/api/v1/notebooks/{notebook_id}/chunks?limit=1")
    assert limited.status_code == 200
    assert len(limited.json()) == 1
    assert limited.json()[0]["source_filename"] == "notes.txt"
