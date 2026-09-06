from __future__ import annotations

import uuid
from datetime import datetime, timezone

from study_logic.errors import bad_request, insufficient_evidence, not_found, topics_unconfirmed
from study_logic.models import DEFAULT_TOP_K, Attempt, Scoreboard, Topic
from study_logic.quiz import build_grounded_items, create_quiz_record
from study_logic.scoreboard import build_scoreboard, score_topic
from study_logic.store import MemoryStore
from study_logic.topics import all_topics_confirmed, normalize_explicit_names, propose_topic_names, topics_from_names
from study_logic.vault import RetrieveFn, call_retrieve, create_fixture_vault


class StudyEngine:
    def __init__(self, retrieve: RetrieveFn | None = None, store: MemoryStore | None = None) -> None:
        self.retrieve = retrieve or create_fixture_vault().retrieve
        self.store = store or MemoryStore()

    def propose_topics(self, notebook_id: str) -> list[Topic]:
        chunks = call_retrieve(self.retrieve, notebook_id, "", 50)
        topics = topics_from_names(notebook_id, propose_topic_names(chunks), False)
        self.store.set_topics(notebook_id, topics)
        return topics

    def confirm_topics(
        self,
        notebook_id: str,
        names: list[str] | None = None,
        topics: list[str] | None = None,
        topic_ids: list[str] | None = None,
    ) -> list[Topic]:
        explicit = normalize_explicit_names(names or topics)
        if explicit:
            confirmed = topics_from_names(notebook_id, explicit, True)
            self.store.set_topics(notebook_id, confirmed)
            return confirmed
        existing = self.store.list_topics(notebook_id)
        allow = set(topic_ids) if topic_ids else None
        updated = [
            Topic(
                id=t.id,
                notebook_id=t.notebook_id,
                name=t.name,
                confirmed=True if allow is None else (t.id in allow or t.confirmed),
                sort_order=t.sort_order,
                parent_id=t.parent_id,
            )
            for t in existing
        ]
        self.store.set_topics(notebook_id, updated)
        return updated

    def list_topics(self, notebook_id: str) -> list[Topic]:
        return self.store.list_topics(notebook_id)

    def create_quiz(self, notebook_id: str) -> dict:
        topics = self.store.list_topics(notebook_id)
        if not all_topics_confirmed(topics):
            raise topics_unconfirmed("Confirm every topic before generating a quiz")

        evidence: dict[str, list] = {}
        known_ids: set[str] = set()
        for topic in topics:
            chunks = call_retrieve(self.retrieve, notebook_id, topic.name, DEFAULT_TOP_K)
            evidence[topic.id] = chunks
            known_ids.update(c.id for c in chunks)

        if not known_ids:
            raise insufficient_evidence("Vault is empty or returned no citable chunks")

        quiz_id = str(uuid.uuid4())
        items = build_grounded_items(quiz_id, topics, evidence)
        if not items:
            raise insufficient_evidence("No grounded quiz items could be built from retrieved chunks")

        quiz = create_quiz_record(notebook_id, items, datetime.now(timezone.utc).isoformat())
        self.store.put_quiz(quiz, items)
        return {"quiz": quiz.as_dict(), "items": [item.as_dict() for item in items]}

    def grade_attempt(self, quiz_id: str, item_id: str, selected_choice_id: str) -> dict:
        if not item_id or not selected_choice_id:
            raise bad_request("item_id and selected_choice_id are required")
        quiz = self.store.get_quiz(quiz_id)
        if not quiz:
            raise not_found(f"Quiz not found: {quiz_id}")
        item = self.store.get_item(item_id)
        if not item or item.quiz_id != quiz_id:
            raise not_found(f"Quiz item not found: {item_id}")

        now = datetime.now(timezone.utc).isoformat()
        attempt = Attempt(
            id=str(uuid.uuid4()),
            item_id=item.id,
            quiz_id=quiz.id,
            notebook_id=quiz.notebook_id,
            selected_choice_id=selected_choice_id,
            correct=selected_choice_id == item.correct_choice_id,
            topic_ids=list(item.topic_ids),
            created_at=now,
        )
        self.store.add_attempt(attempt)
        attempts = self.store.list_attempts(quiz.notebook_id)
        scores = [score_topic(quiz.notebook_id, topic_id, attempts, now) for topic_id in item.topic_ids]
        return {"attempt": attempt.as_dict(), "scores": [s.as_dict() for s in scores]}

    def scoreboard(self, notebook_id: str) -> Scoreboard:
        return build_scoreboard(notebook_id, self.store.list_topics(notebook_id), self.store.list_attempts(notebook_id))
