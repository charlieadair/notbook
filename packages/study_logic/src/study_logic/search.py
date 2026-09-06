"""Optional web search — Study calls this only when supplement=true.

Preferred DEMO wiring is Backend’s injectable (same shape as retrieve):

    search(query: str, top_k: int = 5) -> list[{title, url, snippet}]

or GET /api/v1/supplement/search?q=&top_k= → { results, warning? }.

This module keeps a SearXNG fallback for tests / standalone when `search=` is
not injected. Do not add a second Backend client here if Backend already mounts
one. Unset or down SearXNG → warning + empty hits (never invented).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from study_logic.models import WebCitation

DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT = 8.0
MAX_SNIPPET_CHARS = 280
UNSET_WARNING = "SEARXNG_URL is unset; falling back to vault-only (no web results)."
DOWN_WARNING = "SearXNG is unavailable ({reason}); falling back to vault-only (no web results)."

SearchFn = Callable[..., Any]


@dataclass(frozen=True)
class SearchOutcome:
    hits: list[WebCitation]
    warning: str | None = None


class SearchAdapter(Protocol):
    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> SearchOutcome | Sequence[Mapping[str, Any]]: ...


def call_search(search: SearchFn | SearchAdapter, query: str, top_k: int = DEFAULT_TOP_K) -> SearchOutcome:
    """Normalize Backend’s list callable or a SearchOutcome adapter."""
    raw = _invoke_search(search, query, top_k)
    if isinstance(raw, SearchOutcome):
        return raw
    if isinstance(raw, Mapping) and "results" in raw:
        hits = _citations_from_rows(raw.get("results"))
        warning = raw.get("warning")
        return SearchOutcome(hits=hits, warning=str(warning) if warning else None)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return SearchOutcome(hits=_citations_from_rows(raw))
    return SearchOutcome(hits=[])


def _invoke_search(search: SearchFn | SearchAdapter, query: str, top_k: int) -> object:
    target = search.search if hasattr(search, "search") and callable(getattr(search, "search")) else search
    try:
        return target(query, top_k=top_k)
    except TypeError:
        try:
            return target(query, top_k)
        except TypeError:
            return target(query)


def _citations_from_rows(rows: object) -> list[WebCitation]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    hits: list[WebCitation] = []
    for row in rows:
        if isinstance(row, WebCitation):
            hits.append(row)
            continue
        if not isinstance(row, Mapping):
            continue
        parsed = WebCitation.from_mapping(row)
        if parsed is None or not _is_http_url(parsed.url):
            continue
        hits.append(
            WebCitation(
                url=parsed.url,
                title=parsed.title,
                snippet=_clip(parsed.snippet, MAX_SNIPPET_CHARS),
            )
        )
    return hits


class UnavailableSearch:
    """Explicit no-op adapter — never fabricates results."""

    def __init__(self, warning: str = UNSET_WARNING) -> None:
        self.warning = warning

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> SearchOutcome:
        return SearchOutcome(hits=[], warning=self.warning)


class SearxngClient:
    """Fallback HTTP client for a self-hosted SearXNG JSON search API.

    Prefer injecting Backend’s `search=` callable in DEMO. This exists for
    standalone / tests when that hook is omitted.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> SearchOutcome:
        q = (query or "").strip()
        if not q:
            return SearchOutcome(hits=[])
        try:
            response = self._client.get(
                f"{self.base_url}/search",
                params={"q": q, "format": "json"},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return SearchOutcome(
                hits=[],
                warning=DOWN_WARNING.format(reason=f"HTTP {exc.response.status_code}"),
            )
        except httpx.HTTPError as exc:
            return SearchOutcome(
                hits=[],
                warning=DOWN_WARNING.format(reason=exc.__class__.__name__),
            )
        try:
            payload = response.json()
        except ValueError:
            return SearchOutcome(hits=[], warning=DOWN_WARNING.format(reason="invalid JSON"))
        return SearchOutcome(hits=_parse_searxng_results(payload, top_k))


class HttpSupplementSearch:
    """HTTP client mode: GET /api/v1/supplement/search?q=&top_k= → { results, warning? }."""

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> SearchOutcome:
        q = (query or "").strip()
        if not q:
            return SearchOutcome(hits=[])
        params = urllib.parse.urlencode({"q": q, "top_k": top_k})
        url = f"{self.base_url}/api/v1/supplement/search?{params}"
        req = urllib.request.Request(url, headers={"accept": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                body = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return SearchOutcome(
                hits=[],
                warning=DOWN_WARNING.format(reason=f"HTTP {exc.code}"),
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return SearchOutcome(
                hits=[],
                warning=DOWN_WARNING.format(reason=exc.__class__.__name__),
            )
        if not isinstance(body, dict):
            return SearchOutcome(hits=[])
        warning = body.get("warning")
        return SearchOutcome(
            hits=_citations_from_rows(body.get("results"))[: max(0, top_k)],
            warning=str(warning) if warning else None,
        )


def _parse_searxng_results(payload: object, top_k: int) -> list[WebCitation]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("results")
    if not isinstance(raw, list):
        return []
    return _citations_from_rows(raw)[: max(0, top_k)]


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rsplit(" ", 1)[0] + "…"


def search_adapter_from_env(env: Mapping[str, str] | None = None) -> SearchAdapter:
    source = env if env is not None else os.environ
    url = str(source.get("SEARXNG_URL") or "").strip()
    if not url:
        return UnavailableSearch()
    return SearxngClient(url)
