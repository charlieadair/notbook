from fastapi.testclient import TestClient

from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.vault import create_fixture_vault


def test_refuses_quiz_until_topics_confirmed() -> None:
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve)
    proposed = engine.propose_topics("nb_bio")
    assert proposed
    assert all(not t.confirmed for t in proposed)
    try:
        engine.create_quiz("nb_bio")
        raise AssertionError("expected TopicsUnconfirmed")
    except StudyError as exc:
        assert exc.code == "TopicsUnconfirmed"
        assert exc.status == 409


def test_explicit_names_are_already_confirmed() -> None:
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve)
    topics = engine.confirm_topics("nb_bio", names=["Mitosis", "Meiosis"])
    assert [t.name for t in topics] == ["Mitosis", "Meiosis"]
    assert all(t.confirmed for t in topics)
    result = engine.create_quiz("nb_bio")
    assert result["items"]


def test_http_409_until_confirm(client: TestClient) -> None:
    client.post("/api/v1/notebooks/nb_bio/topics/propose")
    refused = client.post("/api/v1/notebooks/nb_bio/quizzes")
    assert refused.status_code == 409
    assert refused.json()["error"] == "TopicsUnconfirmed"

    confirmed = client.post("/api/v1/notebooks/nb_bio/topics/confirm")
    assert confirmed.status_code == 200
    assert all(row["confirmed"] for row in confirmed.json())

    ok = client.post("/api/v1/notebooks/nb_bio/quizzes")
    assert ok.status_code == 200
    assert ok.json()["quiz"]["kind"] == "pretest"
    assert ok.json()["items"]


def test_http_explicit_names_skip_propose(client: TestClient) -> None:
    confirmed = client.post(
        "/api/v1/notebooks/nb_bio/topics/confirm",
        json={"names": ["Mitosis"]},
    )
    assert confirmed.status_code == 200
    assert [row["name"] for row in confirmed.json()] == ["Mitosis"]
    assert confirmed.json()[0]["confirmed"] is True
    quiz = client.post("/api/v1/notebooks/nb_bio/quizzes")
    assert quiz.status_code == 200
    assert quiz.json()["items"]
