from __future__ import annotations

import uuid
from datetime import datetime, timezone

from study_logic.chats import build_handoff_summary, build_spawn_offer
from study_logic.errors import (
    bad_request,
    chat_closed,
    insufficient_evidence,
    not_found,
    too_many_specialists,
    topics_unconfirmed,
)
from study_logic.models import (
    DEFAULT_TOP_K,
    MAX_SPAWN,
    Attempt,
    Chat,
    ChatMessage,
    Handoff,
    Scoreboard,
    SpawnOffer,
    Topic,
    WebCitation,
)
from study_logic.quiz import CompleteFn, build_grounded_items, create_quiz_record, evidence_is_thin
from study_logic.scoreboard import build_scoreboard, score_topic
from study_logic.search import SearchAdapter, search_adapter_from_env
from study_logic.store import MemoryStore
from study_logic.topics import all_topics_confirmed, normalize_explicit_names, propose_topic_names, topics_from_names
from study_logic.vault import (
    ListChunksFn,
    RetrieveFn,
    call_list_chunks,
    call_retrieve,
    companion_list_chunks,
    create_fixture_vault,
)


class StudyEngine:
    def __init__(
        self,
        retrieve: RetrieveFn | None = None,
        store: MemoryStore | None = None,
        list_chunks: ListChunksFn | None = None,
        complete: CompleteFn | None = None,
        search: SearchAdapter | None = None,
    ) -> None:
        if retrieve is None and list_chunks is None:
            vault = create_fixture_vault()
            retrieve = vault.retrieve
            list_chunks = vault.list_chunks
        self.retrieve = retrieve or create_fixture_vault().retrieve
        self.list_chunks = list_chunks or companion_list_chunks(self.retrieve)
        self.store = store or MemoryStore()
        self.complete = complete
        self.search = search

    def propose_topics(self, notebook_id: str) -> list[Topic]:
        # Never sample via retrieve(query=""): Backend blank-query retrieve is [].
        if self.list_chunks is None:
            raise insufficient_evidence(
                "No sample-chunks source (list_chunks= or GET /notebooks/{id}/chunks). "
                "Refuse empty-query retrieve."
            )
        chunks = call_list_chunks(self.list_chunks, notebook_id)
        if not chunks:
            self.store.set_topics(notebook_id, [])
            return []
        names = propose_topic_names(chunks)
        if not names:
            raise insufficient_evidence("Sampled chunks yielded no draft topic names")
        topics = topics_from_names(notebook_id, names, False)
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

    def create_quiz(
        self,
        notebook_id: str,
        topic_ids: list[str] | None = None,
        supplement: bool = False,
    ) -> dict:
        topics = self.store.list_topics(notebook_id)
        if not all_topics_confirmed(topics):
            raise topics_unconfirmed("Confirm every topic before generating a quiz")
        if topic_ids:
            wanted = {tid for tid in topic_ids if tid}
            scoped = [topic for topic in topics if topic.id in wanted]
            if not scoped:
                raise bad_request("No matching confirmed topics for quiz")
            topics = scoped

        evidence: dict[str, list] = {}
        known_ids: set[str] = set()
        for topic in topics:
            chunks = call_retrieve(self.retrieve, notebook_id, topic.name, DEFAULT_TOP_K)
            evidence[topic.id] = chunks
            known_ids.update(c.id for c in chunks)

        if not known_ids:
            raise insufficient_evidence("Vault is empty or returned no citable chunks")

        web_by_topic, warnings = self._supplement_web(topics, evidence) if supplement else ({}, [])

        quiz_id = str(uuid.uuid4())
        items = build_grounded_items(
            quiz_id,
            topics,
            evidence,
            complete=self.complete,
            web_by_topic=web_by_topic or None,
        )
        if not items:
            raise insufficient_evidence("No grounded quiz items could be built from retrieved chunks")

        quiz = create_quiz_record(notebook_id, items, datetime.now(timezone.utc).isoformat())
        self.store.put_quiz(quiz, items)
        payload: dict = {"quiz": quiz.as_dict(), "items": [item.as_dict() for item in items]}
        if supplement and warnings:
            payload["warnings"] = warnings
        return payload

    def _supplement_web(
        self,
        topics: list[Topic],
        evidence: dict[str, list],
    ) -> tuple[dict[str, list[WebCitation]], list[str]]:
        adapter = self.search if self.search is not None else search_adapter_from_env()
        web_by_topic: dict[str, list[WebCitation]] = {}
        warnings: list[str] = []
        thin_names = [topic.name for topic in topics if evidence_is_thin(evidence.get(topic.id, []))]
        if thin_names:
            warnings.append(
                "Vault evidence is thin for: "
                + ", ".join(thin_names)
                + ". Web snippets are a labeled hedge, not course truth."
            )
        for topic in topics:
            outcome = adapter.search(topic.name)
            if outcome.warning and outcome.warning not in warnings:
                warnings.append(outcome.warning)
            if outcome.hits:
                web_by_topic[topic.id] = list(outcome.hits)
        return web_by_topic, warnings

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

    def get_or_create_orchestrator(self, notebook_id: str) -> Chat:
        existing = self.store.get_orchestrator(notebook_id)
        if existing:
            if existing.status == "closed":
                existing.status = "open"
                existing.closed_at = None
                self.store.put_chat(existing)
            return existing
        now = datetime.now(timezone.utc).isoformat()
        chat = Chat(
            id=str(uuid.uuid4()),
            notebook_id=notebook_id,
            kind="orchestrator",
            topic_ids=[],
            status="open",
            created_at=now,
            closed_at=None,
        )
        self.store.put_chat(chat)
        return chat

    def list_chats(self, notebook_id: str) -> list[Chat]:
        # Notebook open / chat list always has a root orchestrator (get-or-create).
        self.get_or_create_orchestrator(notebook_id)
        return self.store.list_chats(notebook_id)

    def spawn_offer(self, notebook_id: str) -> SpawnOffer:
        # Scope: offer only after pretest / attempts — never invent candidates from the topic map.
        if not self.store.list_attempts(notebook_id):
            return SpawnOffer(notebook_id=notebook_id, candidates=[], max_spawn=MAX_SPAWN)
        topics = self.store.list_topics(notebook_id)
        return build_spawn_offer(notebook_id, topics, self.scoreboard(notebook_id))

    def open_specialist(self, notebook_id: str, topic_ids: list[str]) -> dict:
        unique: list[str] = []
        seen: set[str] = set()
        for raw in topic_ids:
            topic_id = raw.strip() if isinstance(raw, str) else str(raw)
            if not topic_id or topic_id in seen:
                continue
            seen.add(topic_id)
            unique.append(topic_id)
        if not unique:
            raise bad_request("topic_ids is required")

        topics = {topic.id: topic for topic in self.store.list_topics(notebook_id)}
        missing = [topic_id for topic_id in unique if topic_id not in topics]
        if missing:
            raise bad_request(f"Unknown topic_ids: {', '.join(missing)}")
        if any(not topics[topic_id].confirmed for topic_id in unique):
            raise topics_unconfirmed("Specialist topics must be confirmed")

        if len(self.store.list_open_specialists(notebook_id)) >= MAX_SPAWN:
            raise too_many_specialists(f"At most {MAX_SPAWN} open specialist chats")

        offered = {candidate.topic_id for candidate in self.spawn_offer(notebook_id).candidates}
        warnings: list[str] = []
        not_offered = [topic_id for topic_id in unique if topic_id not in offered]
        if not_offered:
            warnings.append(
                "topic_ids not in the current spawn offer (mild gaps stay on the scoreboard): "
                + ", ".join(not_offered)
            )

        self.get_or_create_orchestrator(notebook_id)
        now = datetime.now(timezone.utc).isoformat()
        chat = Chat(
            id=str(uuid.uuid4()),
            notebook_id=notebook_id,
            kind="specialist",
            topic_ids=unique,
            status="open",
            created_at=now,
            closed_at=None,
        )
        self.store.put_chat(chat)
        return {"chat": chat.as_dict(), "warnings": warnings}

    def post_message(
        self,
        chat_id: str,
        role: str = "user",
        text: str = "",
        generate_quiz: bool = False,
    ) -> dict:
        chat = self.store.get_chat(chat_id)
        if not chat:
            raise not_found(f"Chat not found: {chat_id}")
        if chat.status != "open":
            raise chat_closed("Cannot post to a closed chat")

        trimmed = (text or "").strip()
        if not trimmed and not generate_quiz:
            raise bad_request("text is required unless generate_quiz is true")

        quiz_payload = None
        stored_role = "assistant" if role == "assistant" else "user"
        if generate_quiz:
            scope = list(chat.topic_ids) if chat.kind == "specialist" and chat.topic_ids else None
            quiz_payload = self.create_quiz(chat.notebook_id, topic_ids=scope)
            if not trimmed:
                trimmed = "Generated a grounded quiz from the vault (items include citation_chunk_ids)."
                stored_role = "assistant"

        message = ChatMessage(
            id=str(uuid.uuid4()),
            chat_id=chat.id,
            role=stored_role,
            text=trimmed,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.store.add_message(message)
        result: dict = {"message": message.as_dict()}
        if quiz_payload:
            result["quiz"] = quiz_payload
        return result

    def close_chat(self, chat_id: str) -> dict:
        chat = self.store.get_chat(chat_id)
        if not chat:
            raise not_found(f"Chat not found: {chat_id}")
        if chat.kind != "specialist":
            raise bad_request("Only specialist chats write a handoff on close")

        existing = self.store.get_handoff_for_chat(chat.id)
        if chat.status == "closed" and existing:
            return {"chat": chat.as_dict(), "handoff": existing.as_dict()}

        now = datetime.now(timezone.utc).isoformat()
        chat.status = "closed"
        chat.closed_at = now
        self.store.put_chat(chat)

        orchestrator = self.get_or_create_orchestrator(chat.notebook_id)
        board = self.scoreboard(chat.notebook_id)
        topics = self.store.list_topics(chat.notebook_id)
        handoff = Handoff(
            id=str(uuid.uuid4()),
            from_chat_id=chat.id,
            to_chat_id=orchestrator.id,
            topic_ids=list(chat.topic_ids),
            summary=build_handoff_summary(chat, topics, board),
            scoreboard_snapshot=list(board.topics),
            created_at=now,
        )
        self.store.add_handoff(handoff)
        return {"chat": chat.as_dict(), "handoff": handoff.as_dict()}

    def list_handoffs(self, notebook_id: str) -> list[Handoff]:
        return self.store.list_handoffs(notebook_id)
