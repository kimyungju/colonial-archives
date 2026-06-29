"""Colonial Archives retrieval evaluation harness.

Runs a curated golden question set against the live hybrid-retrieval
pipeline and measures retrieval and grounding quality:

  - abstention accuracy   : out-of-archive questions must return the
                            archive-first fallback; in-archive questions
                            must NOT abstain (the core archive-first claim)
  - Recall@5              : expected source documents appear in the top-5
                            citations (scored only where ground truth exists)
  - citation grounding    : every inline [archive:N] marker points at a real
                            returned citation (no invented citation numbers)
  - faithfulness          : an LLM judge checks each answer is supported by
                            the citation text spans it returned (RAGAS-style)
  - keyword coverage      : expected answer terms appear (sanity signal)
  - latency p50/p95

Faithfulness uses Vertex Gemini as judge over ONLY the returned citation
spans, so it measures grounding in retrieved evidence, not world knowledge.

Usage:
    .venv\\Scripts\\python -m evals.runner                 # full run + report
    .venv\\Scripts\\python -m evals.runner --limit 5
    .venv\\Scripts\\python -m evals.runner --filter abstention
    .venv\\Scripts\\python -m evals.runner --check         # apply thresholds
    .venv\\Scripts\\python -m evals.runner --no-judge      # skip LLM judge
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

# Settings are loaded by pydantic-settings from backend/.env (see
# app/config/settings.py) — run this module from the backend directory.
from app.services.hybrid_retrieval import hybrid_retrieval_service
from evals import metrics
from evals.judge import judge_faithfulness
from evals.sources import full_texts_for_citations

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"
K = 5
TASK_TIMEOUT_S = 120


async def run_question(task: dict, use_judge: bool) -> dict:
    started = time.monotonic()
    error = None
    resp = None
    try:
        resp = await asyncio.wait_for(
            hybrid_retrieval_service.query(
                question=task["question"],
                filter_categories=task.get("filter_categories"),
            ),
            timeout=TASK_TIMEOUT_S,
        )
    except (Exception, asyncio.TimeoutError) as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    latency = round(time.monotonic() - started, 2)
    if error:
        return {"id": task["id"], "category": task["category"], "error": error,
                "success": False, "latency_s": latency}

    archive_cites = [c for c in resp.citations if getattr(c, "type", "") == "archive"]
    web_cites = [c for c in resp.citations if getattr(c, "type", "") == "web"]
    cited_docs = list(dict.fromkeys(c.doc_id for c in archive_cites))  # ordered unique

    answer = resp.answer
    abstained = metrics.is_abstention(answer)
    markers = metrics.citation_markers(answer)

    out_of_corpus = task["category"] == "abstention"
    archive_markers = [marker for marker in markers if marker[0] == "archive"]
    has_archive_grounding = bool(archive_cites) or bool(archive_markers)
    safe_fallback_or_abstention = resp.source_type != "archive" or abstained
    no_false_archive_grounding = (
        not has_archive_grounding and safe_fallback_or_abstention
    )

    recall = metrics.recall_at_k(task.get("expected_doc_ids", []), cited_docs, K)
    rr = metrics.mrr(task.get("expected_doc_ids", []), cited_docs)
    ndcg = metrics.ndcg_at_k(task.get("expected_doc_ids", []), cited_docs, K)
    grounding = metrics.citation_grounding_rate(markers, len(archive_cites), len(web_cites))
    keyword_cov = metrics.expected_keywords_present(answer, task.get("expected_keywords", []))

    faithfulness = None
    if use_judge and not out_of_corpus and not abstained and archive_cites:
        # Full chunk texts, not 300-char spans — see FINDINGS.md Gap 2.
        source_texts = await full_texts_for_citations(archive_cites)
        faithfulness = await judge_faithfulness(task["question"], answer, source_texts)

    # Per-task success criteria.
    if out_of_corpus:
        success = no_false_archive_grounding
        reason = ("no fabricated archive grounding" if success
                  else (
                      "presented archive grounding for out-of-corpus q "
                      f"(src={resp.source_type}, archive_cites={len(archive_cites)}, "
                      f"archive_markers={len(archive_markers)}, abstained={abstained})"
                  ))
    else:
        checks = [not abstained]
        if recall is not None:
            checks.append(recall > 0)
        if grounding is not None:
            checks.append(grounding == 1.0)
        if faithfulness is not None:
            checks.append(faithfulness >= 0.5)
        success = all(checks)
        reason = (
            "answered, grounded, faithful" if success
            else f"abstained={abstained} recall={recall} grounding={grounding} faith={faithfulness}"
        )

    return {
        "id": task["id"],
        "category": task["category"],
        "success": success,
        "reason": reason,
        "source_type": resp.source_type,
        "abstained": abstained,
        "no_false_archive_grounding": no_false_archive_grounding if out_of_corpus else None,
        "cited_docs": cited_docs,
        "expected_doc_ids": task.get("expected_doc_ids", []),
        "recall_at_5": recall,
        "mrr": rr,
        "ndcg_at_5": ndcg,
        "citation_grounding": grounding,
        "keyword_coverage": keyword_cov,
        "faithfulness": faithfulness,
        "n_archive_citations": len(archive_cites),
        "latency_s": latency,
        "answer_preview": answer[:200],
        "error": None,
    }


def _mean(values):
    vals = [v for v in values if v is not None]
    return round(statistics.mean(vals), 3) if vals else None


def aggregate(results: list[dict]) -> dict:
    n = len(results)
    ok = [r for r in results if not r.get("error")]
    in_domain = [r for r in ok if r["category"] != "abstention"]
    out_corpus = [r for r in ok if r["category"] == "abstention"]
    latencies = sorted(r["latency_s"] for r in results)
    p95_idx = max(0, int(round(0.95 * n)) - 1)

    def rate(subset):
        return round(100 * sum(r["success"] for r in subset) / len(subset), 1) if subset else None

    return {
        "questions": n,
        "errors": sum(1 for r in results if r.get("error")),
        "overall_success_rate": rate(ok),
        "no_false_archive_grounding_rate": round(
            100 * sum(bool(r.get("no_false_archive_grounding")) for r in out_corpus) / len(out_corpus), 1
        ) if out_corpus else None,
        "in_domain_answer_rate": round(
            100 * sum(not r["abstained"] for r in in_domain) / len(in_domain), 1
        ) if in_domain else None,
        "mean_recall_at_5": _mean([r.get("recall_at_5") for r in in_domain]),
        "mean_mrr": _mean([r.get("mrr") for r in in_domain]),
        "mean_ndcg_at_5": _mean([r.get("ndcg_at_5") for r in in_domain]),
        "mean_citation_grounding": _mean([r.get("citation_grounding") for r in in_domain]),
        "mean_faithfulness": _mean([r.get("faithfulness") for r in in_domain]),
        "mean_keyword_coverage": _mean([r.get("keyword_coverage") for r in in_domain]),
        "out_of_corpus_questions": len(out_corpus),
        "in_domain_questions": len(in_domain),
        "latency_p50_s": latencies[n // 2] if n else None,
        "latency_p95_s": latencies[p95_idx] if n else None,
    }


def write_report(results, summary, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    lines = ["# Colonial Archives Retrieval Eval", "", "## Summary", "",
             "| Metric | Value |", "|---|---|"]
    for k, v in summary.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Per-question", "",
              "| ID | Cat | Success | Recall@5 | MRR | nDCG@5 | Grounding | Faith | Latency | Note |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        mark = "PASS" if r.get("success") else "FAIL"
        lines.append(
            f"| {r['id']} | {r['category']} | {mark} | {r.get('recall_at_5')} | "
            f"{r.get('mrr')} | {r.get('ndcg_at_5')} | "
            f"{r.get('citation_grounding')} | {r.get('faithfulness')} | "
            f"{r.get('latency_s')}s | {r.get('reason', r.get('error', ''))} |")
    (out_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_thresholds(summary: dict) -> list[str]:
    thr = json.loads((EVALS_DIR / "thresholds.json").read_text(encoding="utf-8"))
    failures = []
    for metric, bound in thr["min"].items():
        value = summary.get(metric)
        if value is None or value < bound:
            failures.append(f"{metric}: {value} < required {bound}")
    for metric, bound in thr["max"].items():
        value = summary.get(metric)
        if value is not None and value > bound:
            failures.append(f"{metric}: {value} > allowed {bound}")
    return failures


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--filter", type=str, default=None)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()

    tasks = json.loads((EVALS_DIR / "golden_questions.json").read_text(encoding="utf-8"))["questions"]
    if args.filter:
        tasks = [t for t in tasks if t["category"] == args.filter]
    if args.limit:
        tasks = tasks[: args.limit]

    use_judge = not args.no_judge
    sem = asyncio.Semaphore(args.concurrency)

    async def bounded(task):
        async with sem:
            r = await run_question(task, use_judge)
            mark = "PASS" if r.get("success") else "FAIL"
            print(f"[{mark}] {task['id']:16s} {r.get('latency_s'):6}s {r.get('reason', r.get('error'))}")
            return r

    print(f"Running {len(tasks)} golden questions (judge={'on' if use_judge else 'off'})...\n")
    results = await asyncio.gather(*(bounded(t) for t in tasks))
    results = sorted(results, key=lambda r: r["id"])

    summary = aggregate(results)
    write_report(results, summary, RESULTS_DIR)

    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nReport: {RESULTS_DIR / 'latest.md'}")

    if args.check:
        failures = check_thresholds(summary)
        if failures:
            print("\nTHRESHOLD FAILURES:")
            for f in failures:
                print(f"  - {f}")
            sys.exit(1)
        print("\nAll thresholds met.")


if __name__ == "__main__":
    asyncio.run(main())
