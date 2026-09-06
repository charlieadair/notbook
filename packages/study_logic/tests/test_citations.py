from study_logic.engine import StudyEngine
from study_logic.models import QuizChoice, QuizItem
from study_logic.quiz import MAX_CHOICE_CHARS, is_exam_shaped_item, is_grounded_item, keep_grounded_items
from study_logic.vault import create_fixture_vault, fixture_chunks


def test_generated_items_have_real_citation_chunk_ids() -> None:
    vault = create_fixture_vault()
    engine = StudyEngine(retrieve=vault.retrieve)
    engine.confirm_topics("nb_bio", names=["Mitosis", "Photosynthesis"])
    result = engine.create_quiz("nb_bio")
    known = {c.id for c in fixture_chunks()}
    assert result["items"]
    for item in result["items"]:
        assert item["citation_chunk_ids"]
        assert "stated in the cited source" not in item["stem"].lower()
        correct = next(c for c in item["choices"] if c["id"] == item["correct_choice_id"])
        assert len(correct["text"]) <= MAX_CHOICE_CHARS
        assert item.get("rationale")
        assert "because [" in item["rationale"].lower()
        for chunk_id in item["citation_chunk_ids"]:
            assert chunk_id in known
            chunk = vault.get_chunk(chunk_id)
            assert chunk is not None
            assert chunk.text.strip()


def test_drops_uncited_items() -> None:
    known = {"chunk_mitosis"}
    cited = QuizItem(
        id="i1",
        quiz_id="q1",
        topic_ids=["t1"],
        stem="grounded",
        choices=[QuizChoice(id="a", text="from source")],
        correct_choice_id="a",
        citation_chunk_ids=["chunk_mitosis"],
    )
    uncited = QuizItem(
        id="i2",
        quiz_id="q1",
        topic_ids=["t1"],
        stem="invented",
        choices=[QuizChoice(id="b", text="not in vault")],
        correct_choice_id="b",
        citation_chunk_ids=[],
    )
    unknown = QuizItem(
        id="i3",
        quiz_id="q1",
        topic_ids=["t1"],
        stem="fake cite",
        choices=[QuizChoice(id="c", text="ghost")],
        correct_choice_id="c",
        citation_chunk_ids=["chunk_missing"],
    )
    kept = keep_grounded_items([cited, uncited, unknown], known)
    assert [item.id for item in kept] == ["i1"]
    assert is_grounded_item(cited, known)
    assert not is_grounded_item(uncited, known)
