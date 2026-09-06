from __future__ import annotations

from study_logic.models import Attempt, Quiz, QuizItem, Topic


class MemoryStore:
    def __init__(self) -> None:
        self._topics: dict[str, list[Topic]] = {}
        self._quizzes: dict[str, Quiz] = {}
        self._items: dict[str, QuizItem] = {}
        self._attempts: list[Attempt] = []

    def list_topics(self, notebook_id: str) -> list[Topic]:
        return list(self._topics.get(notebook_id, []))

    def set_topics(self, notebook_id: str, topics: list[Topic]) -> None:
        self._topics[notebook_id] = list(topics)

    def put_quiz(self, quiz: Quiz, items: list[QuizItem]) -> None:
        self._quizzes[quiz.id] = quiz
        for item in items:
            self._items[item.id] = item

    def get_quiz(self, quiz_id: str) -> Quiz | None:
        return self._quizzes.get(quiz_id)

    def get_item(self, item_id: str) -> QuizItem | None:
        return self._items.get(item_id)

    def add_attempt(self, attempt: Attempt) -> None:
        self._attempts.append(attempt)

    def list_attempts(self, notebook_id: str) -> list[Attempt]:
        return [a for a in self._attempts if a.notebook_id == notebook_id]
