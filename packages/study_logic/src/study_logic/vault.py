from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from study_logic.models import DEFAULT_SAMPLE_LIMIT, DEFAULT_TOP_K, Chunk, is_citable

RetrieveFn = Callable[..., Sequence[Chunk | Mapping[str, Any]]]
ListChunksFn = Callable[..., Sequence[Chunk | Mapping[str, Any]]]


class VaultRetrieve(Protocol):
    def retrieve(self, notebook_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> Sequence[Chunk | Mapping[str, Any]]:
        ...

    def list_chunks(
        self, notebook_id: str, limit: int = DEFAULT_SAMPLE_LIMIT
    ) -> Sequence[Chunk | Mapping[str, Any]]:
        ...


def normalize_chunks(raw: Sequence[Chunk | Mapping[str, Any]]) -> list[Chunk]:
    out: list[Chunk] = []
    for item in raw:
        chunk = item if isinstance(item, Chunk) else Chunk.from_mapping(item)
        if is_citable(chunk):
            out.append(chunk)
    return out


def call_retrieve(retrieve: RetrieveFn, notebook_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[Chunk]:
    result = retrieve(notebook_id, query, top_k)
    return normalize_chunks(list(result))


def call_list_chunks(
    list_chunks: ListChunksFn, notebook_id: str, limit: int = DEFAULT_SAMPLE_LIMIT
) -> list[Chunk]:
    result = list_chunks(notebook_id, limit)
    return normalize_chunks(list(result))


def companion_list_chunks(retrieve: RetrieveFn | None) -> ListChunksFn | None:
    """If retrieve is a bound VaultRetrieve.retrieve, reuse the same object's list_chunks."""
    owner = getattr(retrieve, "__self__", None)
    companion = getattr(owner, "list_chunks", None)
    return companion if callable(companion) else None


class InMemoryVault:
    def __init__(self, seed: Mapping[str, Sequence[Chunk | Mapping[str, Any]]] | None = None) -> None:
        self._chunks: dict[str, list[Chunk]] = {}
        if seed:
            for notebook_id, chunks in seed.items():
                self._chunks[notebook_id] = [c if isinstance(c, Chunk) else Chunk.from_mapping(c) for c in chunks]

    def retrieve(self, notebook_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[Chunk]:
        all_chunks = [c for c in self._chunks.get(notebook_id, []) if is_citable(c)]
        q = query.strip().lower()
        if not q:
            return [Chunk(**{**c.__dict__, "score": c.score or 1}) for c in all_chunks[:top_k]]
        terms = [t for t in q.split() if t]
        ranked: list[tuple[float, Chunk]] = []
        for chunk in all_chunks:
            hay = f"{chunk.text} {chunk.source_filename} {chunk.source_id} {chunk.locator}".lower()
            score = 0.0
            if q in hay:
                score += 5
            score += sum(1 for t in terms if t in hay)
            if score > 0:
                ranked.append((score, chunk))
        ranked.sort(key=lambda row: row[0], reverse=True)
        return [Chunk(**{**chunk.__dict__, "score": score}) for score, chunk in ranked[:top_k]]

    def list_chunks(self, notebook_id: str, limit: int = DEFAULT_SAMPLE_LIMIT) -> list[Chunk]:
        all_chunks = [c for c in self._chunks.get(notebook_id, []) if is_citable(c)]
        return [Chunk(**{**c.__dict__, "score": c.score or 1}) for c in all_chunks[:limit]]

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        for chunks in self._chunks.values():
            for chunk in chunks:
                if chunk.id == chunk_id:
                    return Chunk(**chunk.__dict__)
        return None


class HttpVaultRetrieve:
    """HTTP client mode: POST retrieve for quiz; GET …/chunks for propose."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def retrieve(self, notebook_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[Chunk]:
        url = f"{self.base_url}/api/v1/notebooks/{notebook_id}/retrieve"
        payload = json.dumps({"query": query, "top_k": top_k}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as res:
                body = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Vault retrieve failed: {exc.code}") from exc
        chunks = body.get("chunks") if isinstance(body, dict) else body
        if not isinstance(chunks, list):
            return []
        return normalize_chunks(chunks)

    def list_chunks(self, notebook_id: str, limit: int = DEFAULT_SAMPLE_LIMIT) -> list[Chunk]:
        encoded = urllib.parse.quote(notebook_id, safe="")
        query = urllib.parse.urlencode({"limit": limit})
        url = f"{self.base_url}/api/v1/notebooks/{encoded}/chunks?{query}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req) as res:
                body = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Vault list_chunks failed: {exc.code}") from exc
        if isinstance(body, list):
            chunks = body
        elif isinstance(body, dict):
            chunks = body.get("chunks")
        else:
            chunks = None
        if not isinstance(chunks, list):
            return []
        return normalize_chunks(chunks)


FIXTURE_NOTEBOOK_ID = "nb_bio"


def fixture_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="chunk_mitosis",
            source_id="notes-cell-cycle",
            text=(
                "# Mitosis\n"
                "Mitosis is a type of cell division that produces two genetically identical daughter cells. "
                "The stages of mitosis are prophase, metaphase, anaphase, and telophase. "
                "During metaphase, chromosomes align at the cell equator."
            ),
            locator="notes-cell-cycle.md#mitosis",
            score=1,
            source_filename="notes-cell-cycle.md",
        ),
        Chunk(
            id="chunk_meiosis",
            source_id="notes-cell-cycle",
            text=(
                "# Meiosis\n"
                "Meiosis produces four haploid gametes and includes two rounds of division. "
                "Crossing over occurs during prophase I and increases genetic variation."
            ),
            locator="notes-cell-cycle.md#meiosis",
            score=1,
            source_filename="notes-cell-cycle.md",
        ),
        Chunk(
            id="chunk_photosynthesis",
            source_id="notes-energy",
            text=(
                "# Photosynthesis\n"
                "Photosynthesis converts light energy into chemical energy stored in sugars. "
                "The light-dependent reactions occur in the thylakoid membrane and produce ATP and NADPH."
            ),
            locator="notes-energy.md#photosynthesis",
            score=1,
            source_filename="notes-energy.md",
        ),
    ]


def create_fixture_vault() -> InMemoryVault:
    return InMemoryVault({FIXTURE_NOTEBOOK_ID: fixture_chunks()})
