import json
from unittest.mock import patch

import httpx

from study_logic.search import (
    DOWN_WARNING,
    UNSET_WARNING,
    HttpSupplementSearch,
    SearxngClient,
    UnavailableSearch,
    call_search,
    search_adapter_from_env,
)


def _transport(handler):
    return httpx.MockTransport(handler)


def test_searxng_parses_json_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["q"] == "Mitosis"
        assert request.url.params["format"] == "json"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://en.wikipedia.org/wiki/Mitosis",
                        "title": "Mitosis - Wikipedia",
                        "content": "Mitosis is a part of the cell cycle in which replicated chromosomes are separated.",
                    },
                    {
                        "url": "https://www.ncbi.nlm.nih.gov/books/NBK2687/",
                        "title": "Mitosis",
                        "content": "The stages of mitosis.",
                    },
                    {"url": "ftp://ignored.example/x", "title": "bad scheme", "content": "skip"},
                    {"url": "", "title": "no url", "content": "skip"},
                ]
            },
        )

    client = SearxngClient("http://searxng.test", transport=_transport(handler))
    outcome = client.search("Mitosis", top_k=3)
    assert outcome.warning is None
    assert len(outcome.hits) == 2
    assert outcome.hits[0].url == "https://en.wikipedia.org/wiki/Mitosis"
    assert outcome.hits[0].title == "Mitosis - Wikipedia"
    assert "cell cycle" in outcome.hits[0].snippet
    assert outcome.hits[0].as_dict()["source"] == "web"


def test_searxng_empty_or_malformed_payload_is_not_invented() -> None:
    def empty_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    empty = SearxngClient("http://searxng.test", transport=_transport(empty_handler)).search("Mitosis")
    assert empty.hits == []
    assert empty.warning is None

    def list_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    listed = SearxngClient("http://searxng.test", transport=_transport(list_handler)).search("Mitosis")
    assert listed.hits == []

    def junk_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    junk = SearxngClient("http://searxng.test", transport=_transport(junk_handler)).search("Mitosis")
    assert junk.hits == []
    assert junk.warning is not None
    assert "invalid JSON" in junk.warning


def test_searxng_down_returns_warning_not_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="nope")

    outcome = SearxngClient("http://searxng.test", transport=_transport(handler)).search("Mitosis")
    assert outcome.hits == []
    assert outcome.warning == DOWN_WARNING.format(reason="HTTP 503")


def test_searxng_connect_error_is_vault_only_warning() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    outcome = SearxngClient("http://searxng.test", transport=_transport(handler)).search("Mitosis")
    assert outcome.hits == []
    assert outcome.warning is not None
    assert "ConnectError" in outcome.warning
    assert "vault-only" in outcome.warning


def test_unset_env_is_unavailable_search() -> None:
    adapter = search_adapter_from_env({})
    assert isinstance(adapter, UnavailableSearch)
    outcome = adapter.search("Mitosis")
    assert outcome.hits == []
    assert outcome.warning == UNSET_WARNING


def test_env_url_builds_client() -> None:
    adapter = search_adapter_from_env({"SEARXNG_URL": "http://127.0.0.1:8080"})
    assert isinstance(adapter, SearxngClient)
    assert adapter.base_url == "http://127.0.0.1:8080"


def test_call_search_accepts_backend_list_callable() -> None:
    def search(query: str, top_k: int = 5):
        assert query == "Mitosis"
        assert top_k == 5
        return [
            {
                "title": "Mitosis - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Mitosis",
                "snippet": "Cell division.",
            }
        ]

    outcome = call_search(search, "Mitosis")
    assert outcome.warning is None
    assert len(outcome.hits) == 1
    assert outcome.hits[0].url == "https://en.wikipedia.org/wiki/Mitosis"
    assert outcome.hits[0].title == "Mitosis - Wikipedia"


def test_call_search_reads_warning_envelope() -> None:
    outcome = call_search(
        lambda q, top_k=5: {"results": [], "warning": UNSET_WARNING},
        "Mitosis",
    )
    assert outcome.hits == []
    assert outcome.warning == UNSET_WARNING


def test_http_supplement_search_parses_backend_envelope() -> None:
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "results": [
                        {
                            "title": "Mitosis - Wikipedia",
                            "url": "https://en.wikipedia.org/wiki/Mitosis",
                            "snippet": "Cell division.",
                        }
                    ]
                }
            ).encode()

    client = HttpSupplementSearch("http://127.0.0.1:8000")
    with patch("urllib.request.urlopen", return_value=_Resp()) as opener:
        outcome = client.search("Mitosis", top_k=5)
    req = opener.call_args[0][0]
    assert "/api/v1/supplement/search" in req.full_url
    assert "q=Mitosis" in req.full_url
    assert "top_k=5" in req.full_url
    assert outcome.hits[0].url == "https://en.wikipedia.org/wiki/Mitosis"
    assert outcome.warning is None


def test_http_supplement_search_down_is_empty_plus_warning() -> None:
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "down", hdrs={}, fp=None)

    client = HttpSupplementSearch("http://127.0.0.1:8000")
    with patch("urllib.request.urlopen", side_effect=boom):
        outcome = client.search("Mitosis")
    assert outcome.hits == []
    assert outcome.warning == DOWN_WARNING.format(reason="HTTP 503")
