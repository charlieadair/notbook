from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, model_validator

SCORE_WINDOW = 20
PROFICIENCY_BAR = 0.8
SEVERE_RATE = 0.5
SEVERE_MISS_COUNT = 3
DEFAULT_TOP_K = 8
DEFAULT_SAMPLE_LIMIT = 32
MAX_SPAWN = 2


@dataclass
class Chunk:
    id: str
    source_id: str
    text: str
    locator: str
    score: float
    source_filename: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Chunk:
        return cls(
            id=str(data["id"]),
            source_id=str(data.get("source_id", "")),
            text=str(data.get("text", "")),
            locator=str(data.get("locator", "")),
            score=float(data.get("score") or 0),
            source_filename=str(data.get("source_filename", "")),
        )


def is_citable(chunk: Chunk) -> bool:
    return bool(chunk.id.strip()) and bool(chunk.text.strip())


@dataclass
class Topic:
    id: str
    notebook_id: str
    name: str
    confirmed: bool
    sort_order: int
    parent_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "name": self.name,
            "confirmed": self.confirmed,
            "sort_order": self.sort_order,
            "parent_id": self.parent_id,
        }


@dataclass
class QuizChoice:
    id: str
    text: str


@dataclass
class WebCitation:
    """Labeled web provenance — never a vault chunk id."""

    url: str
    title: str
    snippet: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": "web",
        }


@dataclass
class QuizItem:
    id: str
    quiz_id: str
    topic_ids: list[str]
    stem: str
    choices: list[QuizChoice]
    correct_choice_id: str
    citation_chunk_ids: list[str]
    rationale: str | None = None
    web_citations: list[WebCitation] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "quiz_id": self.quiz_id,
            "topic_ids": list(self.topic_ids),
            "stem": self.stem,
            "choices": [{"id": c.id, "text": c.text} for c in self.choices],
            "correct_choice_id": self.correct_choice_id,
            "citation_chunk_ids": list(self.citation_chunk_ids),
            **({"rationale": self.rationale} if self.rationale else {}),
            **({"web_citations": [w.as_dict() for w in self.web_citations]} if self.web_citations else {}),
        }


@dataclass
class Quiz:
    id: str
    notebook_id: str
    kind: Literal["pretest"]
    item_ids: list[str]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "kind": self.kind,
            "item_ids": list(self.item_ids),
            "created_at": self.created_at,
        }


@dataclass
class Attempt:
    id: str
    item_id: str
    quiz_id: str
    notebook_id: str
    selected_choice_id: str
    correct: bool
    topic_ids: list[str]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "quiz_id": self.quiz_id,
            "notebook_id": self.notebook_id,
            "selected_choice_id": self.selected_choice_id,
            "correct": self.correct,
            "topic_ids": list(self.topic_ids),
            "created_at": self.created_at,
        }


@dataclass
class TopicScore:
    topic_id: str
    notebook_id: str
    correct_count: int
    attempt_count: int
    correct_rate: float
    proficient: bool
    severity: Literal["ok", "mild", "severe"]
    updated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "notebook_id": self.notebook_id,
            "correct_count": self.correct_count,
            "attempt_count": self.attempt_count,
            "correct_rate": self.correct_rate,
            "proficient": self.proficient,
            "severity": self.severity,
            "updated_at": self.updated_at,
        }


@dataclass
class Scoreboard:
    topics: list[TopicScore]
    window: int = SCORE_WINDOW
    proficiency_bar: float = PROFICIENCY_BAR

    def as_dict(self) -> dict[str, Any]:
        return {
            "topics": [t.as_dict() for t in self.topics],
            "window": self.window,
            "proficiency_bar": self.proficiency_bar,
        }


@dataclass
class Chat:
    id: str
    notebook_id: str
    kind: Literal["orchestrator", "specialist"]
    topic_ids: list[str]
    status: Literal["open", "closed"]
    created_at: str
    closed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "kind": self.kind,
            "topic_ids": list(self.topic_ids),
            "status": self.status,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }


@dataclass
class ChatMessage:
    id: str
    chat_id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "role": self.role,
            "text": self.text,
            "created_at": self.created_at,
        }


@dataclass
class SpawnCandidate:
    topic_id: str
    severity: Literal["mild", "severe"]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "severity": self.severity,
            "reason": self.reason,
        }


@dataclass
class SpawnOffer:
    notebook_id: str
    candidates: list[SpawnCandidate]
    max_spawn: int = MAX_SPAWN

    def as_dict(self) -> dict[str, Any]:
        return {
            "notebook_id": self.notebook_id,
            "candidates": [c.as_dict() for c in self.candidates],
            "max_spawn": self.max_spawn,
        }


@dataclass
class Handoff:
    id: str
    from_chat_id: str
    to_chat_id: str
    topic_ids: list[str]
    summary: str
    scoreboard_snapshot: list[TopicScore]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_chat_id": self.from_chat_id,
            "to_chat_id": self.to_chat_id,
            "topic_ids": list(self.topic_ids),
            "summary": self.summary,
            "scoreboard_snapshot": [s.as_dict() for s in self.scoreboard_snapshot],
            "created_at": self.created_at,
        }


class ConfirmBody(BaseModel):
    names: list[str] | None = None
    topics: list[str] | None = None
    topic_ids: list[str] | None = None


class AttemptBody(BaseModel):
    item_id: str = Field(min_length=1)
    selected_choice_id: str = Field(min_length=1)


class QuizBody(BaseModel):
    """Optional topic scope. Omit for the S0 whole-notebook pretest.

    ``supplement=true`` is an explicit opt-in for labeled web background.
    Vault remains the default and is still required for citations.
    """

    topic_ids: list[str] | None = None
    supplement: bool = False


class SpecialistBody(BaseModel):
    topic_ids: list[str] = Field(min_length=1)


class MessageBody(BaseModel):
    """POST /chats/{id}/messages body.

    `text` is canonical. `content` is accepted as a Web-compat alias.
    If both are present, `text` wins.
    """

    role: Literal["user", "assistant"] = "user"
    text: str | None = None
    content: str | None = None
    generate_quiz: bool = False

    @model_validator(mode="after")
    def require_text_or_content(self) -> MessageBody:
        if self.text is None and self.content is None and not self.generate_quiz:
            raise ValueError("message body requires 'text' (canonical) or 'content' (Web alias)")
        return self

    def resolved_text(self) -> str:
        if self.text is not None:
            return self.text
        if self.content is not None:
            return self.content
        return ""
