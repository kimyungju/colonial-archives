# Colonial Archives Retrieval Eval

## Summary

| Metric | Value |
|---|---|
| questions | 30 |
| errors | 0 |
| overall_success_rate | 96.7 |
| no_false_archive_grounding_rate | 100.0 |
| in_domain_answer_rate | 100.0 |
| mean_recall_at_5 | 0.75 |
| mean_mrr | 0.778 |
| mean_ndcg_at_5 | 0.708 |
| mean_citation_grounding | 1.0 |
| mean_faithfulness | 1.0 |
| mean_keyword_coverage | 1.0 |
| out_of_corpus_questions | 18 |
| in_domain_questions | 12 |
| latency_p50_s | 24.11 |
| latency_p95_s | 30.06 |

## Per-question

| ID | Cat | Success | Recall@5 | MRR | nDCG@5 | Grounding | Faith | Latency | Note |
|---|---|---|---|---|---|---|---|---|---|
| abstain-01 | abstention | PASS | None | None | None | None | None | 27.38s | no fabricated archive grounding |
| abstain-02 | abstention | PASS | None | None | None | 1.0 | None | 29.7s | no fabricated archive grounding |
| abstain-03 | abstention | PASS | None | None | None | 1.0 | None | 29.09s | no fabricated archive grounding |
| abstain-04 | abstention | PASS | None | None | None | 1.0 | None | 28.25s | no fabricated archive grounding |
| abstain-05 | abstention | PASS | None | None | None | 1.0 | None | 15.25s | no fabricated archive grounding |
| abstain-06 | abstention | PASS | None | None | None | 1.0 | None | 29.84s | no fabricated archive grounding |
| abstain-07 | abstention | PASS | None | None | None | 1.0 | None | 11.09s | no fabricated archive grounding |
| abstain-08 | abstention | PASS | None | None | None | None | None | 38.45s | no fabricated archive grounding |
| abstain-09 | abstention | PASS | None | None | None | None | None | 23.78s | no fabricated archive grounding |
| abstain-10 | abstention | PASS | None | None | None | 1.0 | None | 24.11s | no fabricated archive grounding |
| abstain-11 | abstention | PASS | None | None | None | 1.0 | None | 26.05s | no fabricated archive grounding |
| abstain-12 | abstention | PASS | None | None | None | None | None | 16.53s | no fabricated archive grounding |
| abstain-13 | abstention | PASS | None | None | None | 1.0 | None | 21.97s | no fabricated archive grounding |
| abstain-14 | abstention | PASS | None | None | None | 1.0 | None | 16.17s | no fabricated archive grounding |
| abstain-15 | abstention | PASS | None | None | None | 1.0 | None | 12.91s | no fabricated archive grounding |
| abstain-16 | abstention | PASS | None | None | None | None | None | 5.44s | no fabricated archive grounding |
| abstain-17 | abstention | PASS | None | None | None | 1.0 | None | 24.69s | no fabricated archive grounding |
| abstain-18 | abstention | PASS | None | None | None | 1.0 | None | 16.86s | no fabricated archive grounding |
| indomain-01 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 10.8s | answered, grounded, faithful |
| indomain-02 | economic | PASS | 0.5 | 0.5 | 0.38685280723454163 | 1.0 | 1.0 | 23.45s | answered, grounded, faithful |
| indomain-03 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 25.41s | answered, grounded, faithful |
| indomain-04 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 25.89s | answered, grounded, faithful |
| indomain-05 | governance | PASS | 1.0 | 0.3333333333333333 | 0.5 | 1.0 | None | 18.03s | answered, grounded, faithful |
| indomain-06 | social | PASS | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 14.61s | answered, grounded, faithful |
| indomain-07 | defence | PASS | 0.5 | 1.0 | 0.6131471927654584 | 1.0 | None | 18.02s | answered, grounded, faithful |
| indomain-08 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 30.06s | answered, grounded, faithful |
| indomain-09 | governance | PASS | 0.5 | 1.0 | 0.6131471927654584 | 1.0 | 1.0 | 25.38s | answered, grounded, faithful |
| indomain-10 | economic | FAIL | 0.0 | 0.0 | 0.0 | 1.0 | None | 52.83s | abstained=False recall=0.0 grounding=1.0 faith=None |
| indomain-11 | governance | PASS | 0.5 | 0.5 | 0.38685280723454163 | 1.0 | None | 29.8s | answered, grounded, faithful |
| indomain-12 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 22.12s | answered, grounded, faithful |
