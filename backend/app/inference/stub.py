from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.inference.base import InferenceAdapter

STUB_DIM = 64
STUB_COMPLETE = (
    '{"type":"stub","ok":true,'
    '"message":"Inference is stubbed. Set INFERENCE_ADAPTER=openai-compatible '
    'plus OPENAI_API_BASE / OPENAI_API_KEY for real completions."}'
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def hash_embed(text: str, dim: int = STUB_DIM) -> list[float]:
    """Deterministic feature-hashed embedding so similar text ranks together offline."""
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        tokens = ["_empty"]
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class StubInference(InferenceAdapter):
    name = "stub"
    embed_model = "stub-hash-v1"
    chat_model = "stub-complete"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [hash_embed(t) for t in texts]

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        return STUB_COMPLETE
