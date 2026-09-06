from __future__ import annotations

import array
import math


def pack_embedding(vec: list[float]) -> bytes:
    buf = array.array("f", vec)
    return buf.tobytes()


def unpack_embedding(blob: bytes) -> list[float]:
    buf = array.array("f")
    buf.frombytes(blob)
    return buf.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom == 0.0:
        return 0.0
    return dot / denom
