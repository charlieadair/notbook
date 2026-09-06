from __future__ import annotations

import re
import uuid

from study_logic.models import Chunk, Topic

DEFINITION = re.compile(r"^([A-Z][A-Za-z0-9][A-Za-z0-9 \-]{1,48})\s+is\s+")
FIRST_CLAUSE = re.compile(
    r"^([A-Z][A-Za-z0-9][A-Za-z0-9 \-]{1,48})\s+(?:is|are|was|were)\s+"
)
HEADING = re.compile(r"^#{1,3}\s+(.+)$")
_WORD = re.compile(r"[A-Za-z0-9\-]+")
GENERIC_STEMS = {
    "notes",
    "note",
    "upload",
    "document",
    "paste",
    "file",
    "scan",
    "image",
    "untitled",
    "text",
    "handwritten",
    "handwritten scan",
}

TOPIC_STOPWORDS = frozenset(
    {
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "there",
        "here",
        "it",
        "they",
        "we",
        "you",
        "i",
        "a",
        "an",
        "the",
    }
)


def _words(name: str) -> list[str]:
    return _WORD.findall(name)


def _is_stopword_name(name: str) -> bool:
    tokens = _words(name)
    return not tokens or all(token.lower() in TOPIC_STOPWORDS for token in tokens)


def _is_term_like(name: str) -> bool:
    """Prefer multi-word heads, or a single non-stopword token that looks like a term."""
    tokens = _words(name)
    if not tokens or tokens[0].lower() in TOPIC_STOPWORDS or _is_stopword_name(name):
        return False
    if len(tokens) >= 2:
        return True
    token = tokens[0]
    if token.isupper() and len(token) >= 2:
        return True
    return len(token) >= 4


def _iter_sentences(text: str):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or HEADING.match(stripped):
            continue
        for part in re.split(r"(?<=[.!?])\s+", stripped):
            sentence = part.strip()
            if sentence:
                yield sentence


def _source_stem(filename: str) -> str:
    stem = re.sub(r"\.[^.]+$", "", filename or "").replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", stem).strip()


def propose_topic_names(chunks: list[Chunk]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add(raw: str, *, term_like: bool = False) -> None:
        name = re.sub(r"\s+", " ", raw).strip().strip(" .!?")
        key = name.lower()
        if not name or len(key) < 2 or key in seen:
            return
        if _is_stopword_name(name):
            return
        if term_like and not _is_term_like(name):
            return
        seen.add(key)
        names.append(name)

    for chunk in chunks:
        stem = _source_stem(chunk.source_filename)
        if re.match(r"^[A-Z]", stem) and len(stem.split()) <= 4:
            add(stem)
        for line in chunk.text.splitlines():
            heading = HEADING.match(line.strip())
            if heading:
                add(heading.group(1))
        for sentence in _iter_sentences(chunk.text):
            definition = DEFINITION.match(sentence)
            if definition:
                add(definition.group(1), term_like=True)
                continue
            clause = FIRST_CLAUSE.match(sentence)
            if clause:
                add(clause.group(1), term_like=True)
    if names:
        return names

    # S0 fallback: source labels + first clause when notes have no headings.
    for chunk in chunks:
        stem = _source_stem(chunk.source_filename)
        if stem and stem.lower() not in GENERIC_STEMS and len(stem.split()) <= 6:
            add(stem.title() if stem[:1].islower() else stem)
        for line in chunk.text.splitlines():
            clause = re.split(r"[.:\n]", line.strip().lstrip("#").strip(), maxsplit=1)[0].strip()
            clause = re.sub(r"^(The|A|An)\s+", "", clause, flags=re.I)
            if 2 <= len(clause) <= 48:
                add(clause, term_like=True)
                break
    return names


def topics_from_names(notebook_id: str, names: list[str], confirmed: bool) -> list[Topic]:
    return [
        Topic(
            id=str(uuid.uuid4()),
            notebook_id=notebook_id,
            name=name,
            confirmed=confirmed,
            sort_order=index,
            parent_id=None,
        )
        for index, name in enumerate(names)
    ]


def all_topics_confirmed(topics: list[Topic]) -> bool:
    return bool(topics) and all(t.confirmed for t in topics)


def normalize_explicit_names(names: list[str] | None) -> list[str]:
    if not names:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in names:
        name = re.sub(r"\s+", " ", raw).strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out
