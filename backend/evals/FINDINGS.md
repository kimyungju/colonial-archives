# Retrieval eval — findings

Baseline run: 2026-06-11, 20 golden questions (8 out-of-corpus + 12 in-domain),
`gemini-2.5-flash`, live Vertex Vector Search + Neo4j Aura + GCS.

## Headline numbers

| Metric | Result | Notes |
|---|---|---|
| Overall success rate | 90.0% (18/20) | |
| In-domain answer rate | 100% (12/12) | every in-corpus question answered, not abstained |
| Mean Recall@5 | 0.917 | expected source docs appear in top-5 citations |
| Mean citation grounding | 1.0 | every inline [archive:N] points at a real returned citation |
| Mean keyword coverage | 1.0 | |
| No-false-archive-grounding | 87.5% (7/8) | **target 100% — see Gap 1** |
| Mean faithfulness | 0.415 | conservative lower bound — **see Gap 2** |
| Latency p50 / p95 | 26.4s / 33.1s | hybrid retrieval + 2 sequential Gemini calls |

The core retrieval quality is strong: in-corpus questions are answered with
high recall and fully-grounded citations. The two gaps below are real and
tracked; the eval exists precisely to surface them.

## Gap 1 — archive grounding fabricated for an out-of-corpus question

**Symptom:** `abstain-01` ("What is the capital of France?") returned
`source_type=archive` with **10 archive citations** instead of falling back to
web / abstaining.

**Root cause:** `app/config/settings.py` defines `RELEVANCE_THRESHOLD = 0.7`,
but `hybrid_retrieval.query()` computes `relevance_score` only to **log** it
(step 6) — it is never used as a gate. Vector search always returns its top-k
nearest chunks regardless of how weak the match is, and the archive LLM then
answers from them. Web fallback only triggers when the archive LLM itself
emits the exact fallback string, which it did not here.

**Why not a one-line fix:** in-corpus chunks in this corpus sit at cosine
distances ~0.34–0.50, i.e. `vector_score` ~0.50–0.66 — already **below** the
0.7 constant. Turning the existing threshold on as-is would reject good
in-domain answers and tank the 100% in-domain answer rate. The fix is a
**corpus-tuned relevance gate**: log `relevance_score` for a labelled
in-domain vs out-of-corpus set, pick a separating threshold (likely ~0.55),
and route below-threshold queries to web fallback instead of archive.

**Next step:** threshold sweep over the golden set, then apply the gate in
step 6/7 of `hybrid_retrieval.query()` and re-baseline.

## Gap 2 — faithfulness is a conservative lower bound

**Symptom:** mean faithfulness 0.415; `indomain-11` (legal/judicial) scored
0.33 despite Recall@5 = 1.0 and grounding = 1.0.

**Root cause:** the judge scores the answer against
`ArchiveCitation.text_span`, which the API **truncates to 300 characters**
(`hybrid_retrieval.py`). The judge therefore sees only a fragment of each
cited chunk, so claims supported by the rest of the chunk look unsupported.
The score is a genuine lower bound on grounding, not a true 0.41.

**Next step:** have the runner fetch full chunk text from GCS by
`doc_id`/`chunk_id` for the judge (more GCS reads), or widen `text_span`. Then
re-baseline and raise the faithfulness floor toward the 0.7 target.

## What's solid

- Recall@5 0.917 and citation grounding 1.0 on in-domain questions.
- 7/8 out-of-corpus questions correctly avoid archive grounding (web fallback
  or abstain).
- The judge (once given enough `max_output_tokens` for a thinking model)
  produces stable, discriminating faithfulness scores.
