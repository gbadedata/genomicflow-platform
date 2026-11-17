#!/usr/bin/env bash
# End-to-end check of the v0.2 failure handling on a deployed project.
#
#   GCP_PROJECT_ID=your-project bash scripts/verify_gcp.sh
#
# Publishes four kinds of message, runs the pipeline in rounds, and reports
# where each one ended up:
#
#   5 simulator runs           -> sequencing_runs (no duplicates)
#   1 run_id without "RUN-"    -> rejected_records, VALIDATION
#   1 payload that is not JSON -> rejected_records, UNPARSEABLE
#   1 run BigQuery cannot store (total_bases = "lots")
#                              -> retried, then genomic-events-dead-letter-sub
#
# Costs a few pence at most. Output is also saved to docs/evidence/.
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
[ -n "$PROJECT_ID" ] || { echo "Set GCP_PROJECT_ID first."; exit 1; }
export GCP_PROJECT_ID="$PROJECT_ID"

TOPIC=genomic-events
DLQ_SUB=genomic-events-dead-letter-sub
DATASET=genomicflow
TAG="verify$(date -u +%Y%m%d%H%M%S)"
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p docs/evidence
OUT="docs/evidence/gcp-verify-$(date -u +%Y-%m-%d).txt"
exec > >(tee "$OUT") 2>&1

PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python

echo "GenomicFlow GCP verification"
echo "project=$PROJECT_ID tag=$TAG start=$START"
echo

echo "== 1. Publishing test messages"
"$PY" -c "from simulator.src.runner import run_simulator; run_simulator(dry_run=False, max_runs=5, interval_seconds=0.2)" >/dev/null
echo "  5 simulator runs published"
gcloud pubsub topics publish "$TOPIC" --project "$PROJECT_ID" \
  --message="{\"run_id\": \"BAD-$TAG\", \"sample_id\": \"SAMP-TEST\", \"status\": \"PASSED\"}" \
  --attribute="verify_tag=$TAG,kind=bad_run_id" >/dev/null
echo "  1 bad run_id published"
gcloud pubsub topics publish "$TOPIC" --project "$PROJECT_ID" \
  --message="this is not json $TAG" \
  --attribute="verify_tag=$TAG,kind=not_json" >/dev/null
echo "  1 non-JSON payload published"
gcloud pubsub topics publish "$TOPIC" --project "$PROJECT_ID" \
  --message="{\"run_id\": \"RUN-$TAG\", \"sample_id\": \"SAMP-POISON\", \"status\": \"PASSED\", \"total_bases\": \"lots\", \"run_timestamp\": \"$START\"}" \
  --attribute="verify_tag=$TAG,kind=poison" >/dev/null
echo "  1 unstorable run published (RUN-$TAG)"
echo

echo "== 2. Running the pipeline until the unstorable run is dead-lettered"
echo "  Pub/Sub backs off 10s, 20s, 40s... between deliveries, so this takes a few minutes."
FOUND=no
for round in $(seq 1 16); do
  SUMMARY="$("$PY" -c "
import json, structlog, logging
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
from pipeline.src.pipeline import run_pipeline
print(json.dumps(run_pipeline(max_messages=100)))" 2>/dev/null | tail -1)"
  echo "  round $round: $SUMMARY"
  if gcloud pubsub subscriptions pull "$DLQ_SUB" --project "$PROJECT_ID" --limit=10 \
       --format='value(message.attributes.verify_tag)' 2>/dev/null | grep -q "^$TAG$"; then
    FOUND=yes
    break
  fi
  sleep 30
done
echo

q() { bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=csv --quiet "$1" | tail -n +2; }

echo "== 3. Where each message ended up"
RUNS="$(q "SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET.sequencing_runs\` WHERE ingested_at >= TIMESTAMP('$START')")"
DUPES="$(q "SELECT COUNT(*) - COUNT(DISTINCT run_id) FROM \`$PROJECT_ID.$DATASET.sequencing_runs\` WHERE ingested_at >= TIMESTAMP('$START')")"
BAD="$(q "SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET.rejected_records\` WHERE rejection_type = 'VALIDATION' AND run_id = 'BAD-$TAG'")"
JUNK="$(q "SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET.rejected_records\` WHERE rejection_type = 'UNPARSEABLE' AND STRPOS(payload, '$TAG') > 0")"
POISON_STORED="$(q "SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET.sequencing_runs\` WHERE run_id = 'RUN-$TAG'")"

check() { if [ "$2" = "$3" ]; then echo "  PASS  $1 (got $2)"; else echo "  FAIL  $1 (expected $3, got $2)"; fi; }
check "simulator runs written to sequencing_runs"        "$RUNS"          5
check "duplicate run rows"                              "$DUPES"         0
check "bad run_id stored in rejected_records"           "$BAD"           1
check "non-JSON payload stored in rejected_records"     "$JUNK"          1
check "unstorable run kept out of sequencing_runs"      "$POISON_STORED" 0
check "unstorable run reached the dead-letter subscription" "$FOUND"     yes
echo

echo "== 4. Rejected records from this run"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=pretty --quiet \
  "SELECT rejection_type, run_id, rejection_reason, delivery_attempt
   FROM \`$PROJECT_ID.$DATASET.rejected_records\`
   WHERE received_at >= TIMESTAMP('$START') ORDER BY received_at"
echo
echo "Saved to $OUT"
echo "If alert_email was set, the dead-letter alert should email you within about 5 minutes."
echo "To clear the dead-lettered test message afterwards:"
echo "  gcloud pubsub subscriptions pull $DLQ_SUB --project $PROJECT_ID --limit=10 --auto-ack"
