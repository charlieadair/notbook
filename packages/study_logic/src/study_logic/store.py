from __future__ import annotations

from study_logic.models import Attempt, Chat, ChatMessage, Handoff, Quiz, QuizItem, Topic


class MemoryStore:
    def __init__(self) -> None:
        self._topics: dict[str, list[Topic]] = {}
        self._quizzes: dict[str, Quiz] = {}
        self._items: dict[str, QuizItem] = {}
        self._attempts: list[Attempt] = []
        self._chats: dict[str, Chat] = {}
        self._messages: list[ChatMessage] = []
        self._handoffs: list[Handoff] = []

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

    def put_chat(self, chat: Chat) -> None:
        self._chats[chat.id] = chat

    def get_chat(self, chat_id: str) -> Chat | None:
        return self._chats.get(chat_id)

    def list_chats(self, notebook_id: str) -> list[Chat]:
        chats = [chat for chat in self._chats.values() if chat.notebook_id == notebook_id]
        chats.sort(key=lambda chat: (0 if chat.kind == "orchestrator" else 1, chat.created_at, chat.id))
        return chats

    def get_orchestrator(self, notebook_id: str) -> Chat | None:
        for chat in self.list_chats(notebook_id):
            if chat.kind == "orchestrator":
                return chat
        return None

    def list_open_specialists(self, notebook_id: str) -> list[Chat]:
        return [chat for chat in self.list_chats(notebook_id) if chat.kind == "specialist" and chat.status == "open"]

    def add_message(self, message: ChatMessage) -> None:
        self._messages.append(message)

    def list_messages(self, chat_id: str) -> list[ChatMessage]:
        return [message for message in self._messages if message.chat_id == chat_id]

    def add_handoff(self, handoff: Handoff) -> None:
        self._handoffs.append(handoff)

    def list_handoffs(self, notebook_id: str) -> list[Handoff]:
        chat_ids = {chat.id for chat in self.list_chats(notebook_id)}
        rows = [row for row in self._handoffs if row.from_chat_id in chat_ids or row.to_chat_id in chat_ids]
        rows.sort(key=lambda row: row.created_at)
        return rows

    def get_handoff_for_chat(self, from_chat_id: str) -> Handoff | None:
        for row in self._handoffs:
            if row.from_chat_id == from_chat_id:
                return row
        return None
