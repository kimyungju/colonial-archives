# Colonial Archives Retrieval Eval

## Summary

| Metric | Value |
|---|---|
| questions | 30 |
| errors | 0 |
| overall_success_rate | 100.0 |
| no_false_archive_grounding_rate | 100.0 |
| in_domain_answer_rate | 100.0 |
| mean_recall_at_5 | 0.917 |
| mean_mrr | 0.808 |
| mean_ndcg_at_5 | 0.816 |
| mean_citation_grounding | 1.0 |
| mean_faithfulness | 1.0 |
| mean_keyword_coverage | 1.0 |
| out_of_corpus_questions | 18 |
| in_domain_questions | 12 |
| latency_p50_s | 20.61 |
| latency_p95_s | 32.77 |

## Per-question

| ID | Cat | Success | Recall@5 | MRR | nDCG@5 | Grounding | Faith | Latency | Note |
|---|---|---|---|---|---|---|---|---|---|
| abstain-01 | abstention | PASS | None | None | None | None | None | 12.25s | no fabricated archive grounding |
| abstain-02 | abstention | PASS | None | None | None | 1.0 | None | 10.81s | no fabricated archive grounding |
| abstain-03 | abstention | PASS | None | None | None | 1.0 | None | 23.73s | no fabricated archive grounding |
| abstain-04 | abstention | PASS | None | None | None | 1.0 | None | 25.31s | no fabricated archive grounding |
| abstain-05 | abstention | PASS | None | None | None | 1.0 | None | 11.48s | no fabricated archive grounding |
| abstain-06 | abstention | PASS | None | None | None | 1.0 | None | 19.2s | no fabricated archive grounding |
| abstain-07 | abstention | PASS | None | None | None | 1.0 | None | 28.69s | no fabricated archive grounding |
| abstain-08 | abstention | PASS | None | None | None | None | None | 19.09s | no fabricated archive grounding |
| abstain-09 | abstention | PASS | None | None | None | None | None | 15.69s | no fabricated archive grounding |
| abstain-10 | abstention | PASS | None | None | None | 1.0 | None | 24.78s | no fabricated archive grounding |
| abstain-11 | abstention | PASS | None | None | None | 1.0 | None | 21.17s | no fabricated archive grounding |
| abstain-12 | abstention | PASS | None | None | None | 1.0 | None | 20.05s | no fabricated archive grounding |
| abstain-13 | abstention | PASS | None | None | None | 1.0 | None | 21.61s | no fabricated archive grounding |
| abstain-14 | abstention | PASS | None | None | None | None | None | 11.94s | no fabricated archive grounding |
| abstain-15 | abstention | PASS | None | None | None | None | None | 14.97s | no fabricated archive grounding |
| abstain-16 | abstention | PASS | None | None | None | None | None | 14.27s | no fabricated archive grounding |
| abstain-17 | abstention | PASS | None | None | None | 1.0 | None | 20.58s | no fabricated archive grounding |
| abstain-18 | abstention | PASS | None | None | None | 1.0 | None | 8.28s | no fabricated archive grounding |
| indomain-01 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 20.78s | answered, grounded, faithful |
| indomain-02 | economic | PASS | 1.0 | 0.5 | 0.6934264036172708 | 1.0 | 1.0 | 24.83s | answered, grounded, faithful |
| indomain-03 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 37.34s | answered, grounded, faithful |
| indomain-04 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 24.67s | answered, grounded, faithful |
| indomain-05 | governance | PASS | 1.0 | 0.5 | 0.6309297535714575 | 1.0 | None | 18.77s | answered, grounded, faithful |
| indomain-06 | social | PASS | 1.0 | 1.0 | 0.9197207891481876 | 1.0 | 1.0 | 30.25s | answered, grounded, faithful |
| indomain-07 | defence | PASS | 0.5 | 1.0 | 0.6131471927654584 | 1.0 | 1.0 | 49.83s | answered, grounded, faithful |
| indomain-08 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 19.2s | answered, grounded, faithful |
| indomain-09 | governance | PASS | 0.5 | 0.2 | 0.23719771276929622 | 1.0 | None | 15.19s | answered, grounded, faithful |
| indomain-10 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 20.61s | answered, grounded, faithful |
| indomain-11 | governance | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 30.34s | answered, grounded, faithful |
| indomain-12 | economic | PASS | 1.0 | 0.5 | 0.6934264036172708 | 1.0 | 1.0 | 32.77s | answered, grounded, faithful |
