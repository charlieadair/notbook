from __future__ import annotations

from typing import Any

import httpx

from app.inference.base import InferenceAdapter


class OpenAICompatibleInference(InferenceAdapter):
    """Any OpenAI-compatible /v1 HTTP server (local runtime, MCP proxy, or paid provider).

    Base URL and model names come from env — this module does not encode a vendor policy.
    """

    name = "openai-compatible"

    def __init__(
        self,
        api_base: str,
        api_key: str,
        embed_model: str,
        chat_model: str,
        timeout: float | None = None,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
    ) -> None:
        if not api_base or not api_key:
            raise ValueError(
                "OpenAI-compatible adapter requires OPENAI_API_BASE and OPENAI_API_KEY"
            )
        self.api_base = api_base.rstrip("/")
        self.embed_model = embed_model
        self.chat_model = chat_model
        # A single float used to mean "all operations". Prefer explicit connect + read
        # so a stalled OpenRouter/:free embed cannot hold the socket indefinitely.
        if timeout is not None:
            connect_timeout = timeout
            read_timeout = timeout
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=read_timeout,
                pool=connect_timeout,
            ),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.post(
            f"{self.api_base}/embeddings",
            json={"model": self.embed_model, "input": texts},
        )
        response.raise_for_status()
        rows = response.json()["data"]
        rows = sorted(rows, key=lambda row: row.get("index", 0))
        return [row["embedding"] for row in rows]

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        body: dict[str, Any] = {"model": self.chat_model, "messages": messages}
        for key in ("temperature", "max_tokens", "top_p", "stop"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]
        response = self._client.post(f"{self.api_base}/chat/completions", json=body)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
