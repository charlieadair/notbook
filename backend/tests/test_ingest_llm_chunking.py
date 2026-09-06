import json
import threading
import time

from app.inference.stub import StubInference
from tests.helpers import build_simple_pdf


class _ScriptedAdapter:
    name = "openai-compatible"

    def __init__(self, complete_fn):
        self._complete_fn = complete_fn
        self.complete_calls = 0
        self.embed_model = "scripted-embed"
        self.chat_model = "scripted-chat"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return StubInference().embed(texts)

    def complete(self, messages, **kwargs):
        self.complete_calls += 1
        return self._complete_fn(messages, **kwargs)


def _install(app, complete_fn, **setting_overrides):
    adapter = _ScriptedAdapter(complete_fn)
    app.state.inference = adapter
    for key, value in setting_overrides.items():
        setattr(app.state.settings, key, value)
    app.state.settings.chunking_strategy = setting_overrides.get("chunking_strategy", "auto")
    return adapter


def test_ingest_stores_llm_slices_when_complete_returns_json(client, notebook_id, app):
    source_text = (
        "Section A: eigenvalues of a real symmetric matrix.\n\n"
        "Section B: the spectral theorem is the computational form of that fact."
    )
    slice_a = "Section A: eigenvalues of a real symmetric matrix."
    slice_b = "Section B: the spectral theorem is the computational form of that fact."

    def complete(_messages, **_kwargs):
        return json.dumps({"slices": [{"text": slice_a}, {"text": slice_b}]})

    adapter = _install(app, complete)
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"filename": "notes.txt", "text": source_text},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["extract_status"] == "ok"
    assert body["chunk_count"] == 2
    assert adapter.complete_calls == 1

    chunks = client.get(f"/api/v1/sources/{body['id']}/chunks")
    assert chunks.status_code == 200
    texts = [row["text"] for row in chunks.json()]
    assert texts == [slice_a, slice_b]
    assert chunks.json()[0]["locator"]["order"] == 0
    assert chunks.json()[1]["locator"]["order"] == 1

    retrieved = client.post(
        f"/api/v1/notebooks/{notebook_id}/retrieve",
        json={"query": "spectral theorem", "top_k": 8},
    )
    assert retrieved.status_code == 200
    hits = retrieved.json()["chunks"]
    assert hits
    assert any("spectral theorem" in hit["text"] for hit in hits)


def test_ingest_llm_timeout_falls_back_to_heuristic(client, notebook_id, app):
    release = threading.Event()

    def hang(_messages, **_kwargs):
        release.wait(timeout=5)
        return "{}"

    adapter = _install(app, hang, llm_chunk_timeout_seconds=0.3, chunking_strategy="llm")
    pasted = "Cauchy-Schwarz inequality holds in any inner product space."
    start = time.monotonic()
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"filename": "review.txt", "text": pasted},
    )
    elapsed = time.monotonic() - start
    release.set()

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["extract_status"] == "ok"
    assert body["chunk_count"] >= 1
    assert body["error"] is None
    assert elapsed < 3.0
    assert adapter.complete_calls == 1

    chunks = client.get(f"/api/v1/sources/{body['id']}/chunks")
    assert "Cauchy-Schwarz" in chunks.json()[0]["text"]


def test_ingest_llm_parse_failure_falls_back_to_heuristic(client, notebook_id, app):
    def bad(_messages, **_kwargs):
        return "not-json definitely"

    _install(app, bad, chunking_strategy="auto")
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"filename": "review.txt", "text": "Partial pivoting yields PA = LU."},
    )
    assert created.status_code == 201, created.text
    assert created.json()["extract_status"] == "ok"
    assert created.json()["chunk_count"] >= 1
    chunks = client.get(f"/api/v1/sources/{created.json()['id']}/chunks")
    assert "PA = LU" in chunks.json()[0]["text"]


def test_ingest_invented_slices_fall_back_to_heuristic(client, notebook_id, app):
    def invented(_messages, **_kwargs):
        return json.dumps({"slices": [{"text": "A fact that is not in the source."}]})

    _install(app, invented)
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"filename": "review.txt", "text": "Cauchy-Schwarz holds in inner product spaces."},
    )
    assert created.status_code == 201, created.text
    assert created.json()["extract_status"] == "ok"
    chunks = client.get(f"/api/v1/sources/{created.json()['id']}/chunks")
    assert "Cauchy-Schwarz" in chunks.json()[0]["text"]
    assert "not in the source" not in chunks.json()[0]["text"]


def test_stub_adapter_does_not_call_complete_for_chunking(client, notebook_id, app, monkeypatch):
    def boom(_messages, **_kwargs):
        raise AssertionError("stub complete must not be used for semantic chunking")

    monkeypatch.setattr(app.state.inference, "complete", boom)
    app.state.settings.chunking_strategy = "auto"
    created = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        json={"filename": "review.txt", "text": "Cauchy-Schwarz holds in inner product spaces."},
    )
    assert created.status_code == 201, created.text
    assert created.json()["extract_status"] == "ok"
    assert created.json()["chunk_count"] >= 1


def test_pdf_ingest_llm_attaches_page_from_markers(client, notebook_id, app):
    def complete(_messages, **_kwargs):
        return json.dumps({"slices": [{"text": "Eigenvalues"}]})

    adapter = _install(app, complete)
    upload = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources",
        files={"file": ("notes.pdf", build_simple_pdf("Eigenvalues"), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["extract_status"] == "ok"
    assert adapter.complete_calls == 1
    chunks = client.get(f"/api/v1/sources/{upload.json()['id']}/chunks")
    assert chunks.json()
    assert "Eigenvalues" in chunks.json()[0]["text"]
    assert chunks.json()[0]["locator"].get("page") == 1
