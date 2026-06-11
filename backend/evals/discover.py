"""Discovery pass for grounding the retrieval golden set.

Runs a list of broad in-domain seed questions against the live hybrid
retrieval pipeline and records which archive documents/pages each one
surfaces. The output (results/discovery.json) is used to hand-curate
golden_questions.json with real expected_doc_ids — so Recall@k is measured
against documents we have confirmed actually contain the answer, not guesses.

Usage:
    .venv\\Scripts\\python -m evals.discover
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.services.hybrid_retrieval import hybrid_retrieval_service  # noqa: E402

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"

SEED_QUESTIONS = [
    "What commodities were traded in the Straits Settlements?",
    "Describe the colonial revenue and financial accounts.",
    "What was the role of the Governor in the Straits Settlements?",
    "What does the archive say about tin mining or tin trade?",
    "What correspondence concerns Chinese immigration or labour?",
    "What military or defence matters are recorded?",
    "What does the archive say about opium revenue or the opium farm?",
    "What infrastructure or public works are mentioned?",
    "What trade or shipping with neighbouring territories is recorded?",
    "What administrative or establishment matters are discussed?",
    "What is recorded about land, plantations, or agriculture?",
    "What legal or judicial matters appear in the correspondence?",
]


async def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for q in SEED_QUESTIONS:
        try:
            resp = await hybrid_retrieval_service.query(question=q)
            archive_cites = [c for c in resp.citations if getattr(c, "type", "") == "archive"]
            out.append({
                "question": q,
                "source_type": resp.source_type,
                "answer_preview": resp.answer[:200],
                "doc_ids": sorted({c.doc_id for c in archive_cites}),
                "citations": [
                    {"doc_id": c.doc_id, "pages": c.pages,
                     "confidence": round(c.confidence, 3),
                     "text_span": c.text_span[:160]}
                    for c in archive_cites
                ],
            })
            print(f"[ok] {q[:55]:55s} -> {sorted({c.doc_id for c in archive_cites})}")
        except Exception as exc:  # noqa: BLE001
            out.append({"question": q, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[ERR] {q[:55]:55s} -> {type(exc).__name__}: {exc}")

    (RESULTS_DIR / "discovery.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {RESULTS_DIR / 'discovery.json'}")


if __name__ == "__main__":
    asyncio.run(main())
