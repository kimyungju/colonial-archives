# Vector Search index — cost operations

The biggest standing GCP cost for this project is the **Vertex AI Vector Search
deployed index**. It runs on **dedicated, always-on replicas** (currently
`minReplicaCount: 2`), billed per hour **whether or not anyone queries it** —
zero users still costs money. This is what accrued charges and led to the
2026-06 billing suspension.

When the system is not being demoed, **undeploy the index** to stop the bleed.
The index data and the endpoint stay; only the always-on serving replicas go
away. Redeploy (~20–40 min to become queryable) before a demo or an eval run.

> While undeployed, retrieval returns no archive results and
> `backend/evals/runner.py` cannot run. Redeploy first.

## Current deployment parameters (captured 2026-06-11)

| Field | Value |
|---|---|
| Project | `aihistory-488807` |
| Region | `asia-southeast1` |
| Index endpoint id | `7992877787885076480` |
| Index id | `5700013413925650432` |
| Deployed index id | `colonial_archives_deployed_1772349960200` |
| Display name | `colonial-archives-deployed` |
| Replicas | min 2 / max 2 (automaticResources) |

These match `VECTOR_SEARCH_ENDPOINT`, `VECTOR_SEARCH_INDEX_ID`, and
`VECTOR_SEARCH_DEPLOYED_INDEX_ID` in `backend/.env`.

## Stop cost — undeploy

```bash
gcloud ai index-endpoints undeploy-index 7992877787885076480 \
  --region=asia-southeast1 \
  --project=aihistory-488807 \
  --deployed-index-id=colonial_archives_deployed_1772349960200
```

Verify it is gone (deployedIndexes should be empty):

```bash
gcloud ai index-endpoints describe 7992877787885076480 \
  --region=asia-southeast1 --project=aihistory-488807 \
  --format="value(deployedIndexes)"
```

## Before a demo — redeploy

```bash
gcloud ai index-endpoints deploy-index 7992877787885076480 \
  --region=asia-southeast1 \
  --project=aihistory-488807 \
  --index=5700013413925650432 \
  --deployed-index-id=colonial_archives_deployed_1772349960200 \
  --display-name="colonial-archives-deployed" \
  --min-replica-count=2 \
  --max-replica-count=2
```

Deployment takes roughly 20–40 minutes. It is queryable once
`describe ... --format="value(deployedIndexes)"` shows the deployed index with
an `indexSyncTime`. A quick end-to-end check:

```bash
cd backend
.venv/Scripts/python -m evals.discover   # should print real CO 273 doc ids
```

## Other standing costs (smaller)

- **Neo4j Aura** — managed graph DB; has its own pricing/pause controls in the
  Aura console. The retrieval layer already degrades to a deterministic local
  path when Neo4j is unavailable (`Graph search failed` is logged, vector
  search carries the query).
- **Cloud Run** — scales to zero between requests; negligible when idle.
- **GCS** (`aihistory-co273-nus`) — storage only; cheap. Holds the OCR chunks
  and source PDFs, so do not delete it.

## Model note

`gemini-2.0-flash` was retired from Vertex AI. The backend now uses
`gemini-2.5-flash` (`backend/app/config/settings.py`,
`VERTEX_LLM_MODEL`). 2.5-flash is a thinking model, so answer/judge calls need
a larger `max_output_tokens` budget or they return empty text.
