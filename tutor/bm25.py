"""
bm25.py — Minimal BM25Okapi + Reciprocal Rank Fusion (P3.2 hybrid retrieval).

Why hand-rolled instead of the `rank-bm25` package:
  The package is the preferred dependency (tiny, pure Python, battle-tested),
  but it could not be installed while the network was down. This module
  implements the same BM25Okapi algorithm with the same defaults
  (k1=1.5, b=0.75) and the same tokeniser shape, so swapping back is a
  two-line change:
      from rank_bm25 import BM25Okapi   # instead of from tutor.bm25 import BM25Okapi
  and deleting the class below. Both expose .get_scores(tokenized_query).

Pure module: no Chroma / Gemini imports — directly unit-testable offline.
"""

from __future__ import annotations

import math
import re

K1 = 1.5
B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenisation, matching rank-bm25's default."""
    return _TOKEN_RE.findall((text or "").lower())


class BM25Okapi:
    """Okapi BM25 scorer over a corpus of tokenised documents."""

    def __init__(self, corpus: list[list[str]]) -> None:
        self.corpus_size = len(corpus)
        self.corpus = corpus
        self.doc_len = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_len) / self.corpus_size if corpus else 0.0

        self.doc_freqs: list[dict[str, int]] = []
        idf: dict[str, float] = {}
        for doc in corpus:
            freqs: dict[str, int] = {}
            for token in doc:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)
            for token in freqs:
                idf[token] = idf.get(token, 0) + 1

        for token, df in idf.items():
            idf[token] = math.log(1 + (self.corpus_size - df + 0.5) / (df + 0.5))
        self.idf = idf

    def get_scores(self, query: list[str]) -> list[float]:
        """BM25 scores of every corpus document for `query` (parallel to corpus)."""
        scores = [0.0] * self.corpus_size
        for i, (doc_len, freqs) in enumerate(zip(self.doc_len, self.doc_freqs)):
            score = 0.0
            for token in query:
                tf = freqs.get(token)
                if not tf:
                    continue
                denom = tf + K1 * (1 - B + B * doc_len / self.avgdl) if self.avgdl else tf
                score += self.idf.get(token, 0.0) * (tf * (K1 + 1)) / denom
            scores[i] = score
        return scores


def reciprocal_rank_fusion_scored(
    ranked_id_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """
    Reciprocal Rank Fusion (Cormack et al. 2009): fuse several ranked id lists
    into a single ranking with scores. Returns a list of (doc_id, fused_score)
    tuples ordered by descending score (ties broken by first appearance).
    """
    fused: dict[str, float] = {}
    for ranked in ranked_id_lists:
        for rank, doc_id in enumerate(ranked, 1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    ordered_ids = sorted(fused, key=lambda doc_id: (-fused[doc_id], _first_seen(doc_id, ranked_id_lists)))
    return [(doc_id, fused[doc_id]) for doc_id in ordered_ids]


def reciprocal_rank_fusion(ranked_id_lists: list[list[str]], k: int = 60) -> list[str]:
    """
    Reciprocal Rank Fusion (Cormack et al. 2009): fuse several ranked id lists
    into a single ranking. Returns ordered doc_ids.
    """
    return [doc_id for doc_id, _ in reciprocal_rank_fusion_scored(ranked_id_lists, k=k)]


def _first_seen(doc_id: str, ranked_id_lists: list[list[str]]) -> int:
    for i, ranked in enumerate(ranked_id_lists):
        if doc_id in ranked:
            return i
    return 0
