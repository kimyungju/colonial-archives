#!/usr/bin/env bash
# One-shot helper: re-run entity extraction (steps 7-9) for every doc_id whose
# chunks are present in GCS. Used after AuraDB instance migration to repopulate
# the empty graph without paying for OCR + embedding again.
#
# Usage: bash retry_entities_all.sh [BASE_URL]
#   BASE_URL defaults to http://localhost:8090
set -u

BASE_URL="${1:-http://localhost:8090}"
LOG_FILE="${RETRY_LOG:-/tmp/retry_entities.log}"

doc_ids=(
  "CO 273:534:11a"
  "CO 273:534:11b"
  "CO 273:534:13"
  "CO 273:534:15a"
  "CO 273:534:15b"
  "CO 273:534:2"
  "CO 273:534:24"
  "CO 273:534:3"
  "CO 273:534:5"
  "CO 273:534:6"
  "CO 273:534:7"
  "CO 273:534:9"
  "CO 273:550:1"
  "CO 273:550:10"
  "CO 273:550:11"
  "CO 273:550:13"
  "CO 273:550:14"
  "CO 273:550:18"
  "CO 273:550:19"
  "CO 273:550:21"
  "CO 273:550:3"
  "CO 273:550:5"
  "CO 273:550:8"
  "CO 273:579:1"
  "CO 273:579:2a"
  "CO 273:579:2b"
  "CO 273:579:3"
  "CO 273:579:4"
  "Huff Economic Growth"
  "Trocki Opium"
)

total=${#doc_ids[@]}
ok=0
fail=0

: > "$LOG_FILE"
echo "[$(date -Is)] Starting /retry_entities run against $BASE_URL ($total docs)" | tee -a "$LOG_FILE"

for i in "${!doc_ids[@]}"; do
  doc_id="${doc_ids[$i]}"
  idx=$((i + 1))
  body=$(printf '{"doc_id":"%s"}' "$doc_id")
  start=$(date +%s)
  resp=$(curl -sS --max-time 1800 -w '\n__HTTP__:%{http_code}' \
              -H 'Content-Type: application/json' \
              -X POST -d "$body" "$BASE_URL/retry_entities" 2>&1)
  end=$(date +%s)
  http=$(printf '%s' "$resp" | sed -n 's/^__HTTP__://p' | tail -n1)
  body_resp=$(printf '%s' "$resp" | sed '$d')
  elapsed=$((end - start))
  if [ "$http" = "200" ]; then
    ok=$((ok + 1))
    echo "[$(date -Is)] [$idx/$total] OK  (${elapsed}s) $doc_id -> $body_resp" | tee -a "$LOG_FILE"
  else
    fail=$((fail + 1))
    echo "[$(date -Is)] [$idx/$total] FAIL http=$http (${elapsed}s) $doc_id -> $body_resp" | tee -a "$LOG_FILE"
  fi
done

echo "[$(date -Is)] DONE ok=$ok fail=$fail total=$total" | tee -a "$LOG_FILE"
