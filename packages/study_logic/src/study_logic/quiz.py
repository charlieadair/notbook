from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from study_logic.models import Chunk, Quiz, QuizChoice, QuizItem, Topic, is_citable

GENERIC_DISTRACTORS = [
    "This statement is not present in the retrieved source material.",
    "The retrieved source material does not support this claim.",
    "No citation in the vault states this.",
]


@dataclass
class SentenceHit:
    text: str
    chunk_id: str


def extract_sentences(chunk: Chunk) -> list[SentenceHit]:
    if not is_citable(chunk):
        return []
    without_headings = re.sub(r"^#{1,3}\s+.*$", " ", chunk.text, flags=re.M)
    parts = re.split(r"(?<=[.!?])\s+", without_headings)
    hits: list[SentenceHit] = []
    for part in parts:
        text = re.sub(r"\s+", " ", part).strip()
        if len(text) >= 24:
            hits.append(SentenceHit(text=text, chunk_id=chunk.id))
    return hits


def is_grounded_item(item: QuizItem, known_chunk_ids: set[str]) -> bool:
    if not item.citation_chunk_ids:
        return False
    return all(cid and cid in known_chunk_ids for cid in item.citation_chunk_ids)


def keep_grounded_items(items: list[QuizItem], known_chunk_ids: set[str]) -> list[QuizItem]:
    return [item for item in items if is_grounded_item(item, known_chunk_ids)]


def build_grounded_items(quiz_id: str, topics: list[Topic], evidence: dict[str, list[Chunk]]) -> list[QuizItem]:
    items: list[QuizItem] = []
    all_sentences: list[SentenceHit] = []
    known_ids: set[str] = set()
    for chunks in evidence.values():
        for chunk in chunks:
            known_ids.add(chunk.id)
            all_sentences.extend(extract_sentences(chunk))

    for topic in topics:
        local = [hit for chunk in evidence.get(topic.id, []) for hit in extract_sentences(chunk)]
        used: set[str] = set()
        for hit in local:
            if hit.text in used or len(items) >= 12:
                continue
            used.add(hit.text)
            item = _make_item(quiz_id, topic, hit, all_sentences)
            if item:
                items.append(item)
            if len(used) >= 2:
                break
    return keep_grounded_items(items, known_ids)


def _make_item(quiz_id: str, topic: Topic, hit: SentenceHit, pool: list[SentenceHit]) -> QuizItem | None:
    distractors = _pick_distractors(hit, pool)
    correct_id = str(uuid.uuid4())
    choices = [
        QuizChoice(id=correct_id, text=hit.text),
        *[QuizChoice(id=str(uuid.uuid4()), text=text) for text in distractors],
    ]
    choices.sort(key=lambda c: c.text)
    if len(choices) < 2:
        return None
    return QuizItem(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        topic_ids=[topic.id],
        stem=f'Which of the following is stated in the cited source material about "{topic.name}"?',
        choices=choices,
        correct_choice_id=correct_id,
        citation_chunk_ids=[hit.chunk_id],
        rationale=hit.text,
    )


def _pick_distractors(correct: SentenceHit, pool: list[SentenceHit]) -> list[str]:
    others = [s.text for s in pool if s.text != correct.text and s.chunk_id != correct.chunk_id]
    picked = list(dict.fromkeys(others))[:3]
    i = 0
    while len(picked) < 3:
        picked.append(GENERIC_DISTRACTORS[i % len(GENERIC_DISTRACTORS)])
        i += 1
    return picked


def create_quiz_record(notebook_id: str, items: list[QuizItem], created_at: str) -> Quiz:
    quiz_id = items[0].quiz_id if items else str(uuid.uuid4())
    return Quiz(
        id=quiz_id,
        notebook_id=notebook_id,
        kind="pretest",
        item_ids=[item.id for item in items],
        created_at=created_at,
    )
