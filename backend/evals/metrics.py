"""Pure, offline-testable metric functions for the retrieval eval.

Kept separate from runner.py so they can be unit-tested without any live
GCP/Neo4j/Vertex dependency (see tests/test_eval_metrics.py).
"""

from __future__ import annotations

import re

FALLBACK_ANSWER = "I cannot answer this based on the available sources."
CITATION_RE = re.compile(r"\[(archive|web):(\d+)\]")


def is_abstention(answer: str) -> bool:
    """True when the answer is the archive-first abstention response."""
    return FALLBACK_ANSWER.lower() in (answer or "").lower().strip()


def citation_markers(answer: str) -> list[tuple[str, int]]:
    """Return the [archive:N] / [web:N] markers present in an answer."""
    return [(m.group(1), int(m.group(2))) for m in CITATION_RE.finditer(answer or "")]


def has_inline_citation(answer: str) -> bool:
    return bool(CITATION_RE.search(answer or ""))


def recall_at_k(expected_doc_ids: list[str], cited_doc_ids: list[str], k: int) -> float | None:
    """Fraction of expected docs that appear in the top-k cited docs.

    Returns None when there is no ground truth to score against (so the
    aggregate can skip it rather than counting it as 0).
    """
    if not expected_doc_ids:
        return None
    top = cited_doc_ids[:k]
    hits = sum(1 for d in expected_doc_ids if d in top)
    return hits / len(expected_doc_ids)


def citation_grounding_rate(markers: list[tuple[str, int]], n_archive: int, n_web: int) -> float | None:
    """Fraction of inline citation markers that point at a real returned source.

    A marker like [archive:3] is grounded iff the response actually returned a
    3rd archive citation. Catches the agent inventing citation numbers.
    """
    if not markers:
        return None
    grounded = 0
    for kind, idx in markers:
        limit = n_archive if kind == "archive" else n_web
        if 1 <= idx <= limit:
            grounded += 1
    return grounded / len(markers)


def expected_keywords_present(answer: str, keywords: list[str]) -> float | None:
    """Fraction of expected answer keywords present (case-insensitive)."""
    if not keywords:
        return None
    blob = (answer or "").lower()
    hits = sum(1 for kw in keywords if kw.lower() in blob)
    return hits / len(keywords)
