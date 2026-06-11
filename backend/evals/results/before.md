# Colonial Archives Retrieval Eval

## Summary

| Metric | Value |
|---|---|
| questions | 30 |
| errors | 0 |
| overall_success_rate | 93.3 |
| no_false_archive_grounding_rate | 88.9 |
| in_domain_answer_rate | 100.0 |
| mean_recall_at_5 | 0.917 |
| mean_mrr | 0.808 |
| mean_ndcg_at_5 | 0.816 |
| mean_citation_grounding | 1.0 |
| mean_faithfulness | 1.0 |
| mean_keyword_coverage | 1.0 |
| out_of_corpus_questions | 18 |
| in_domain_questions | 12 |
| latency_p50_s | 23.42 |
| latency_p95_s | 29.23 |

## Per-question

| ID | Cat | Success | Recall@5 | MRR | nDCG@5 | Grounding | Faith | Latency | Note |
|---|---|---|---|---|---|---|---|---|---|
| abstain-01 | abstention | PASS | None | None | None | 1.0 | None | 19.0s | no fabricated archive grounding |
| abstain-02 | abstention | PASS | None | None | None | 1.0 | None | 13.58s | no fabricated archive grounding |
| abstain-03 | abstention | PASS | None | None | None | 1.0 | None | 16.23s | no fabricated archive grounding |
| abstain-04 | abstention | PASS | None | None | None | 1.0 | None | 29.23s | no fabricated archive grounding |
| abstain-05 | abstention | PASS | None | None | None | 1.0 | None | 22.33s | no fabricated archive grounding |
| abstain-06 | abstention | PASS | None | None | None | 1.0 | None | 25.92s | no fabricated archive grounding |
| abstain-07 | abstention | PASS | None | None | None | 1.0 | None | 23.05s | no fabricated archive grounding |
| abstain-08 | abstention | PASS | None | None | None | None | None | 35.55s | no fabricated archive grounding |
| abstain-09 | abstention | FAIL | None | None | None | None | None | 20.36s | presented archive grounding for out-of-corpus q (src=archive, archive_cites=10) |
| abstain-10 | abstention | PASS | None | None | None | 1.0 | None | 27.47s | no fabricated archive grounding |
| abstain-11 | abstention | PASS | None | None | None | 1.0 | None | 17.22s | no fabricated archive grounding |
| abstain-12 | abstention | PASS | None | None | None | None | None | 28.64s | no fabricated archive grounding |
| abstain-13 | abstention | FAIL | None | None | None | 1.0 | None | 17.89s | presented archive grounding for out-of-corpus q (src=archive, archive_cites=10) |
| abstain-14 | abstention | PASS | None | None | None | None | None | 17.92s | no fabricated archive grounding |
| abstain-15 | abstention | PASS | None | None | None | 1.0 | None | 28.8s | no fabricated archive grounding |
| abstain-16 | abstention | PASS | None | None | None | None | None | 8.62s | no fabricated archive grounding |
| abstain-17 | abstention | PASS | None | None | None | 1.0 | None | 26.19s | no fabricated archive grounding |
| abstain-18 | abstention | PASS | None | None | None | 1.0 | None | 23.42s | no fabricated archive grounding |
| indomain-01 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 21.44s | answered, grounded, faithful |
| indomain-02 | economic | PASS | 1.0 | 0.5 | 0.6934264036172708 | 1.0 | 1.0 | 17.44s | answered, grounded, faithful |
| indomain-03 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 24.34s | answered, grounded, faithful |
| indomain-04 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 26.61s | answered, grounded, faithful |
| indomain-05 | governance | PASS | 1.0 | 0.5 | 0.6309297535714575 | 1.0 | None | 16.28s | answered, grounded, faithful |
| indomain-06 | social | PASS | 1.0 | 1.0 | 0.9197207891481876 | 1.0 | 1.0 | 87.84s | answered, grounded, faithful |
| indomain-07 | defence | PASS | 0.5 | 1.0 | 0.6131471927654584 | 1.0 | None | 14.88s | answered, grounded, faithful |
| indomain-08 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 27.94s | answered, grounded, faithful |
| indomain-09 | governance | PASS | 0.5 | 0.2 | 0.23719771276929622 | 1.0 | None | 18.0s | answered, grounded, faithful |
| indomain-10 | economic | PASS | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 29.17s | answered, grounded, faithful |
| indomain-11 | governance | PASS | 1.0 | 1.0 | 1.0 | 1.0 | None | 24.47s | answered, grounded, faithful |
| indomain-12 | economic | PASS | 1.0 | 0.5 | 0.6934264036172708 | 1.0 | 1.0 | 25.05s | answered, grounded, faithful |
