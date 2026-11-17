#!/usr/bin/env bash
# Read-only checks before deploying GenomicFlow to GCP. Changes nothing.
#
#   GCP_PROJECT_ID=your-project bash scripts/gcp_preflight.sh
#
# Without GCP_PROJECT_ID it uses the gcloud default project.
set -u
cd "$(dirname "$0")/.." || exit 1

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
ok()   { printf '  OK    %s\n' "$*"; }
warn() { printf '  CHECK %s\n' "$*"; }

echo "== Tools"
for t in gcloud terraform bq python3; do
  if command -v "$t" >/dev/null 2>&1; then
    case "$t" in
      terraform) ok "$t $(terraform -version 2>/dev/null | head -1)" ;;
      bq)        ok "$t present" ;;
      *)         ok "$t $("$t" --version 2>/dev/null | head -1)" ;;
    esac
  else
    warn "$t is not installed"
  fi
done
if python3 -c "import google.cloud.pubsub_v1, google.cloud.bigquery, structlog, faker" 2>/dev/null; then
  ok "Python packages installed"
else
  warn "Python packages missing: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e ."
fi

echo "== Authentication"
ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)"
if [ -n "$ACCOUNT" ]; then ok "gcloud signed in as $ACCOUNT"; else warn "not signed in: gcloud auth login --no-launch-browser"; fi
if gcloud auth application-default print-access-token >/dev/null 2>&1; then
  ok "application default credentials present (used by Terraform and the pipeline)"
else
  warn "no application default credentials: gcloud auth application-default login --no-launch-browser"
fi

echo "== Project: ${PROJECT_ID:-<none set>}"
if [ -z "$PROJECT_ID" ]; then
  warn "no project: export GCP_PROJECT_ID=... or gcloud config set project ..."
  exit 1
fi
DESC="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber,lifecycleState)' 2>/dev/null)"
if [ -n "$DESC" ]; then ok "project number and state: $DESC"; else warn "project not found or no access"; fi
BILLING="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null)"
if [ "$BILLING" = "True" ]; then ok "billing enabled"; else warn "billing enabled: ${BILLING:-unknown}"; fi

echo "== APIs"
ENABLED="$(gcloud services list --enabled --project "$PROJECT_ID" --format='value(config.name)' 2>/dev/null)"
MISSING=""
for api in pubsub bigquery storage monitoring iam cloudresourcemanager; do
  if echo "$ENABLED" | grep -q "^${api}.googleapis.com$"; then ok "$api"; else warn "$api not enabled"; MISSING="$MISSING ${api}.googleapis.com"; fi
done
[ -n "$MISSING" ] && echo "  enable with: gcloud services enable$MISSING --project $PROJECT_ID"

echo "== What already exists in the project"
echo "  Pub/Sub topics:";        gcloud pubsub topics list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | sed 's/^/    /'
echo "  Pub/Sub subscriptions:"; gcloud pubsub subscriptions list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | sed 's/^/    /'
echo "  BigQuery datasets:";     bq ls --project_id "$PROJECT_ID" 2>/dev/null | sed 's/^/    /'
echo "  Buckets:";               gcloud storage buckets list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | sed 's/^/    /'
echo "  Cloud Run services:";    gcloud run services list --project "$PROJECT_ID" --format='value(metadata.name,status.url)' 2>/dev/null | sed 's/^/    /'

echo "== Terraform state"
if [ -f infra/terraform.tfstate ]; then
  N="$(python3 -c "import json;print(len(json.load(open('infra/terraform.tfstate')).get('resources',[])))" 2>/dev/null)"
  ok "infra/terraform.tfstate found with ${N:-?} resources"
  STATE=yes
else
  warn "no infra/terraform.tfstate in this folder"
  STATE=no
fi

echo "== Next step"
if gcloud pubsub topics describe genomic-events --project "$PROJECT_ID" >/dev/null 2>&1; then
  if [ "$STATE" = yes ]; then
    echo "  The May deployment and its state are here: run terraform plan and apply as normal."
  else
    echo "  Resources from the May deployment exist but this folder has no state for them."
    echo "  Either use the folder you deployed from, or import them before applying (send this output to Claude)."
  fi
else
  echo "  Nothing deployed: terraform apply will create everything fresh."
fi
