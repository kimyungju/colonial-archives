# Colonial Archives Retrieval Eval

## Summary

| Metric | Value |
|---|---|
| questions | 20 |
| errors | 0 |
| overall_success_rate | 90.0 |
| no_false_archive_grounding_rate | 87.5 |
| in_domain_answer_rate | 100.0 |
| mean_recall_at_5 | 0.917 |
| mean_citation_grounding | 1.0 |
| mean_faithfulness | 0.415 |
| mean_keyword_coverage | 1.0 |
| out_of_corpus_questions | 8 |
| in_domain_questions | 12 |
| latency_p50_s | 26.39 |
| latency_p95_s | 33.11 |

## Per-question

| ID | Cat | Success | Recall@5 | Grounding | Faith | Latency | Note |
|---|---|---|---|---|---|---|---|
| abstain-01 | abstention | FAIL | None | None | None | 20.67s | presented archive grounding for out-of-corpus q (src=archive, archive_cites=10) |
| abstain-02 | abstention | PASS | None | 1.0 | None | 20.08s | no fabricated archive grounding |
| abstain-03 | abstention | PASS | None | 1.0 | None | 29.16s | no fabricated archive grounding |
| abstain-04 | abstention | PASS | None | 1.0 | None | 29.41s | no fabricated archive grounding |
| abstain-05 | abstention | PASS | None | 1.0 | None | 20.76s | no fabricated archive grounding |
| abstain-06 | abstention | PASS | None | 1.0 | None | 16.05s | no fabricated archive grounding |
| abstain-07 | abstention | PASS | None | 1.0 | None | 16.64s | no fabricated archive grounding |
| abstain-08 | abstention | PASS | None | None | None | 26.39s | no fabricated archive grounding |
| indomain-01 | economic | PASS | 1.0 | 1.0 | None | 23.36s | answered, grounded, faithful |
| indomain-02 | economic | PASS | 1.0 | 1.0 | None | 21.81s | answered, grounded, faithful |
| indomain-03 | economic | PASS | 1.0 | None | None | 30.7s | answered, grounded, faithful |
| indomain-04 | economic | PASS | 1.0 | 1.0 | None | 29.0s | answered, grounded, faithful |
| indomain-05 | governance | PASS | 1.0 | 1.0 | None | 18.34s | answered, grounded, faithful |
| indomain-06 | social | PASS | 1.0 | 1.0 | 0.5 | 14.61s | answered, grounded, faithful |
| indomain-07 | defence | PASS | 0.5 | 1.0 | None | 19.2s | answered, grounded, faithful |
| indomain-08 | economic | PASS | 1.0 | 1.0 | None | 29.78s | answered, grounded, faithful |
| indomain-09 | governance | PASS | 0.5 | 1.0 | None | 32.7s | answered, grounded, faithful |
| indomain-10 | economic | PASS | 1.0 | 1.0 | None | 33.11s | answered, grounded, faithful |
| indomain-11 | governance | FAIL | 1.0 | 1.0 | 0.33 | 38.22s | abstained=False recall=1.0 grounding=1.0 faith=0.33 |
| indomain-12 | economic | PASS | 1.0 | 1.0 | None | 26.95s | answered, grounded, faithful |
