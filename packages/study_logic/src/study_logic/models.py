from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

SCORE_WINDOW = 20
PROFICIENCY_BAR = 0.8
SEVERE_RATE = 0.5
SEVERE_MISS_COUNT = 3
DEFAULT_TOP_K = 8


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
class QuizItem:
    id: str
    quiz_id: str
    topic_ids: list[str]
    stem: str
    choices: list[QuizChoice]
    correct_choice_id: str
    citation_chunk_ids: list[str]
    rationale: str | None = None

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


class ConfirmBody(BaseModel):
    names: list[str] | None = None
    topics: list[str] | None = None
    topic_ids: list[str] | None = None


class AttemptBody(BaseModel):
    item_id: str = Field(min_length=1)
    selected_choice_id: str = Field(min_length=1)
