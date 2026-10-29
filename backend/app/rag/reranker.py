"""Reranking stage: deterministic local fusion of dense + lexical ranks.

Uses reciprocal-rank fusion plus a term-overlap bonus. A local model-based
reranker can replace this later; the interface stays the same.
"""
from __future__ import annotations

import re

from .retriever import RetrievedChunk

_RRF_K = 60  # standard RRF constant


def _rrf(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / (_RRF_K + rank + 1)


def _overlap_score(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = set(re.findall(r"\w+", text.lower()))
    return len(query_terms & text_terms) / len(query_terms)


def rerank(chunks: list[RetrievedChunk], query: str,
           lexical_weight: float, top_n: int) -> list[tuple[RetrievedChunk, float]]:
    query_terms = set(re.findall(r"\w+", query.lower()))
    dense_weight = 1.0 - lexical_weight
    scored: list[tuple[RetrievedChunk, float]] = []
    for c in chunks:
        score = (dense_weight * _rrf(c.dense_rank)
                 + lexical_weight * _rrf(c.lexical_rank)
                 + 0.5 * _overlap_score(query_terms, c.text))
        scored.append((c, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_n]
