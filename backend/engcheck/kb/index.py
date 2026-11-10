"""Lokal qidiruv: BM25 (bog'liqliksiz, oflayn) va ixtiyoriy embedding o'xshashligi."""
import math
import re
from collections import Counter

import numpy as np

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
K1, B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if len(w) >= 2]


def bm25_rank(query: str, docs: list[str]) -> list[tuple[int, float]]:
    """[(hujjat indeksi, ball)] — kamayish tartibida, faqat ball > 0."""
    terms = set(tokenize(query))
    if not terms or not docs:
        return []
    tokens = [tokenize(d) for d in docs]
    avg_len = sum(len(t) for t in tokens) / len(tokens) or 1.0
    df = Counter(term for t in tokens for term in set(t) if term in terms)
    scores = []
    for i, doc in enumerate(tokens):
        tf = Counter(doc)
        score = 0.0
        for term in terms:
            if not tf[term]:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * (K1 + 1) / (tf[term] + K1 * (1 - B + B * len(doc) / avg_len))
        if score > 0:
            scores.append((i, score))
    return sorted(scores, key=lambda x: -x[1])


def to_blob(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def cosine_rank(query_vec: list[float], blobs: list[bytes | None], threshold: float = 0.3) -> list[tuple[int, float]]:
    q = np.asarray(query_vec, dtype=np.float32)
    qn = float(np.linalg.norm(q))
    out = []
    for i, blob in enumerate(blobs):
        if not blob or not qn:
            continue
        v = np.frombuffer(blob, dtype=np.float32)
        vn = float(np.linalg.norm(v))
        if v.shape != q.shape or not vn:
            continue
        score = float(np.dot(q, v) / (qn * vn))
        if score >= threshold:
            out.append((i, score))
    return sorted(out, key=lambda x: -x[1])


def rrf(*rankings: list[tuple[int, float]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: bir nechta reytingni birlashtiradi."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, (idx, _) in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])
