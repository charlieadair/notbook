from __future__ import annotations

import json
from typing import Any
from urllib.request import Request

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from study_logic.api import install_study_logic
from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.models import Chunk
from study_logic.vault import HttpVaultRetrieve, InMemoryVault, create_fixture_vault, fixture_chunks


def _recording_retrieve() -> tuple[list[str], Any]:
    calls: list[str] = []

    def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[Chunk]:
        calls.append(query)
        raise AssertionError(f"propose must not retrieve (query={query!r})")

    return calls, retrieve


def test_propose_sampled_chunks_returns_topics() -> None:
    vault = create_fixture_vault()
    engine = StudyEngine(retrieve=vault.retrieve, list_chunks=vault.list_chunks)
    topics = engine.propose_topics("nb_bio")
    names = {t.name for t in topics}
    assert "Mitosis" in names
    assert "Meiosis" in names
    assert "Photosynthesis" in names
    assert all(not t.confirmed for t in topics)


def test_propose_does_not_use_empty_query_retrieve() -> None:
    calls, retrieve = _recording_retrieve()
    engine = StudyEngine(retrieve=retrieve, list_chunks=create_fixture_vault().list_chunks)
    topics = engine.propose_topics("nb_bio")
    assert topics
    assert calls == []


def test_propose_without_list_chunks_refuses_empty_retrieve() -> None:
    calls: list[str] = []

    def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[Chunk]:
        calls.append(query)
        return fixture_chunks()

    engine = StudyEngine(retrieve=retrieve)
    with pytest.raises(StudyError) as exc:
        engine.propose_topics("nb_bio")
    assert exc.value.code == "InsufficientEvidence"
    assert exc.value.status == 422
    assert calls == []


def test_propose_empty_vault_is_honest_empty_not_retrieve_miss() -> None:
    engine = StudyEngine(retrieve=InMemoryVault().retrieve, list_chunks=InMemoryVault().list_chunks)
    assert engine.propose_topics("nb_empty") == []


def test_propose_chunks_without_names_is_insufficient_evidence() -> None:
    vault = InMemoryVault(
        {
            "nb_opaque": [
                Chunk(
                    id="chunk_opaque",
                    source_id="dot",
                    text=".",
                    locator="dot.md",
                    score=1,
                    source_filename="x.md",
                )
            ]
        }
    )
    engine = StudyEngine(retrieve=vault.retrieve, list_chunks=vault.list_chunks)
    with pytest.raises(StudyError) as exc:
        engine.propose_topics("nb_opaque")
    assert exc.value.code == "InsufficientEvidence"
    assert exc.value.status == 422


def test_propose_fallback_names_from_source_label_and_text() -> None:
    vault = InMemoryVault(
        {
            "nb_la": [
                Chunk(
                    id="chunk_spectral",
                    source_id="paste",
                    text="The spectral theorem: a real symmetric matrix is orthogonally diagonalizable.",
                    locator="notes.txt#1",
                    score=1,
                    source_filename="notes.txt",
                )
            ]
        }
    )
    engine = StudyEngine(list_chunks=vault.list_chunks, retrieve=vault.retrieve)
    topics = engine.propose_topics("nb_la")
    assert [t.name for t in topics] == ["spectral theorem"]


def test_http_propose_uses_sample_chunks_not_retrieve() -> None:
    vault = create_fixture_vault()
    app = FastAPI()
    install_study_logic(app, retrieve=vault.retrieve, list_chunks=vault.list_chunks)
    client = TestClient(app)
    proposed = client.post("/api/v1/notebooks/nb_bio/topics/propose")
    assert proposed.status_code == 200
    names = {row["name"] for row in proposed.json()}
    assert {"Mitosis", "Meiosis", "Photosynthesis"} <= names


def test_http_vault_list_chunks_gets_sample_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    class _Resp:
        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(
                [
                    {
                        "id": "chunk_photo",
                        "source_id": "notes",
                        "text": "# Photosynthesis\nPhotosynthesis is conversion of light.",
                        "locator": "notes.md#1",
                        "source_filename": "notes.md",
                    }
                ]
            ).encode("utf-8")

    def fake_urlopen(req: Request, timeout: float | None = None) -> _Resp:
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        return _Resp()

    monkeypatch.setattr("study_logic.vault.urllib.request.urlopen", fake_urlopen)
    vault = HttpVaultRetrieve("http://vault.example")
    retrieve_calls: list[str] = []

    def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[Chunk]:
        retrieve_calls.append(query)
        raise AssertionError("HTTP propose must GET /chunks, not retrieve")

    engine = StudyEngine(retrieve=retrieve, list_chunks=vault.list_chunks)
    topics = engine.propose_topics("nb_bio")
    assert [t.name for t in topics] == ["Photosynthesis"]
    assert retrieve_calls == []
    assert seen["method"] == "GET"
    assert seen["url"] == "http://vault.example/api/v1/notebooks/nb_bio/chunks?limit=32"
