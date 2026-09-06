from fastapi.testclient import TestClient

from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.models import Chunk
from study_logic.vault import InMemoryVault


def test_empty_vault_does_not_invent_items() -> None:
    engine = StudyEngine(retrieve=InMemoryVault().retrieve)
    engine.confirm_topics("nb_empty", names=["Mitosis"])
    try:
        engine.create_quiz("nb_empty")
        raise AssertionError("expected InsufficientEvidence")
    except StudyError as exc:
        assert exc.code == "InsufficientEvidence"
        assert exc.status == 422


def test_blank_chunks_are_not_citable() -> None:
    vault = InMemoryVault(
        {
            "nb_blank": [
                Chunk(
                    id="chunk_blank",
                    source_id="blank",
                    text="   ",
                    locator="blank.md",
                    score=0,
                    source_filename="blank.md",
                )
            ]
        }
    )
    engine = StudyEngine(retrieve=vault.retrieve)
    engine.confirm_topics("nb_blank", names=["Anything"])
    try:
        engine.create_quiz("nb_blank")
        raise AssertionError("expected InsufficientEvidence")
    except StudyError as exc:
        assert exc.code == "InsufficientEvidence"
        assert exc.status == 422


def test_http_empty_vault_422(empty_client: TestClient) -> None:
    empty_client.post("/api/v1/notebooks/nb_empty/topics/confirm", json={"names": ["Mitosis"]})
    refused = empty_client.post("/api/v1/notebooks/nb_empty/quizzes")
    assert refused.status_code == 422
    assert refused.json()["error"] == "InsufficientEvidence"


def test_propose_empty_vault_returns_no_topics() -> None:
    engine = StudyEngine(retrieve=InMemoryVault().retrieve)
    assert engine.propose_topics("nb_empty") == []
