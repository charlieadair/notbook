from __future__ import annotations

import re
import uuid

from study_logic.models import Chunk, Topic

DEFINITION = re.compile(r"^([A-Z][A-Za-z0-9][A-Za-z0-9 \-]{1,48})\s+is\s+")
HEADING = re.compile(r"^#{1,3}\s+(.+)$")
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


def propose_topic_names(chunks: list[Chunk]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        name = re.sub(r"\s+", " ", raw).strip()
        key = name.lower()
        if not name or len(key) < 2 or key in seen:
            return
        seen.add(key)
        names.append(name)

    for chunk in chunks:
        stem = re.sub(r"\.[^.]+$", "", chunk.source_filename or "").replace("-", " ").replace("_", " ")
        stem = re.sub(r"\s+", " ", stem).strip()
        if re.match(r"^[A-Z]", stem) and len(stem.split()) <= 4:
            add(stem)
        for line in chunk.text.splitlines():
            heading = HEADING.match(line.strip())
            if heading:
                add(heading.group(1))
            definition = DEFINITION.match(line.strip())
            if definition:
                add(definition.group(1))
    if names:
        return names

    # S0 fallback: source labels + first clause when notes have no headings.
    for chunk in chunks:
        stem = re.sub(r"\.[^.]+$", "", chunk.source_filename or "").replace("-", " ").replace("_", " ")
        stem = re.sub(r"\s+", " ", stem).strip()
        if stem and stem.lower() not in GENERIC_STEMS and len(stem.split()) <= 6:
            add(stem.title() if stem[:1].islower() else stem)
        for line in chunk.text.splitlines():
            clause = re.split(r"[.:\n]", line.strip().lstrip("#").strip(), maxsplit=1)[0].strip()
            clause = re.sub(r"^(The|A|An)\s+", "", clause, flags=re.I)
            if 2 <= len(clause) <= 48:
                add(clause)
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
