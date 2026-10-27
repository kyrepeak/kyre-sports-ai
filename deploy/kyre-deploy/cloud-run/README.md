# KYRE DEPLOY V1 — Cloud Run Foundation

This directory is the fail-closed activation layer for the Kyre Sports API on Google Cloud Run.

## Ownership boundary

GitHub Actions remains the build/test engine. Cloud Run is runtime only. API 2, MONSTER, and Guardian keep their own authority, proof, branch, execution, and GREEN/FROZEN state; this directory does not borrow or infer any of that state.

This script does not create billing accounts. A Google Cloud account, project, linked billing account, and Cloud Run spend-cap budget must exist before activation. This script does not create or store provider secrets. Sportsbook keys, database credentials, Supabase credentials, signing material, and other production values stay outside git and are attached later through the approved runtime secret path.

## Why `us-west1`

The default foundation region is `us-west1` (Oregon) because it is a North American Cloud Run Tier-1 pricing region and is a reasonable low-cost starting point for the current Arizona-centered development phase. The region remains configurable through `KYRE_CLOUD_RUN_REGION` if later latency or data-residency evidence supports a different choice.

## Cost-safety contract

The activation script hard-locks the initial service to:

- request-based billing via `--cpu-throttling`
- minimum instances `0`
- maximum instances `1`
- `1` vCPU
- `1Gi` memory
- startup CPU boost disabled
- concurrency `20`
- request timeout `60s`
- public ingress only for the Kyre Sports API endpoint
- immutable public GHCR image digest only
- no Cloud Build
- no source deployment
- no VPC connector
- no background worker or Cloud Run job

The first service identity should have no broad project roles. Secret access is granted later only to the exact secrets required by the API.

## Human-owned prerequisites

These steps require the Google account owner and therefore are intentionally not automated from ChatGPT:

1. Create or select the dedicated Google Cloud project for KYRE DEPLOY.
2. Link a Cloud Billing account so Cloud Run can be enabled.
3. In **Billing → Budgets & alerts**, create a **Spend cap enforcement** budget scoped to exactly that project and the **Cloud Run** service.
4. Remember that Google's spend-cap calculation uses gross estimated cost and does not include free-tier credits/savings, so the cap is an emergency breaker rather than a direct estimate of the final bill.
5. Keep the cap conservative and let Guardian monitor free-tier consumption separately at 70% warning and 90% critical thresholds.
6. Use Google Cloud Shell for activation so no computer is required.

Spend-cap enforcement is not instantaneous. It is the last-resort breaker; the min/max/billing locks in the deployment script are the first line of defense.

## Activation variables

Start from `cloud-run.env.example` and populate values only inside the authenticated Cloud Shell session:

```bash
export KYRE_GCP_PROJECT_ID="your-project-id"
export KYRE_CLOUD_RUN_REGION="us-west1"
export KYRE_CLOUD_RUN_SERVICE="kyre-sports-api"
export KYRE_CLOUD_RUN_IMAGE="ghcr.io/kyrepeak/kyre-sports-ai/kyre-sports-api@sha256:..."
export KYRE_CLOUD_RUN_SERVICE_ACCOUNT="kyre-sports-api-runtime@your-project-id.iam.gserviceaccount.com"
export KYRE_CLOUD_RUN_SPEND_CAP_CONFIRMED="true"
export KYRE_CLOUD_RUN_ACTIVATE="YES_I_UNDERSTAND"
```

Then run:

```bash
bash deploy/kyre-deploy/cloud-run/deploy-sports-api.sh
```

The script fails closed unless the image is an immutable GHCR digest, the service-account address is valid, the spend-cap acknowledgement is true, and the explicit activation phrase is present.

## What Chunk 2 proves

Chunk 2 proves the repository-side Cloud Run foundation and safety policy. It does not claim a live Cloud Run deployment, DNS cutover, provider-secret injection, production health, or Step 2F/2G convergence. Those are Chunk 3/4 evidence and must be proven against the actual Google project before production migration.
