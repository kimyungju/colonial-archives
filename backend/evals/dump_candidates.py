"""Dump per-question vector-search candidates for offline experiments.

Run ONCE while the Vector Search index is deployed. Writes
results/candidates.json with the full top-RERANK_CANDIDATES pool (chunk id,
cosine distance, full chunk text) for every golden question, so that the
threshold sweep (evals/sweep.py) and any rerank metric experiments can run
entirely offline afterwards — no redeployed index, no further cost.

Usage:
    .venv\\Scripts\\python -m evals.dump_candidates
"""

import asyncio
import json
from pathlib import Path

from app.config.settings import settings
from app.services.embeddings import embeddings_service
from app.services.hybrid_retrieval import hybrid_retrieval_service
from app.services.vector_search import vector_search_service

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"


async def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(
        (EVALS_DIR / "golden_questions.json").read_text(encoding="utf-8")
    )["questions"]

    out = []
    for task in tasks:
        question = task["question"]
        try:
            embedding = await embeddings_service.embed_query(question)
            vector_results = await vector_search_service.search(
                embedding, top_k=settings.RERANK_CANDIDATES
            )
            contexts = await hybrid_retrieval_service._load_chunk_contexts(
                vector_results
            )
            distance_by_id = {r["id"]: r["distance"] for r in vector_results}
            out.append({
                "id": task["id"],
                "category": task["category"],
                "question": question,
                "candidates": [
                    {
                        "id": c["id"],
                        "doc_id": c["doc_id"],
                        "distance": distance_by_id.get(c["id"]),
                        "text": c["text"],
                    }
                    for c in contexts
                ],
            })
            print(f"[ok] {task['id']:16s} {len(contexts)} candidates")
        except Exception as exc:  # noqa: BLE001
            out.append({"id": task["id"], "category": task["category"],
                        "question": question, "error": f"{type(exc).__name__}: {exc}",
                        "candidates": []})
            print(f"[ERR] {task['id']:16s} {type(exc).__name__}: {exc}")

    (RESULTS_DIR / "candidates.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {RESULTS_DIR / 'candidates.json'}")


if __name__ == "__main__":
    asyncio.run(main())
