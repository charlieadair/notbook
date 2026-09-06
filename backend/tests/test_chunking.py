import json
import threading
import time

import pytest

from app.config import Settings
from app.inference.stub import StubInference
from app.services.chunking import (
    chunk_extracted_document,
    chunk_text,
    ground_slice,
    join_pdf_pages,
    llm_chunk_document,
    page_for_offset,
    parse_llm_slices,
    split_budget_segments,
)


def test_heuristic_windows_unchanged():
    text = "x" * 3000
    pieces = chunk_text(text)
    assert len(pieces) >= 2
    assert pieces[0][1]["order"] == 0
    assert "char_start" in pieces[0][1]


def test_parse_llm_slices_object_and_fence():
    raw = """```json
{"slices": [{"text": "Eigenvalues of A", "char_start": 0, "char_end": 16}]}
```"""
    rows = parse_llm_slices(raw)
    assert rows == [{"text": "Eigenvalues of A", "char_start": 0, "char_end": 16}]


def test_parse_llm_slices_bare_list():
    rows = parse_llm_slices('[{"text": "spectral theorem"}]')
    assert rows[0]["text"] == "spectral theorem"


def test_parse_llm_slices_rejects_empty():
    with pytest.raises(ValueError):
        parse_llm_slices('{"type":"stub","ok":true}')


def test_ground_slice_exact_and_whitespace():
    source = "The spectral theorem:\n\na real symmetric matrix is orthogonally diagonalizable."
    exact = ground_slice(source, "The spectral theorem:")
    assert exact is not None
    assert exact[0] == "The spectral theorem:"
    relaxed = ground_slice(
        source,
        "The spectral theorem: a real symmetric matrix is orthogonally diagonalizable.",
    )
    assert relaxed is not None
    assert "symmetric matrix" in relaxed[0]
    assert source[relaxed[1] : relaxed[2]].strip() == relaxed[0]


def test_ground_slice_drops_invented_text():
    source = "Cauchy-Schwarz holds in any inner product space."
    assert ground_slice(source, "The fundamental theorem of calculus.") is None


def test_join_pdf_pages_maps_offsets():
    marked, spans = join_pdf_pages(
        [
            (1, "Eigenvalues live on page one."),
            (2, "SVD lives on page two."),
        ]
    )
    assert "--- page 1 ---" in marked
    assert "--- page 2 ---" in marked
    idx = marked.find("SVD lives")
    assert page_for_offset(spans, idx) == 2
    assert page_for_offset(spans, marked.find("Eigenvalues")) == 1


def test_split_budget_segments_no_overlap():
    text = "aaa\n\nbbb\n\nccc"
    parts = split_budget_segments(text, max_chars=5)
    joined = "".join(segment for _offset, segment in parts)
    assert "aaa" in joined and "ccc" in joined
    offsets = [offset for offset, _segment in parts]
    assert offsets == sorted(offsets)
    assert len(parts) >= 2


class _ScriptedAdapter:
    name = "openai-compatible"

    def __init__(self, complete_fn):
        self._complete_fn = complete_fn
        self.complete_calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        return StubInference().embed(texts)

    def complete(self, messages, **kwargs):
        self.complete_calls += 1
        return self._complete_fn(messages, **kwargs)


def test_llm_chunk_document_returns_grounded_slices():
    source = (
        "Section A: eigenvalues of a real symmetric matrix.\n\n"
        "Section B: the spectral theorem is the computational form of that fact."
    )
    slice_a = "Section A: eigenvalues of a real symmetric matrix."
    slice_b = "Section B: the spectral theorem is the computational form of that fact."

    def complete(_messages, **_kwargs):
        return json.dumps({"slices": [{"text": slice_a}, {"text": slice_b}]})

    adapter = _ScriptedAdapter(complete)
    settings = Settings(chunking_strategy="llm")
    pieces = llm_chunk_document(adapter, settings, text=source)
    assert pieces is not None
    assert [text for text, _loc in pieces] == [slice_a, slice_b]
    assert pieces[0][1]["order"] == 0
    assert pieces[1][1]["order"] == 1
    assert source[pieces[0][1]["char_start"] : pieces[0][1]["char_end"]] == slice_a


def test_llm_chunk_document_maps_pdf_page():
    pages = [
        (1, "Eigenvalues live on page one."),
        (2, "The spectral theorem lives on page two."),
    ]

    def complete(_messages, **_kwargs):
        return json.dumps(
            {"slices": [{"text": "The spectral theorem lives on page two."}]}
        )

    pieces = llm_chunk_document(
        _ScriptedAdapter(complete),
        Settings(chunking_strategy="llm"),
        pages=pages,
    )
    assert pieces is not None
    assert pieces[0][0] == "The spectral theorem lives on page two."
    assert pieces[0][1]["page"] == 2


def test_llm_timeout_returns_none():
    release = threading.Event()

    def hang(_messages, **_kwargs):
        release.wait(timeout=5)
        return "{}"

    settings = Settings(chunking_strategy="llm", llm_chunk_timeout_seconds=0.25)
    start = time.monotonic()
    pieces = llm_chunk_document(
        _ScriptedAdapter(hang),
        settings,
        text="Cauchy-Schwarz holds in any inner product space.",
    )
    elapsed = time.monotonic() - start
    release.set()
    assert pieces is None
    assert elapsed < 1.5


def test_stub_adapter_uses_heuristic_even_when_strategy_llm():
    adapter = StubInference()
    settings = Settings(chunking_strategy="llm")
    assert settings.uses_llm_chunking(adapter.name) is False
    text = "Cauchy-Schwarz holds in any inner product space."
    pieces = chunk_extracted_document(adapter, settings, text=text)
    assert len(pieces) == 1
    assert "Cauchy-Schwarz" in pieces[0][0]


def test_uses_llm_chunking_auto_remote_only():
    auto = Settings(chunking_strategy="auto")
    assert auto.uses_llm_chunking("stub") is False
    assert auto.uses_llm_chunking("openai-compatible") is True
    assert Settings(chunking_strategy="heuristic").uses_llm_chunking("openai-compatible") is False
