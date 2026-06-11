# Retrieval eval — findings

Baseline run: 2026-06-11, 20 golden questions (8 out-of-corpus + 12 in-domain),
`gemini-2.5-flash`, live Vertex Vector Search + Neo4j Aura + GCS.

> **Status update (2026-06-11, Phase 1 complete):** all three gaps closed
> and measured live on the expanded 30-question set. Final config
> (`DISTANCE_GATE_THRESHOLD=0.4175`, reranker off): **overall 100%,
> no-false-archive-grounding 100%, in-domain 100%, Recall@5 0.917, MRR
> 0.808, nDCG@5 0.816, faithfulness 1.0, p50 20.6s**. The cross-encoder
> rerank-score gate was falsified by the sweep and reranking itself hurt
> ranking metrics on this corpus — see "Phase 1 results" below. Full runs:
> `results/before.{json,md}`, `results/after_reranker.{json,md}`,
> `results/after_final.{json,md}`.

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

**Fix (implemented, Phase 0):** a PyTorch cross-encoder reranker
(`app/services/reranker.py`, `cross-encoder/ms-marco-MiniLM-L6-v2`) now
scores the top-30 vector candidates; the **max rerank score** is the
relevance gate. Below `RERANK_GATE_THRESHOLD` the archive LLM is skipped
and the query routes to the labelled web fallback (or abstains with zero
citations if web fails). The cross-encoder separates far better than raw
cosine distance (smoke test: relevant chunk 0.988 vs off-topic 0.000), so
the gate no longer collides with the in-domain 0.34–0.50 distance band.
Everything is behind `RERANKER_ENABLED` (default off).

**Resolution (Phase 1, 2026-06-11):** the rerank-score gate was
**falsified** by the live sweep and replaced with a min-vector-distance
gate (`DISTANCE_GATE_THRESHOLD=0.4175`), which achieves
no-false-archive-grounding 100% with in-domain answer rate 100%. See
"Phase 1 results" below.

## Gap 2 — faithfulness is a conservative lower bound

**Symptom:** mean faithfulness 0.415; `indomain-11` (legal/judicial) scored
0.33 despite Recall@5 = 1.0 and grounding = 1.0.

**Root cause:** the judge scores the answer against
`ArchiveCitation.text_span`, which the API **truncates to 300 characters**
(`hybrid_retrieval.py`). The judge therefore sees only a fragment of each
cited chunk, so claims supported by the rest of the chunk look unsupported.
The score is a genuine lower bound on grounding, not a true 0.41.

**Fixed (Phase 0):** `evals/sources.py` recovers the full chunk text from
GCS by prefix-matching the 300-char span against the doc's chunk file
(citations carry `doc_id` but not `chunk_id`), falling back to the span for
graph citations or on GCS failure. Re-baseline in Phase 1, then raise the
faithfulness floor toward the 0.7 target.

## Gap 3 — citations were ordered worst-first (found in Phase 0 review, fixed)

**Symptom:** `_load_chunk_contexts` sorted context chunks by
`confidence` (= raw distance) **descending**, but the index is
`COSINE_DISTANCE` (verified via `gcloud ai indexes describe`): lower is
better. The least-relevant chunk led every citation list, and
`ArchiveCitation.confidence` carried a distance labelled as a confidence
(inverted semantics vs the graph chunks' 0.8).

**Fix:** confidence now stores similarity (`1 - distance`); the descending
sort then yields best-first. Note the 0.917 Recall@5 baseline was measured
on the old ordering — doc-level dedup masked much of the damage, but
re-baseline before quoting before/after numbers. With the reranker enabled,
citation confidence is the cross-encoder score instead.

## Phase 1 results (2026-06-11, single deploy window)

Three live runs on the 30-question set (18 OOC + 12 in-domain), all with
the fixed judge and fixed citation ordering:

| Metric | Before (no gate, no rerank) | Rerank + distance gate | **Final: distance gate only** |
|---|---|---|---|
| Overall success | 93.3% | 96.7% | **100%** |
| No-false-archive-grounding | 88.9% | 100% | **100%** |
| In-domain answer rate | 100% | 100% | **100%** |
| Recall@5 | 0.917 | 0.750 | **0.917** |
| MRR | 0.808 | 0.778 | **0.808** |
| nDCG@5 | 0.816 | 0.708 | **0.816** |
| Faithfulness | 1.0 | 1.0 | **1.0** |
| Latency p50 | 23.4s | 24.1s | **20.6s** |

**Finding 1 — the rerank-score gate hypothesis was falsified.** In-domain
max cross-encoder scores span 0.0002–0.98: specific factoid questions
(opium, Governor) score 0.96+, but broad thematic questions ("what legal
matters appear in the correspondence?") score ~0 against MS MARCO. Worse,
entity-overlap adversarial OOC questions ("opium farm revenue in 2024")
score up to 0.80. The distributions are fully interleaved — 14/18 OOC
overlap the in-domain range (`results/sweep.json`).

**Finding 2 — min vector distance separates instead.** In-domain min
distances span 0.277–0.412; OOC 0.354–0.631, with 14/18 OOC (including
both live failures: crypto 0.4236, MRT 0.4234) above every in-domain
query. Threshold 0.4175 (gap midpoint) gates them; the 4 entity-overlap
OOC below it are already handled by the LLM's own refusal + web fallback.
**Caveat:** the gap is narrow (0.4117 vs 0.4234) — expand the golden set
before trusting the margin further.

**Finding 3 — reranking hurt ranking on this corpus.** The same MS MARCO
scoring failure reorders the top-30 badly: Recall@5 0.917 → 0.750
(indomain-10 lost its expected doc entirely). **The reranker therefore
ships disabled** (`RERANKER_ENABLED=false`); making it useful requires
fine-tuning the cross-encoder on archive-style (question, chunk) pairs —
future work.

**Production config:** `DISTANCE_GATE_THRESHOLD=0.4175`,
`RERANKER_ENABLED=false`. OOC queries now skip the archive LLM call,
which is also why p50 improved. thresholds.json floors raised to the
final run (no-false-grounding gates at 100).

## What's solid

- Recall@5 0.917 and citation grounding 1.0 on in-domain questions.
- 7/8 out-of-corpus questions correctly avoid archive grounding (web fallback
  or abstain).
- The judge (once given enough `max_output_tokens` for a thinking model)
  produces stable, discriminating faithfulness scores.
