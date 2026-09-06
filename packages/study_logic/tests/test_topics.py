from study_logic.models import Chunk
from study_logic.topics import propose_topic_names
from study_logic.vault import fixture_chunks


def _chunk(text: str, filename: str = "lecture.txt") -> Chunk:
    return Chunk(
        id="chunk_1",
        source_id="src",
        text=text,
        locator="lecture.txt",
        score=1,
        source_filename=filename,
    )


def test_rejects_this_is_and_keeps_real_term() -> None:
    names = propose_topic_names([_chunk("This is a lemma. Mitosis is cell division.")])
    lowered = [name.lower() for name in names]
    assert "this" not in lowered
    assert any("mitosis" in name.lower() for name in names)


def test_rejects_what_is_question() -> None:
    names = propose_topic_names([_chunk("What is energy?")])
    assert "what" not in [name.lower() for name in names]


def test_prefers_multi_word_definition_heads() -> None:
    names = propose_topic_names([_chunk("Linear regression is a model that fits a line.")])
    assert "Linear regression" in names
    assert "This" not in names


def test_keeps_headings_and_source_stems() -> None:
    names = propose_topic_names(
        [
            _chunk(
                "# Breadth-first search\nThis is an overview of the algorithm.",
                filename="Algorithms Test.pdf",
            )
        ]
    )
    assert "Breadth-first search" in names
    assert "Algorithms Test" in names
    assert "This" not in names


def test_rejects_stopword_heading_and_stem() -> None:
    names = propose_topic_names([_chunk("# This\nWhat is energy?", filename="This.pdf")])
    lowered = [name.lower() for name in names]
    assert "this" not in lowered
    assert "what" not in lowered


def test_fixture_vault_still_proposes_real_topics() -> None:
    names = propose_topic_names(fixture_chunks())
    assert "Mitosis" in names
    assert "Meiosis" in names
    assert "Photosynthesis" in names
    assert "This" not in names
    assert "What" not in names
