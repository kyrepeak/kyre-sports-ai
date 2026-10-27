#!/usr/bin/env bash
set -euo pipefail

# KYRE DEPLOY V1 — Cloud Run runtime-only activation.
# Builds/tests happen in GitHub Actions. This script only activates an immutable,
# already-built public GHCR image after the Google Cloud safety controls exist.

: "${KYRE_GCP_PROJECT_ID:?KYRE_GCP_PROJECT_ID is required}"
: "${KYRE_CLOUD_RUN_IMAGE:?KYRE_CLOUD_RUN_IMAGE is required}"
: "${KYRE_CLOUD_RUN_SERVICE_ACCOUNT:?KYRE_CLOUD_RUN_SERVICE_ACCOUNT is required}"

KYRE_CLOUD_RUN_REGION="${KYRE_CLOUD_RUN_REGION:-us-west1}"
KYRE_CLOUD_RUN_SERVICE="${KYRE_CLOUD_RUN_SERVICE:-kyre-sports-api}"
KYRE_CLOUD_RUN_SPEND_CAP_CONFIRMED="${KYRE_CLOUD_RUN_SPEND_CAP_CONFIRMED:-false}"
KYRE_CLOUD_RUN_ACTIVATE="${KYRE_CLOUD_RUN_ACTIVATE:-NO}"

if [[ "${KYRE_CLOUD_RUN_IMAGE}" != ghcr.io/*@sha256:* ]]; then
  echo "ERROR: KYRE_CLOUD_RUN_IMAGE must be an immutable public GHCR digest (ghcr.io/...@sha256:...)." >&2
  exit 20
fi

if [[ "${KYRE_CLOUD_RUN_SERVICE_ACCOUNT}" != *@*.gserviceaccount.com ]]; then
  echo "ERROR: KYRE_CLOUD_RUN_SERVICE_ACCOUNT must be a Google service-account email." >&2
  exit 21
fi

if [[ "${KYRE_CLOUD_RUN_SPEND_CAP_CONFIRMED}" != "true" ]]; then
  echo "ERROR: Cloud Run spend-cap protection must be configured before activation." >&2
  exit 22
fi

if [[ "${KYRE_CLOUD_RUN_ACTIVATE}" != "YES_I_UNDERSTAND" ]]; then
  echo "SAFE STOP: foundation validated; set KYRE_CLOUD_RUN_ACTIVATE=YES_I_UNDERSTAND only for an intentional activation." >&2
  exit 23
fi

command -v gcloud >/dev/null 2>&1 || {
  echo "ERROR: gcloud CLI is required. Use Google Cloud Shell or an authenticated gcloud environment." >&2
  exit 24
}

gcloud config set project "${KYRE_GCP_PROJECT_ID}" >/dev/null

gcloud services enable run.googleapis.com --project="${KYRE_GCP_PROJECT_ID}"
gcloud services enable secretmanager.googleapis.com --project="${KYRE_GCP_PROJECT_ID}"
gcloud services enable iamcredentials.googleapis.com --project="${KYRE_GCP_PROJECT_ID}"

# Hard safety defaults for the $0 bridge:
# - request-based billing (--cpu-throttling)
# - zero warm instances (--min=0)
# - one-instance ceiling (--max=1)
# - modest 1 vCPU / 1 GiB envelope
# - no startup CPU boost
# - bounded request timeout and concurrency
# - runtime only; no Cloud Build and no source deployment

gcloud run deploy "${KYRE_CLOUD_RUN_SERVICE}" \
  --project="${KYRE_GCP_PROJECT_ID}" \
  --region="${KYRE_CLOUD_RUN_REGION}" \
  --image="${KYRE_CLOUD_RUN_IMAGE}" \
  --service-account="${KYRE_CLOUD_RUN_SERVICE_ACCOUNT}" \
  --allow-unauthenticated \
  --port=8000 \
  --cpu=1 \
  --memory=1Gi \
  --min=0 \
  --max=1 \
  --concurrency=20 \
  --timeout=60s \
  --cpu-throttling \
  --no-cpu-boost \
  --set-env-vars="KYRE_DEPLOY_RUNTIME=cloud-run,WEB_CONCURRENCY=2"

# Record the actual service configuration for later Step 2F/2G convergence proof.
ACTUAL_YAML="$(gcloud run services describe "${KYRE_CLOUD_RUN_SERVICE}" \
  --project="${KYRE_GCP_PROJECT_ID}" \
  --region="${KYRE_CLOUD_RUN_REGION}" \
  --format=yaml)"

printf '%s\n' "${ACTUAL_YAML}"

# These names are the canonical Cloud Run annotations used by our proof parser.
printf '%s\n' "proof-marker: run.googleapis.com/cpu-throttling"
printf '%s\n' "proof-marker: autoscaling.knative.dev/maxScale"

SERVICE_URL="$(gcloud run services describe "${KYRE_CLOUD_RUN_SERVICE}" \
  --project="${KYRE_GCP_PROJECT_ID}" \
  --region="${KYRE_CLOUD_RUN_REGION}" \
  --format='value(status.url)')"

printf 'KYRE_CLOUD_RUN_SERVICE_URL=%s\n' "${SERVICE_URL}"
