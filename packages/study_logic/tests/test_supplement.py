import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from study_logic.api import install_study_logic
from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.models import WebCitation
from study_logic.quiz import evidence_is_thin
from study_logic.search import UNSET_WARNING, SearchOutcome, UnavailableSearch
from study_logic.vault import InMemoryVault, create_fixture_vault, fixture_chunks


class SpySearch:
    def __init__(self, outcome: SearchOutcome) -> None:
        self.outcome = outcome
        self.queries: list[str] = []

    def search(self, query: str, *, max_results: int = 3) -> SearchOutcome:
        self.queries.append(query)
        return self.outcome


class BoomSearch:
    def search(self, query: str, *, max_results: int = 3) -> SearchOutcome:
        raise AssertionError("search must not run when supplement is false")


WEB_HIT = WebCitation(
    url="https://en.wikipedia.org/wiki/Mitosis",
    title="Mitosis - Wikipedia",
    snippet="Mitosis produces two genetically identical daughter cells.",
)


def test_supplement_false_path_unchanged() -> None:
    spy = BoomSearch()
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve, search=spy)
    engine.confirm_topics("nb_bio", names=["Mitosis", "Photosynthesis"])
    default = engine.create_quiz("nb_bio")
    explicit = engine.create_quiz("nb_bio", supplement=False)
    known = {c.id for c in fixture_chunks()}
    for result in (default, explicit):
        assert "warnings" not in result
        assert result["items"]
        for item in result["items"]:
            assert item["citation_chunk_ids"]
            assert all(cid in known for cid in item["citation_chunk_ids"])
            assert "web_citations" not in item


def test_supplement_true_attaches_labeled_web_citations() -> None:
    spy = SpySearch(SearchOutcome(hits=[WEB_HIT]))
    captured: list[str] = []

    def fake_complete(messages, **kwargs):
        captured.append(messages[-1]["content"])
        return json.dumps(
            {
                "stem": "What does Mitosis produce?",
                "choices": [
                    "two genetically identical daughter cells",
                    "four haploid gametes",
                    "no change in chromosome number",
                    "a single unchanged parent cell",
                ],
                "correct_index": 0,
            }
        )

    engine = StudyEngine(
        retrieve=create_fixture_vault().retrieve,
        search=spy,
        complete=fake_complete,
    )
    engine.confirm_topics("nb_bio", names=["Mitosis"])
    result = engine.create_quiz("nb_bio", supplement=True)
    assert spy.queries == ["Mitosis"]
    assert result["items"]
    assert "warnings" not in result
    for item in result["items"]:
        assert item["citation_chunk_ids"]
        assert all(cid.startswith("chunk_") for cid in item["citation_chunk_ids"])
        assert item["web_citations"] == [WEB_HIT.as_dict()]
        assert item["web_citations"][0]["source"] == "web"
        assert item["web_citations"][0]["url"] == WEB_HIT.url
        assert "because [" in item["rationale"]
    assert captured
    assert "[web] Mitosis - Wikipedia" in captured[0]
    assert "NOT course truth" in captured[0]


def test_supplement_unset_searxng_warns_and_stays_vault_only() -> None:
    engine = StudyEngine(
        retrieve=create_fixture_vault().retrieve,
        search=UnavailableSearch(),
    )
    engine.confirm_topics("nb_bio", names=["Mitosis"])
    result = engine.create_quiz("nb_bio", supplement=True)
    assert UNSET_WARNING in result["warnings"]
    assert result["items"]
    for item in result["items"]:
        assert item["citation_chunk_ids"]
        assert "web_citations" not in item


def test_supplement_down_searxng_warns_and_does_not_invent() -> None:
    spy = SpySearch(
        SearchOutcome(
            hits=[],
            warning="SearXNG is unavailable (HTTP 503); falling back to vault-only (no web results).",
        )
    )
    engine = StudyEngine(retrieve=create_fixture_vault().retrieve, search=spy)
    engine.confirm_topics("nb_bio", names=["Mitosis"])
    result = engine.create_quiz("nb_bio", supplement=True)
    assert spy.queries == ["Mitosis"]
    assert any("unavailable" in w for w in result["warnings"])
    for item in result["items"]:
        assert "web_citations" not in item
        assert item["citation_chunk_ids"]


def test_supplement_cannot_replace_empty_vault() -> None:
    spy = SpySearch(SearchOutcome(hits=[WEB_HIT]))
    engine = StudyEngine(retrieve=InMemoryVault().retrieve, search=spy)
    engine.confirm_topics("nb_empty", names=["Mitosis"])
    try:
        engine.create_quiz("nb_empty", supplement=True)
        raise AssertionError("expected InsufficientEvidence")
    except StudyError as exc:
        assert exc.code == "InsufficientEvidence"
        assert exc.status == 422
    assert spy.queries == []


def test_http_quiz_body_forwards_supplement() -> None:
    spy = SpySearch(SearchOutcome(hits=[WEB_HIT]))
    app = FastAPI()
    install_study_logic(app, retrieve=create_fixture_vault().retrieve, search=spy)
    client = TestClient(app)
    confirm = client.post(
        "/api/v1/notebooks/nb_bio/topics/confirm",
        json={"names": ["Mitosis"]},
    )
    assert confirm.status_code == 200

    default = client.post("/api/v1/notebooks/nb_bio/quizzes")
    assert default.status_code == 200
    assert spy.queries == []
    assert "web_citations" not in default.json()["items"][0]

    off = client.post("/api/v1/notebooks/nb_bio/quizzes", json={"supplement": False})
    assert off.status_code == 200
    assert spy.queries == []

    on = client.post("/api/v1/notebooks/nb_bio/quizzes", json={"supplement": True})
    assert on.status_code == 200
    assert spy.queries == ["Mitosis"]
    payload = on.json()
    assert payload["items"][0]["citation_chunk_ids"]
    assert payload["items"][0]["web_citations"][0]["url"] == WEB_HIT.url
    assert payload["items"][0]["web_citations"][0]["source"] == "web"


def test_thin_vault_hedge_warning_when_few_sentences() -> None:
    from study_logic.models import Chunk

    thin_chunk = Chunk(
        id="chunk_thin",
        source_id="s",
        text="Big-O describes an upper bound on the growth of a function.",
        locator="x",
        score=1,
        source_filename="thin.md",
    )
    assert evidence_is_thin([thin_chunk])
    spy = SpySearch(SearchOutcome(hits=[WEB_HIT]))
    engine = StudyEngine(retrieve=InMemoryVault({"nb_thin": [thin_chunk]}).retrieve, search=spy)
    engine.confirm_topics("nb_thin", names=["Big-O"])
    result = engine.create_quiz("nb_thin", supplement=True)
    assert any("thin" in w.lower() for w in result["warnings"])
    assert result["items"]
    for item in result["items"]:
        assert item["citation_chunk_ids"] == ["chunk_thin"]
        assert item["web_citations"][0]["source"] == "web"


def test_evidence_is_thin_for_single_short_chunk() -> None:
    from study_logic.models import Chunk

    thin = Chunk(
        id="c1",
        source_id="s",
        text="Too short.",
        locator="x",
        score=1,
        source_filename="x.md",
    )
    assert evidence_is_thin([thin])
    rich = fixture_chunks()
    assert not evidence_is_thin(rich)
