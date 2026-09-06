from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from study_logic.models import Chunk, Quiz, QuizChoice, QuizItem, Topic, is_citable

MAX_CHOICE_CHARS = 100
MAX_RAW_BLOB_CHARS = 150
MAX_EXCERPT_CHARS = 140
SOURCE_RECALL_PHRASE = "stated in the cited source"

# Conceptual contrasts — never “this is not in the retrieved source”.
GENERIC_DISTRACTORS = [
    "a lower bound on growth",
    "the exact runtime",
    "average-case performance only",
    "the reverse of this relationship",
    "an unrelated later stage of the same process",
    "a quantity that is not defined for this topic",
]

KIND_DISTRACTORS: dict[str, list[str]] = {
    "describes": [
        "a lower bound on growth",
        "the exact runtime",
        "average-case performance only",
    ],
    "definition": [
        "the reverse of this process",
        "an unrelated later stage",
        "a quantity that is not defined here",
    ],
    "produces": [
        "four identical diploid cells",
        "no change in chromosome number",
        "a single unchanged parent cell",
    ],
    "converts": [
        "chemical energy into light",
        "heat into mechanical motion",
        "sugars into incoming light",
    ],
    "when": [
        "during interphase only",
        "after the process has already finished",
        "it does not occur in this process",
    ],
    "where": [
        "in the cytoplasm only",
        "outside the cell",
        "in an unrelated organelle",
    ],
    "stages": [
        "interphase, cytokinesis, and apoptosis",
        "a single undivided step",
        "only the final checkpoint",
    ],
    "why": [
        "it reports a lower bound instead",
        "it measures exact wall-clock time",
        "it is never used in practice",
    ],
    "property": [
        "the reverse of this relationship",
        "an unrelated later stage",
        "a quantity that is not defined here",
    ],
}

_DESCRIBES = re.compile(r"^(?P<subj>.+?)\s+describes?\s+(?P<obj>.+)$", re.I)
_MEANS = re.compile(r"^(?P<subj>.+?)\s+means\s+(?P<obj>.+)$", re.I)
_STAGES = re.compile(
    r"^(?:The\s+)?stages\s+of\s+(?P<subj>.+?)\s+(?:are|include)\s+(?P<obj>.+)$", re.I
)
_DURING = re.compile(r"^During\s+(?P<when>.+?),\s+(?P<obj>.+)$", re.I)
_OCCURS_DURING = re.compile(r"^(?P<subj>.+?)\s+occurs?\s+during\s+(?P<obj>.+)$", re.I)
_OCCURS_IN = re.compile(r"^(?P<subj>.+?)\s+occurs?\s+in\s+(?P<obj>.+)$", re.I)
_CONVERTS = re.compile(r"^(?P<subj>.+?)\s+converts?\s+(?P<obj>.+)$", re.I)
_PRODUCES = re.compile(r"^(?P<subj>.+?)\s+produces?\s+(?P<obj>.+)$", re.I)
_INCLUDES = re.compile(r"^(?P<subj>.+?)\s+includes?\s+(?P<obj>.+)$", re.I)
_USE_BECAUSE = re.compile(
    r"(?:we\s+)?(?:colloquially\s+)?use\s+(?P<subj>.+?)\s+because\s+(?P<obj>.+)",
    re.I,
)
_IS_DEF = re.compile(r"^(?P<subj>.+?)\s+(?:is|are)\s+(?P<obj>.+)$", re.I)
_KEY_VERB = re.compile(
    r"\b(?:is|are|describes?|means?|produces?|converts?|occurs?|includes?|uses?)\s+(.+)$",
    re.I,
)
_SOURCE_RECALL_STEM = re.compile(
    r"stated in the cited source|which of the following is stated|according to the (?:cited )?source",
    re.I,
)
_AGENDA = re.compile(r"(?i)\b(agenda|overview|today we will|table of contents|learning objectives)\b")
_TRAILING_PREDICATE = re.compile(
    r"^(includes?|increases?|produces?|occurs?|contains?|creates?)\b", re.I
)


class CompleteFn(Protocol):
    def __call__(self, messages: list[dict[str, Any]], **kwargs: Any) -> str: ...


@dataclass
class SentenceHit:
    text: str
    chunk_id: str
    source_filename: str = ""


@dataclass
class ConceptDraft:
    stem: str
    correct: str
    kind: str
    extras: list[str] = field(default_factory=list)


def extract_sentences(chunk: Chunk) -> list[SentenceHit]:
    if not is_citable(chunk):
        return []
    without_headings = re.sub(r"^#{1,3}\s+.*$", " ", chunk.text, flags=re.M)
    parts = re.split(r"(?<=[.!?])\s+", without_headings)
    hits: list[SentenceHit] = []
    for part in parts:
        text = re.sub(r"\s+", " ", part).strip()
        if len(text) < 24 or not _usable_evidence(text):
            continue
        hits.append(
            SentenceHit(text=text, chunk_id=chunk.id, source_filename=chunk.source_filename)
        )
    return hits


def is_grounded_item(item: QuizItem, known_chunk_ids: set[str]) -> bool:
    if not item.citation_chunk_ids:
        return False
    return all(cid and cid in known_chunk_ids for cid in item.citation_chunk_ids)


def keep_grounded_items(items: list[QuizItem], known_chunk_ids: set[str]) -> list[QuizItem]:
    return [item for item in items if is_grounded_item(item, known_chunk_ids)]


def is_exam_shaped_item(item: QuizItem) -> bool:
    if SOURCE_RECALL_PHRASE in item.stem.lower() or _SOURCE_RECALL_STEM.search(item.stem):
        return False
    correct = next((c for c in item.choices if c.id == item.correct_choice_id), None)
    if correct is None or not _is_clean_choice(correct.text):
        return False
    if not all(_is_clean_choice(choice.text) for choice in item.choices):
        return False
    if not item.citation_chunk_ids:
        return False
    if not item.rationale or "because [" not in item.rationale.lower():
        return False
    return True


def build_grounded_items(
    quiz_id: str,
    topics: list[Topic],
    evidence: dict[str, list[Chunk]],
    complete: CompleteFn | None = None,
) -> list[QuizItem]:
    items: list[QuizItem] = []
    all_sentences: list[SentenceHit] = []
    known_ids: set[str] = set()
    for chunks in evidence.values():
        for chunk in chunks:
            known_ids.add(chunk.id)
            all_sentences.extend(extract_sentences(chunk))

    for topic in topics:
        local = [hit for chunk in evidence.get(topic.id, []) for hit in extract_sentences(chunk)]
        made = 0
        used: set[str] = set()
        for hit in local:
            if hit.text in used or len(items) >= 12:
                continue
            item = _make_item(quiz_id, topic, hit, all_sentences, complete)
            if not item:
                continue
            used.add(hit.text)
            items.append(item)
            made += 1
            if made >= 2:
                break
    return keep_grounded_items(items, known_ids)


def _make_item(
    quiz_id: str,
    topic: Topic,
    hit: SentenceHit,
    pool: list[SentenceHit],
    complete: CompleteFn | None = None,
) -> QuizItem | None:
    drafted = _draft_with_complete(complete, topic, hit) if complete is not None else None
    if drafted is None:
        drafted = _conceptualize(topic, hit.text)
    if drafted is None:
        return None
    if not _is_clean_choice(drafted.correct) or _is_raw_blob(drafted.correct):
        return None
    if _SOURCE_RECALL_STEM.search(drafted.stem):
        return None

    preferred = list(drafted.extras) + list(KIND_DISTRACTORS.get(drafted.kind, []))
    extra = _pick_distractors(drafted.correct, pool, preferred)
    correct_id = str(uuid.uuid4())
    choices = [
        QuizChoice(id=correct_id, text=drafted.correct),
        *[QuizChoice(id=str(uuid.uuid4()), text=text) for text in extra],
    ]
    choices.sort(key=lambda c: c.text.lower())
    if len(choices) < 2:
        return None
    item = QuizItem(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        topic_ids=[topic.id],
        stem=drafted.stem,
        choices=choices,
        correct_choice_id=correct_id,
        citation_chunk_ids=[hit.chunk_id],
        rationale=_grounded_rationale(hit),
    )
    if not is_exam_shaped_item(item):
        return None
    return item


def _draft_with_complete(complete: CompleteFn, topic: Topic, hit: SentenceHit) -> ConceptDraft | None:
    source = hit.source_filename or hit.chunk_id
    prompt = (
        f'Draft one multiple-choice exam item about "{topic.name}".\n\n'
        f"Evidence sentence (cite this; do not invent facts):\n{hit.text}\n\n"
        f"Source label: {source}\n\n"
        "Rules:\n"
        "- Stem must ask for meaning, definition, consequence, or when-to-use.\n"
        '- Never ask which option is "stated in the cited source" or similar source-matching.\n'
        "- Four short clean choices (each ≤ 100 characters). No multi-line dumps.\n"
        "- One correct choice, grounded only in the evidence sentence.\n"
        "- Return JSON only.\n"
    )
    try:
        raw = complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You write grounded exam items. Reply with JSON only: "
                        '{"stem":"...","choices":["...","...","...","..."],'
                        '"correct_index":0}'
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
    except Exception:
        return None
    data = _parse_draft_json(raw)
    if data is None:
        return None
    stem = str(data.get("stem") or "").strip()
    choices = data.get("choices")
    if not stem or not isinstance(choices, list) or len(choices) < 2:
        return None
    if _SOURCE_RECALL_STEM.search(stem):
        return None
    cleaned = [_shorten_phrase(str(c)) for c in choices if str(c).strip()]
    cleaned = [c for c in cleaned if _is_clean_choice(c)]
    if len(cleaned) < 2:
        return None
    idx = data.get("correct_index", 0)
    if not isinstance(idx, int) or idx < 0 or idx >= len(cleaned):
        idx = 0
    correct = cleaned[idx]
    if _is_raw_blob(correct) or correct.rstrip(".") == hit.text.rstrip("."):
        if len(correct) > MAX_CHOICE_CHARS:
            return None
        if len(hit.text) > MAX_CHOICE_CHARS:
            return None
    extras = [c for i, c in enumerate(cleaned) if i != idx]
    return ConceptDraft(stem=stem, correct=correct, kind="property", extras=extras)


def _parse_draft_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict) or data.get("type") == "stub":
        return None
    if "stem" not in data or "choices" not in data:
        return None
    return data


def _conceptualize(topic: Topic, sentence: str) -> ConceptDraft | None:
    text = re.sub(r"\s+", " ", sentence).strip().rstrip(".")
    if not text or not _usable_evidence(text + "."):
        return None

    patterns: list[tuple[re.Pattern[str], str]] = [
        (_STAGES, "stages"),
        (_DURING, "when"),
        (_OCCURS_DURING, "when"),
        (_OCCURS_IN, "where"),
        (_DESCRIBES, "describes"),
        (_MEANS, "definition"),
        (_CONVERTS, "converts"),
        (_PRODUCES, "produces"),
        (_USE_BECAUSE, "why"),
        (_INCLUDES, "property"),
        (_IS_DEF, "definition"),
    ]
    for pattern, kind in patterns:
        match = pattern.match(text)
        if not match:
            continue
        draft = _draft_from_match(topic, kind, match)
        if draft:
            return draft
    return _fallback_draft(topic, text)


def _draft_from_match(topic: Topic, kind: str, match: re.Match[str]) -> ConceptDraft | None:
    groups = match.groupdict()
    obj = _first_clause(groups.get("obj") or "")
    if not obj:
        return None
    correct = _shorten_phrase(obj)
    if not _is_clean_choice(correct):
        return None

    if kind == "stages":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        return ConceptDraft(stem=f"What are the stages of {subject}?", correct=correct, kind=kind)
    if kind == "when" and "when" in groups:
        return ConceptDraft(
            stem=f"What happens during {groups['when'].strip()}?",
            correct=correct,
            kind=kind,
        )
    if kind == "when":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        when = correct if correct.lower().startswith("during ") else f"during {correct}"
        return ConceptDraft(stem=f"When does {subject} occur?", correct=when, kind=kind)
    if kind == "where":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        place = correct if correct.lower().startswith("in ") else f"in {correct}"
        return ConceptDraft(stem=f"Where do {subject} occur?" if _plural_subject(subject) else f"Where does {subject} occur?", correct=place, kind=kind)
    if kind == "describes":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        return ConceptDraft(stem=f"What does {subject} describe?", correct=correct, kind=kind)
    if kind == "converts":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        return ConceptDraft(stem=f"What does {subject} convert?", correct=correct, kind=kind)
    if kind == "produces":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        return ConceptDraft(stem=f"What does {subject} produce?", correct=correct, kind=kind)
    if kind == "why":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        return ConceptDraft(stem=f"Why is {subject} used?", correct=correct, kind=kind)
    if kind == "definition":
        subject = _pretty_subject(groups.get("subj") or topic.name, topic)
        verb = "are" if _plural_subject(subject) else "is"
        return ConceptDraft(stem=f"What {verb} {subject}?", correct=correct, kind=kind)
    subject = _pretty_subject(groups.get("subj") or topic.name, topic)
    return ConceptDraft(stem=f"What does {subject} include?", correct=correct, kind=kind)


def _fallback_draft(topic: Topic, sentence: str) -> ConceptDraft | None:
    match = _KEY_VERB.search(sentence)
    if not match:
        return None
    phrase = _shorten_phrase(_first_clause(match.group(1)))
    if not _is_clean_choice(phrase):
        return None
    if phrase.rstrip(".") == sentence.rstrip(".") and len(phrase) > MAX_CHOICE_CHARS:
        return None
    return ConceptDraft(
        stem=f"Which of the following best describes {topic.name}?",
        correct=phrase,
        kind="property",
    )


def _pick_distractors(correct: str, pool: list[SentenceHit], preferred: list[str]) -> list[str]:
    target = correct.casefold()
    picked: list[str] = []

    def add(text: str) -> None:
        phrase = _shorten_phrase(text)
        if not _is_clean_choice(phrase):
            return
        if phrase.casefold() == target:
            return
        if any(phrase.casefold() == existing.casefold() for existing in picked):
            return
        picked.append(phrase)

    for text in preferred:
        add(text)
        if len(picked) >= 3:
            return picked
    for hit in pool:
        draft = _conceptualize(Topic(id="", notebook_id="", name="", confirmed=True, sort_order=0), hit.text)
        if draft:
            add(draft.correct)
        if len(picked) >= 3:
            return picked
    for text in GENERIC_DISTRACTORS:
        add(text)
        if len(picked) >= 3:
            break
    return picked[:3]


def _grounded_rationale(hit: SentenceHit) -> str:
    source = hit.source_filename or hit.chunk_id
    excerpt = _short_excerpt(hit.text)
    return f'because [{source}] says "{excerpt}"'


def _short_excerpt(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= MAX_EXCERPT_CHARS:
        return cleaned
    return cleaned[: MAX_EXCERPT_CHARS - 1].rsplit(" ", 1)[0] + "…"


def _pretty_subject(raw: str, topic: Topic) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip().rstrip(".")
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.I)
    if not cleaned:
        return topic.name
    if topic.name and topic.name.casefold() in cleaned.casefold():
        return topic.name
    if cleaned.casefold() in topic.name.casefold():
        return topic.name
    if cleaned[0].islower():
        return cleaned[0].upper() + cleaned[1:]
    return cleaned


def _plural_subject(subject: str) -> bool:
    lowered = subject.casefold()
    if lowered.endswith(("sis", "ss")):
        return False
    return lowered.endswith("s") or "reactions" in lowered or "stages" in lowered


def _first_clause(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" .;:")
    if not text:
        return ""
    parts = re.split(r"\s+and\s+", text, maxsplit=1)
    if len(parts) == 2 and _TRAILING_PREDICATE.match(parts[1]):
        return parts[0].strip(" ,")
    return text


def _shorten_phrase(text: str, limit: int = MAX_CHOICE_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip(" .;:")
    if len(text) <= limit:
        return text
    for sep in ("; ", " — ", " - ", ", and ", " that ", ", "):
        head = text.split(sep, 1)[0].strip()
        if 12 <= len(head) <= limit:
            return head
    truncated = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return truncated


def _usable_evidence(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?") and not re.search(r"\b(because|is|are|means|describes)\b", stripped, re.I):
        return False
    if _AGENDA.search(stripped):
        return False
    letters = sum(ch.isalpha() for ch in stripped)
    if letters < 16:
        return False
    if letters / max(len(stripped), 1) < 0.4:
        return False
    return True


def _is_clean_choice(text: str) -> bool:
    if not text or "\n" in text:
        return False
    cleaned = re.sub(r"\s+", " ", text).strip()
    return 2 <= len(cleaned) <= MAX_CHOICE_CHARS


def _is_raw_blob(text: str) -> bool:
    return len(re.sub(r"\s+", " ", text).strip()) > MAX_RAW_BLOB_CHARS


def create_quiz_record(notebook_id: str, items: list[QuizItem], created_at: str) -> Quiz:
    quiz_id = items[0].quiz_id if items else str(uuid.uuid4())
    return Quiz(
        id=quiz_id,
        notebook_id=notebook_id,
        kind="pretest",
        item_ids=[item.id for item in items],
        created_at=created_at,
    )
