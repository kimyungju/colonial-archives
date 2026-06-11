"""Relevance-gate threshold sweep over dumped retrieval candidates.

Pure logic (suggest_threshold) is unit-tested offline; the CLI scores the
dumped candidates with the real cross-encoder and prints/writes the
suggested RERANK_GATE_THRESHOLD.

The hard constraint is the archive-first guarantee: the in-domain answer
rate must stay 100%, so the threshold can never exceed the lowest
in-domain max-score. Within that constraint we reject as many
out-of-corpus questions as possible and report any OOC questions whose
score overlaps the in-domain range (those cannot be gated by score alone).

Usage (after evals/dump_candidates.py has produced results/candidates.json):
    .venv\\Scripts\\python -m evals.sweep
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"


def suggest_threshold(
    in_domain_max_scores: list[float],
    ooc_max_scores: list[float],
) -> dict:
    """Pick a gate threshold from labelled max-score distributions.

    Returns a dict with the threshold, the OOC rejection rate it achieves,
    the count of OOC questions that overlap the in-domain range, and the
    distribution edges used to pick it.
    """
    if not in_domain_max_scores:
        raise ValueError("need at least one in-domain max score")

    floor = min(in_domain_max_scores)  # hard constraint: keep all in-domain
    rejectable = [s for s in ooc_max_scores if s < floor]
    overlapping = [s for s in ooc_max_scores if s >= floor]

    lo = max(rejectable) if rejectable else 0.0
    threshold = (lo + floor) / 2.0

    return {
        "threshold": threshold,
        "ooc_rejected_rate": (
            len(rejectable) / len(ooc_max_scores) if ooc_max_scores else None
        ),
        "overlapping_ooc": len(overlapping),
        "in_domain_min": floor,
        "ooc_max": max(ooc_max_scores) if ooc_max_scores else None,
    }


async def main() -> None:
    from app.services.reranker import reranker_service

    candidates = json.loads(
        (RESULTS_DIR / "candidates.json").read_text(encoding="utf-8")
    )

    in_domain: list[float] = []
    ooc: list[float] = []
    per_question = []

    for entry in candidates:
        texts = [c["text"] for c in entry["candidates"] if c.get("text")]
        if texts:
            scores = await reranker_service.score(entry["question"], texts)
            max_score = max(scores)
        else:
            max_score = 0.0
        per_question.append(
            {"id": entry["id"], "category": entry["category"], "max_score": round(max_score, 4)}
        )
        if entry["category"] == "abstention":
            ooc.append(max_score)
        else:
            in_domain.append(max_score)
        print(f"{entry['id']:16s} {entry['category']:12s} max={max_score:.4f}")

    result = suggest_threshold(in_domain, ooc)
    print("\n=== Sweep result ===")
    for k, v in result.items():
        print(f"  {k}: {v}")

    (RESULTS_DIR / "sweep.json").write_text(
        json.dumps({"summary": result, "per_question": per_question}, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {RESULTS_DIR / 'sweep.json'}")
    print("Set RERANK_GATE_THRESHOLD to the suggested threshold in backend/.env")


if __name__ == "__main__":
    asyncio.run(main())
