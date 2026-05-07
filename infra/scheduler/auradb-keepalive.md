# AuraDB Keep-Alive via Cloud Scheduler

## Purpose

Neo4j AuraDB free tier auto-pauses after **3 days of inactivity**. A paused
database takes 30–60 s to wake on the next connection — long enough that
`_graph_search`'s 15 s timeout fires first and the chatbot serves a
degraded answer with no graph context.

This runbook sets up a Cloud Scheduler job that pings the backend's
`/health` endpoint on a regular cadence. The endpoint already exercises
Neo4j connectivity (`backend/app/main.py:62-69` calls
`neo4j_service.verify_connectivity()` with a 10 s timeout), so the ping
both monitors the service AND keeps AuraDB warm.

We chose this approach over an in-process keep-alive task plus
`min-instances=1 + --no-cpu-throttling` on Cloud Run because:

- No code changes (zero deploy risk).
- ~$0/month vs. ~$30–50/month for instance-based billing.
- Works even when no Cloud Run instance is currently running — the
  scheduler call itself triggers a cold-start, which wakes AuraDB
  along with it.

The trade-off: Cloud Run cold-start tail latency for real user requests
is *not* reduced. If that becomes a measured problem, revisit the
in-process keep-alive option (see `docs/plans/2026-05-07-chatbot-latency-prework.md`
Task C1+C2).

## Cadence

Ping every **6 hours** (`0 */6 * * *`). That gives a 12× safety margin
against the 3-day pause threshold and tolerates any single missed
execution. Cloud Scheduler bills per execution (~$0.10 per million),
so 4 jobs/day = ~120/month is essentially free.

Tighter cadences (every 50 min) are unnecessary unless AuraDB's pause
behavior changes.

## One-time setup

Replace the placeholders, then run from any shell with `gcloud` auth
to project `aihistory-488807`:

```bash
PROJECT_ID="aihistory-488807"
REGION="asia-southeast1"
BACKEND_SERVICE="colonial-archives-backend"

# Look up the backend's URL (or replace with the known URL).
BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.url)")

gcloud scheduler jobs create http auradb-keepalive \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --schedule="0 */6 * * *" \
    --time-zone="Asia/Singapore" \
    --uri="${BACKEND_URL}/health" \
    --http-method=GET \
    --attempt-deadline=30s \
    --description="Pings /health every 6h to keep AuraDB free tier from auto-pausing"
```

## Verification

1. List the job:

   ```bash
   gcloud scheduler jobs describe auradb-keepalive \
       --project="$PROJECT_ID" \
       --location="$REGION"
   ```

2. Force one execution and inspect the response:

   ```bash
   gcloud scheduler jobs run auradb-keepalive \
       --project="$PROJECT_ID" \
       --location="$REGION"
   ```

   Then check the backend's logs for the `/health` request and confirm
   `neo4j: "connected"` in the response payload.

3. After 6 h, check `gcloud scheduler jobs describe` again — `lastAttemptTime`
   should advance and `state` should remain `ENABLED`.

## Removal / rollback

```bash
gcloud scheduler jobs delete auradb-keepalive \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --quiet
```

Removing the job re-exposes the service to AuraDB auto-pause; the next
user query after a 3-day idle window will time out the graph branch
and serve a degraded answer. That is the pre-fix behavior.

## Related

- Plan: `docs/plans/2026-05-07-chatbot-latency-prework.md` Tasks C1, C2 (in-process alternative — not chosen)
- Health endpoint: `backend/app/main.py:62-69`
- AuraDB pause docs: https://neo4j.com/docs/aura/auradb/getting-started/connect-database/
