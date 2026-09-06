"""Optional web search adapter. Study-logic owns this client.

Backend’s httpx usage is the OpenAI-compatible inference adapter only — not a
search home. Quiz generation decides when to call; this module never invents
hits. Unset or down SearXNG → warning + empty results (vault-only fallback).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import urlparse

import httpx

from study_logic.models import WebCitation

DEFAULT_MAX_RESULTS = 3
DEFAULT_TIMEOUT = 8.0
MAX_SNIPPET_CHARS = 280
UNSET_WARNING = "SEARXNG_URL is unset; falling back to vault-only (no web results)."
DOWN_WARNING = "SearXNG is unavailable ({reason}); falling back to vault-only (no web results)."


@dataclass(frozen=True)
class SearchOutcome:
    hits: list[WebCitation]
    warning: str | None = None


class SearchAdapter(Protocol):
    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> SearchOutcome: ...


class UnavailableSearch:
    """Explicit no-op adapter — never fabricates results."""

    def __init__(self, warning: str = UNSET_WARNING) -> None:
        self.warning = warning

    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> SearchOutcome:
        return SearchOutcome(hits=[], warning=self.warning)


class SearxngClient:
    """HTTP client for a self-hosted SearXNG JSON search API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> SearchOutcome:
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
        return SearchOutcome(hits=_parse_results(payload, max_results))


def _parse_results(payload: object, max_results: int) -> list[WebCitation]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("results")
    if not isinstance(raw, list):
        return []
    hits: list[WebCitation] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        parsed = _hit_from_row(row)
        if parsed is None:
            continue
        hits.append(parsed)
        if len(hits) >= max_results:
            break
    return hits


def _hit_from_row(row: Mapping[str, object]) -> WebCitation | None:
    url = str(row.get("url") or "").strip()
    title = str(row.get("title") or "").strip()
    snippet = str(row.get("content") or row.get("snippet") or "").strip()
    if not _is_http_url(url):
        return None
    if not title:
        title = url
    return WebCitation(url=url, title=title, snippet=_clip(snippet, MAX_SNIPPET_CHARS))


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
