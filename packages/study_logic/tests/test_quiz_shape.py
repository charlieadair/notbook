import json

from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.models import Chunk, QuizChoice, QuizItem, Topic
from study_logic.quiz import (
    MAX_CHOICE_CHARS,
    MAX_RAW_BLOB_CHARS,
    SOURCE_RECALL_PHRASE,
    build_grounded_items,
    is_exam_shaped_item,
)
from study_logic.vault import InMemoryVault, create_fixture_vault


def _bigo_chunk(**overrides: object) -> Chunk:
    data = dict(
        id="chunk_bigo",
        source_id="notes-bigo",
        text="Big-O describes an upper bound on the growth of a function.",
        locator="lecture-bigo.md#big-o",
        score=1,
        source_filename="lecture-bigo.md",
    )
    data.update(overrides)
    return Chunk(**data)  # type: ignore[arg-type]


def _engine_for(chunks: list[Chunk], complete=None) -> StudyEngine:
    vault = InMemoryVault({"nb_algo": chunks})
    return StudyEngine(retrieve=vault.retrieve, complete=complete)


def test_fixture_items_are_exam_shaped_not_source_recall() -> None:
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve)
    engine.confirm_topics("nb_bio", names=["Mitosis", "Photosynthesis"])
    result = engine.create_quiz("nb_bio")
    assert result["items"]
    for item in result["items"]:
        assert SOURCE_RECALL_PHRASE not in item["stem"].lower()
        assert "stated in the cited source" not in item["stem"].lower()
        correct = next(c for c in item["choices"] if c["id"] == item["correct_choice_id"])
        assert len(correct["text"]) <= MAX_CHOICE_CHARS
        assert "\n" not in correct["text"]
        assert item["citation_chunk_ids"]
        assert item["rationale"]
        assert "because [" in item["rationale"].lower()


def test_bigo_definition_asks_what_it_describes() -> None:
    engine = _engine_for([_bigo_chunk()])
    engine.confirm_topics("nb_algo", names=["Big-O"])
    result = engine.create_quiz("nb_algo")
    assert result["items"]
    item = result["items"][0]
    assert SOURCE_RECALL_PHRASE not in item["stem"].lower()
    assert "what does" in item["stem"].lower()
    assert "big-o" in item["stem"].lower()
    assert "describe" in item["stem"].lower()
    correct = next(c for c in item["choices"] if c["id"] == item["correct_choice_id"])
    assert len(correct["text"]) <= MAX_CHOICE_CHARS
    assert "upper bound" in correct["text"].lower()
    assert correct["text"] != _bigo_chunk().text
    assert "chunk_bigo" in item["citation_chunk_ids"]
    assert "lecture-bigo.md" in item["rationale"]


def test_drops_long_ocr_blob_that_cannot_be_conceptualized() -> None:
    blob = "Big-O lecture notes " + ("garbled slide token " * 20)
    assert len(blob) > MAX_RAW_BLOB_CHARS
    engine = _engine_for(
        [
            Chunk(
                id="chunk_ocr",
                source_id="ocr",
                text=blob.strip(),
                locator="ocr.md",
                score=1,
                source_filename="ocr.md",
            )
        ]
    )
    engine.confirm_topics("nb_algo", names=["Big-O"])
    try:
        engine.create_quiz("nb_algo")
        raise AssertionError("expected InsufficientEvidence")
    except StudyError as exc:
        assert exc.code == "InsufficientEvidence"
        assert exc.status == 422


def test_question_like_ocr_line_is_not_used_as_a_choice() -> None:
    engine = _engine_for(
        [
            _bigo_chunk(
                text=(
                    "Why do we colloquially use Big-O? "
                    "Big-O describes an upper bound on the growth of a function."
                )
            )
        ]
    )
    engine.confirm_topics("nb_algo", names=["Big-O"])
    result = engine.create_quiz("nb_algo")
    assert result["items"]
    for item in result["items"]:
        for choice in item["choices"]:
            assert "why do we colloquially use" not in choice["text"].lower()
        assert "stated in the cited source" not in item["stem"].lower()


def test_stub_complete_falls_back_to_heuristic() -> None:
    def stub_complete(messages, **kwargs):
        return (
            '{"type":"stub","ok":true,'
            '"message":"Inference is stubbed. Set INFERENCE_ADAPTER=openai-compatible."}'
        )

    engine = _engine_for([_bigo_chunk()], complete=stub_complete)
    engine.confirm_topics("nb_algo", names=["Big-O"])
    result = engine.create_quiz("nb_algo")
    item = result["items"][0]
    assert "what does" in item["stem"].lower()
    assert "describe" in item["stem"].lower()
    correct = next(c for c in item["choices"] if c["id"] == item["correct_choice_id"])
    assert len(correct["text"]) <= MAX_CHOICE_CHARS
    assert "upper bound" in correct["text"].lower()


def test_valid_complete_draft_is_preferred() -> None:
    def fake_complete(messages, **kwargs):
        return json.dumps(
            {
                "stem": "What does Big-O describe?",
                "choices": [
                    "an upper bound on growth",
                    "a lower bound on growth",
                    "the exact runtime",
                    "average-case time only",
                ],
                "correct_index": 0,
            }
        )

    engine = _engine_for([_bigo_chunk()], complete=fake_complete)
    engine.confirm_topics("nb_algo", names=["Big-O"])
    result = engine.create_quiz("nb_algo")
    item = result["items"][0]
    assert item["stem"] == "What does Big-O describe?"
    texts = {c["text"] for c in item["choices"]}
    correct = next(c for c in item["choices"] if c["id"] == item["correct_choice_id"])
    assert correct["text"] == "an upper bound on growth"
    assert "a lower bound on growth" in texts
    assert "the exact runtime" in texts
    assert item["citation_chunk_ids"] == ["chunk_bigo"]
    assert "because [lecture-bigo.md] says" in item["rationale"]


def test_complete_source_recall_stem_is_rejected() -> None:
    def bad_complete(messages, **kwargs):
        return json.dumps(
            {
                "stem": 'Which of the following is stated in the cited source material about "Big-O"?',
                "choices": ["an upper bound on growth", "a lower bound"],
                "correct_index": 0,
            }
        )

    engine = _engine_for([_bigo_chunk()], complete=bad_complete)
    engine.confirm_topics("nb_algo", names=["Big-O"])
    result = engine.create_quiz("nb_algo")
    item = result["items"][0]
    assert SOURCE_RECALL_PHRASE not in item["stem"].lower()
    assert "what does" in item["stem"].lower()


def test_is_exam_shaped_item_rejects_source_recall() -> None:
    bad = QuizItem(
        id="i1",
        quiz_id="q1",
        topic_ids=["t1"],
        stem='Which of the following is stated in the cited source material about "Mitosis"?',
        choices=[QuizChoice(id="a", text="two identical daughter cells")],
        correct_choice_id="a",
        citation_chunk_ids=["chunk_mitosis"],
        rationale='because [notes.md] says "Mitosis is cell division."',
    )
    assert not is_exam_shaped_item(bad)

    long_choice = QuizItem(
        id="i2",
        quiz_id="q1",
        topic_ids=["t1"],
        stem="What is Mitosis?",
        choices=[QuizChoice(id="b", text="x" * (MAX_CHOICE_CHARS + 1))],
        correct_choice_id="b",
        citation_chunk_ids=["chunk_mitosis"],
        rationale='because [notes.md] says "Mitosis is cell division."',
    )
    assert not is_exam_shaped_item(long_choice)


def test_build_grounded_items_keeps_citations() -> None:
    topic = Topic(id="t_bigo", notebook_id="nb_algo", name="Big-O", confirmed=True, sort_order=0)
    items = build_grounded_items("quiz1", [topic], {"t_bigo": [_bigo_chunk()]})
    assert items
    assert all(item.citation_chunk_ids == ["chunk_bigo"] for item in items)
    assert all(is_exam_shaped_item(item) for item in items)
