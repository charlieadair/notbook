import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.models import MAX_SPAWN, Attempt
from study_logic.vault import create_fixture_vault, fixture_chunks


def _attempt(notebook_id: str, topic_id: str, *, correct: bool) -> Attempt:
    return Attempt(
        id=str(uuid.uuid4()),
        item_id=str(uuid.uuid4()),
        quiz_id="seed",
        notebook_id=notebook_id,
        selected_choice_id="choice",
        correct=correct,
        topic_ids=[topic_id],
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _confirm(client: TestClient, names: list[str] | None = None) -> list[dict]:
    names = names or ["Mitosis", "Meiosis", "Photosynthesis"]
    res = client.post("/api/v1/notebooks/nb_bio/topics/confirm", json={"names": names})
    assert res.status_code == 200, res.text
    return res.json()


def _wrong_choice(item: dict) -> str:
    return next(choice["id"] for choice in item["choices"] if choice["id"] != item["correct_choice_id"])


def _grade(client: TestClient, quiz_id: str, item: dict, *, correct: bool) -> dict:
    selected = item["correct_choice_id"] if correct else _wrong_choice(item)
    res = client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        json={"item_id": item["id"], "selected_choice_id": selected},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_spawn_offer_empty_when_no_attempts() -> None:
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve)
    engine.confirm_topics("nb_bio", names=["Mitosis", "Meiosis", "Photosynthesis"])
    offer = engine.spawn_offer("nb_bio")
    assert offer.candidates == []
    assert offer.max_spawn == MAX_SPAWN


def test_http_spawn_offer_empty_before_pretest(client: TestClient) -> None:
    _confirm(client)
    offer = client.get("/api/v1/notebooks/nb_bio/spawn-offer")
    assert offer.status_code == 200
    body = offer.json()
    assert body["candidates"] == []
    assert body["max_spawn"] == 2
    # Notebook open: listing chats get-or-creates the orchestrator; specialists stay unopened.
    listed = client.get("/api/v1/notebooks/nb_bio/chats")
    assert listed.status_code == 200
    assert [chat["kind"] for chat in listed.json()] == ["orchestrator"]
    orch = client.post("/api/v1/notebooks/nb_bio/chats/orchestrator")
    again = client.get("/api/v1/notebooks/nb_bio/chats/orchestrator")
    assert orch.status_code == 200
    assert again.json()["id"] == orch.json()["id"] == listed.json()[0]["id"]


def test_spawn_offer_caps_at_two_and_prefers_severe() -> None:
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve)
    topics = engine.confirm_topics("nb_bio", names=["Mitosis", "Meiosis", "Photosynthesis"])
    by_name = {topic.name: topic.id for topic in topics}

    # Two severe (0/2) and one mild (1/2) — offer must drop the mild, keep severe-first.
    for _ in range(2):
        engine.store.add_attempt(_attempt("nb_bio", by_name["Mitosis"], correct=False))
        engine.store.add_attempt(_attempt("nb_bio", by_name["Meiosis"], correct=False))
    engine.store.add_attempt(_attempt("nb_bio", by_name["Photosynthesis"], correct=True))
    engine.store.add_attempt(_attempt("nb_bio", by_name["Photosynthesis"], correct=False))

    offer = engine.spawn_offer("nb_bio")
    assert offer.max_spawn == MAX_SPAWN == 2
    assert len(offer.candidates) == 2
    assert {row.topic_id for row in offer.candidates} == {by_name["Mitosis"], by_name["Meiosis"]}
    assert all(row.severity == "severe" for row in offer.candidates)

    board = engine.scoreboard("nb_bio")
    photo = next(row for row in board.topics if row.topic_id == by_name["Photosynthesis"])
    assert photo.severity == "mild"


def test_http_spawn_offer_after_pretest_prefers_severe(client: TestClient) -> None:
    topics = _confirm(client)
    by_name = {row["name"]: row["id"] for row in topics}
    quiz = client.post("/api/v1/notebooks/nb_bio/quizzes")
    assert quiz.status_code == 200
    payload = quiz.json()
    quiz_id = payload["quiz"]["id"]

    photo_seen = 0
    for item in payload["items"]:
        topic_id = item["topic_ids"][0]
        # Miss every Mitosis/Meiosis item (severe); 1/2 Photosynthesis (mild).
        if topic_id == by_name["Photosynthesis"]:
            _grade(client, quiz_id, item, correct=photo_seen == 0)
            photo_seen += 1
        else:
            _grade(client, quiz_id, item, correct=False)

    offer = client.get("/api/v1/notebooks/nb_bio/spawn-offer")
    assert offer.status_code == 200
    body = offer.json()
    assert body["max_spawn"] == 2
    assert len(body["candidates"]) <= 2
    assert all(row["severity"] == "severe" for row in body["candidates"])
    offered = {row["topic_id"] for row in body["candidates"]}
    assert by_name["Photosynthesis"] not in offered

    board = client.get("/api/v1/notebooks/nb_bio/scoreboard").json()
    photo = next(row for row in board["topics"] if row["topic_id"] == by_name["Photosynthesis"])
    assert photo["severity"] == "mild"


def test_cannot_open_more_than_two_specialists(client: TestClient) -> None:
    topics = _confirm(client)
    first = client.post(
        "/api/v1/notebooks/nb_bio/chats/specialists",
        json={"topic_ids": [topics[0]["id"]]},
    )
    second = client.post(
        "/api/v1/notebooks/nb_bio/chats/specialists",
        json={"topic_ids": [topics[1]["id"]]},
    )
    third = client.post(
        "/api/v1/notebooks/nb_bio/chats/specialists",
        json={"topic_ids": [topics[2]["id"]]},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert third.status_code == 409
    assert third.json()["error"] == "TooManySpecialists"

    listed = client.get("/api/v1/notebooks/nb_bio/chats")
    assert listed.status_code == 200
    open_specialists = [
        chat for chat in listed.json() if chat["kind"] == "specialist" and chat["status"] == "open"
    ]
    assert len(open_specialists) == 2


def test_specialist_attempts_update_shared_scoreboard(client: TestClient) -> None:
    topics = _confirm(client)
    mitosis = next(row for row in topics if row["name"] == "Mitosis")
    spawned = client.post(
        "/api/v1/notebooks/nb_bio/chats/specialists",
        json={"topic_ids": [mitosis["id"]]},
    )
    assert spawned.status_code == 200
    chat_id = spawned.json()["chat"]["id"]

    before = client.get("/api/v1/notebooks/nb_bio/scoreboard").json()
    before_row = next(row for row in before["topics"] if row["topic_id"] == mitosis["id"])
    assert before_row["attempt_count"] == 0

    generated = client.post(f"/api/v1/chats/{chat_id}/messages", json={"generate_quiz": True})
    assert generated.status_code == 200, generated.text
    quiz = generated.json()["quiz"]
    assert quiz["items"]
    known = {chunk.id for chunk in fixture_chunks()}
    for item in quiz["items"]:
        assert item["citation_chunk_ids"]
        assert all(cid in known for cid in item["citation_chunk_ids"])
        assert item["topic_ids"] == [mitosis["id"]]

    first = quiz["items"][0]
    graded = _grade(client, quiz["quiz"]["id"], first, correct=True)
    assert graded["attempt"]["correct"] is True
    assert graded["attempt"]["notebook_id"] == "nb_bio"

    after = client.get("/api/v1/notebooks/nb_bio/scoreboard").json()
    after_row = next(row for row in after["topics"] if row["topic_id"] == mitosis["id"])
    assert after_row["attempt_count"] == before_row["attempt_count"] + 1
    assert after_row["correct_count"] == 1


def test_close_writes_handoff_visible_on_get(client: TestClient) -> None:
    topics = _confirm(client)
    orch = client.post("/api/v1/notebooks/nb_bio/chats/orchestrator")
    again = client.get("/api/v1/notebooks/nb_bio/chats/orchestrator")
    assert orch.status_code == 200
    assert again.status_code == 200
    assert orch.json()["id"] == again.json()["id"]
    assert orch.json()["kind"] == "orchestrator"

    specialist = client.post(
        "/api/v1/notebooks/nb_bio/chats/specialists",
        json={"topic_ids": [topics[0]["id"]]},
    )
    chat_id = specialist.json()["chat"]["id"]
    posted = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"role": "user", "text": "Focus on this topic."},
    )
    assert posted.status_code == 200
    assert posted.json()["message"]["text"] == "Focus on this topic."

    closed = client.post(f"/api/v1/chats/{chat_id}/close")
    assert closed.status_code == 200, closed.text
    handoff = closed.json()["handoff"]
    assert closed.json()["chat"]["status"] == "closed"
    assert closed.json()["chat"]["closed_at"]
    assert handoff["from_chat_id"] == chat_id
    assert handoff["to_chat_id"] == orch.json()["id"]
    assert handoff["topic_ids"] == [topics[0]["id"]]
    assert handoff["summary"]
    assert isinstance(handoff["scoreboard_snapshot"], list)
    assert handoff["scoreboard_snapshot"]

    listed = client.get("/api/v1/notebooks/nb_bio/handoffs")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [handoff["id"]]

    replay = client.post(f"/api/v1/chats/{chat_id}/close")
    assert replay.status_code == 200
    assert replay.json()["handoff"]["id"] == handoff["id"]


def test_empty_vault_generate_quiz_from_chat_still_422(empty_client: TestClient) -> None:
    confirmed = empty_client.post(
        "/api/v1/notebooks/nb_empty/topics/confirm",
        json={"names": ["Mitosis"]},
    )
    assert confirmed.status_code == 200
    specialist = empty_client.post(
        "/api/v1/notebooks/nb_empty/chats/specialists",
        json={"topic_ids": [confirmed.json()[0]["id"]]},
    )
    assert specialist.status_code == 200
    refused = empty_client.post(
        f"/api/v1/chats/{specialist.json()['chat']['id']}/messages",
        json={"generate_quiz": True},
    )
    assert refused.status_code == 422
    assert refused.json()["error"] == "InsufficientEvidence"


def test_closing_orchestrator_does_not_write_handoff() -> None:
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve)
    chat = engine.get_or_create_orchestrator("nb_bio")
    try:
        engine.close_chat(chat.id)
        raise AssertionError("expected BadRequest")
    except StudyError as exc:
        assert exc.code == "BadRequest"
        assert exc.status == 400
    assert engine.list_handoffs("nb_bio") == []
