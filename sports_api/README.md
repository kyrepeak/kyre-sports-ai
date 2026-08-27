# Kyre Sports API

Private sports-data and analytics backend for the Streamlit app.

## Current foundation

- FastAPI application
- Root status endpoint: `/`
- Health endpoint: `/health`
- Automatic API docs: `/docs`
- Modular packages for collectors, database, models, simulation, and validation

## Run locally

From the repository root:

```bash
pip install -r sports_api/requirements.txt
uvicorn sports_api.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## WNBA production runtime — Step 5R

Step 5R is the fail-closed activation layer around the frozen Step 5P scheduler and Step 5Q multi-worker lock.

The scheduler is not allowed to contact a sportsbook provider or start Monte Carlo/model rebuild work unless the production runtime preflight is green and `WNBA_PRODUCTION_RUNTIME_ENABLED=true`.

Production status endpoints:

- `GET /api/v1/wnba/runtime/readiness` — sanitized network-free Step 5R preflight report
- `GET /api/v1/wnba/runtime/health` — HTTP 200 only when scheduler cycles are allowed; otherwise HTTP 503
- `GET /api/v1/wnba/rankings/player-props/current` — fast durable read path; no sportsbook call or Monte Carlo rebuild
- `GET /api/v1/wnba/rankings/player-props/current/status` — scheduler, cross-process lock, and production runtime diagnostics

## WNBA deployment + live smoke — Step 5S

Step 5S packages the API for deployment and verifies the deployed service without changing any frozen model or publication semantics.

Important topology rule: the current SQLite coordination layer is approved for **one service replica/container only**. Step 5Q safely coordinates multiple Uvicorn worker processes inside that one replica because they share the same persistent volume and lock database. Do not scale this version to multiple service replicas; a true distributed lock backend is required first.

Deployment endpoints:

- `GET /api/v1/wnba/runtime/deployment` — network-free deployment/topology gate
- `GET /api/v1/wnba/runtime/smoke-plan` — returns the exact read-only live smoke plan without making outbound requests

Required Step 5S deployment variables are included in `sports_api/production.env.example`:

- `WNBA_DEPLOYMENT_MODE=container`
- `WNBA_DEPLOYMENT_REPLICA_COUNT=1`
- `WEB_CONCURRENCY=2`
- `PORT=8000`
- `WNBA_PERSISTENT_VOLUME_ROOT=/var/lib/kyre-sports-api`

All runtime SQLite files must live beneath the persistent volume root:

- `WNBA_CURRENT_BOARD_STORE_PATH`
- `WNBA_PROP_FEED_STORE_PATH`
- `WNBA_BACKTEST_STORE_PATH`
- `WNBA_BOARD_SCHEDULER_LOCK_PATH`

Build the production image from the repository root:

```bash
docker build -f sports_api/Dockerfile -t kyre-sports-api .
```

The image runs as a non-root user and starts:

```bash
uvicorn sports_api.main:app --host 0.0.0.0 --port $PORT --workers $WEB_CONCURRENCY
```

The container liveness check uses `/health`. The deeper WNBA deployment/runtime gates remain separate so an intentionally disabled production scheduler does not make the web process look dead.

### Safe deployment sequence

Keep `WNBA_PRODUCTION_RUNTIME_ENABLED=false` for the first deployment. Then verify:

```text
/health
→ /api/v1/wnba/runtime/readiness
→ /api/v1/wnba/runtime/deployment
→ read-only Step 5S live smoke
→ enable WNBA_PRODUCTION_RUNTIME_ENABLED
→ /api/v1/wnba/runtime/health
→ run Step 5S smoke again with scheduler-ready required
```

Run the read-only smoke test from any machine with this repository:

```bash
python -m sports_api.tools.wnba_live_smoke https://your-api-host.example.com
```

After production activation:

```bash
python -m sports_api.tools.wnba_live_smoke https://your-api-host.example.com --expect-scheduler-ready
```

The Step 5S smoke runner issues **GET requests only**. It intentionally excludes `POST /api/v1/wnba/rankings/player-props/current/refresh`, so smoke testing does not intentionally trigger sportsbook collection or Monte Carlo work.

## WNBA immutable releases + rollback — Step 5T

Step 5T adds an immutable release manifest and a two-phase activation/rollback contract around frozen Steps 5R and 5S. It does not change any projection or sportsbook logic.

New runtime endpoints:

- `GET /api/v1/wnba/runtime/release` — current immutable release identity, storage fingerprint, activation state, and rollback readiness
- `GET /api/v1/wnba/runtime/activation-plan` — ordered fail-closed activation procedure
- `GET /api/v1/wnba/runtime/rollback-plan` — ordered rollback procedure that preserves the persistent volume

Every normal production release should record:

```text
WNBA_RELEASE_ID
WNBA_RELEASE_CHANNEL=production
WNBA_DEPLOYMENT_REVISION=<full 40-character Git SHA>
WNBA_DEPLOYMENT_IMAGE_REF=<image-name>@sha256:<64-hex digest>
WNBA_PREVIOUS_DEPLOYMENT_REVISION=<previous full Git SHA>
WNBA_PREVIOUS_DEPLOYMENT_IMAGE_REF=<previous immutable image digest>
```

For a first-ever deployment, explicitly set `WNBA_RELEASE_INITIAL_DEPLOYMENT=true`; the emergency fallback is then to disable the runtime while preserving the persistent volume because there is no prior image yet.

The release sequence is deliberately two phase:

```text
immutable image deployed
→ WNBA_PRODUCTION_RUNTIME_ENABLED=false
→ persistent volume mounted
→ Step 5S read-only smoke passes
→ Step 5T release identity matches expected Git SHA + image digest
→ enable frozen Step 5R runtime switch
→ runtime health must return 200
→ active read-only smoke passes
→ current board publication appears
→ restart once
→ exact persistent storage identity is reverified
```

Remote release verification is also GET-only:

```bash
python -m sports_api.tools.wnba_release_verify \
  https://your-api-host.example.com \
  --revision <full-git-sha> \
  --image-ref registry.example.com/kyre-sports-api@sha256:<digest> \
  --release-id <release-id>
```

Rollback always disables scheduler writes first. It then keeps the same persistent volume and, for non-initial releases, redeploys the previously recorded immutable image. Step 5T never deletes SQLite files and never performs backward schema migration as part of rollback.

The Docker image also records OCI `revision` and `version` labels when built with:

```bash
docker build \
  --build-arg WNBA_RELEASE_REVISION=<full-git-sha> \
  --build-arg WNBA_RELEASE_ID=<release-id> \
  -f sports_api/Dockerfile \
  -t kyre-sports-api .
```

## WNBA hosted staging — Step 5U

Step 5U is the first real-host integration contract. The initial supported host adapter is **Render** because this SQLite architecture requires a Docker-capable web service with one service instance, HTTPS, and a persistent disk.

Step 5U does not activate the sportsbook/model scheduler. The first hosted deployment must stay fail-closed with:

```text
WNBA_PRODUCTION_RUNTIME_ENABLED=false
WNBA_DEPLOYMENT_REPLICA_COUNT=1
WNBA_STAGING_HOST_PROVIDER=render
WNBA_HOST_ENVIRONMENT=staging
```

New endpoints:

- `GET /api/v1/wnba/runtime/hosting` — verifies the hosted staging identity, Render runtime metadata, Step 5T release revision, single-instance deployment contract, persistent-storage identity, and pre-activation state
- `GET /api/v1/wnba/runtime/hosting-smoke-plan` — returns the exact Step 5U GET-only remote verification plan

The Step 5U remote verifier is:

```bash
python -m sports_api.tools.wnba_staging_verify \
  https://your-staging-service.onrender.com \
  --revision <full-git-sha> \
  --release-id <release-id> \
  --storage-identity <64-character-storage-sha256> \
  --service-name kyre-sports-api-staging
```

The hosted smoke sequence requires:

```text
GET /health                                      → 200
GET /api/v1/wnba/runtime/readiness              → 200 + activation OFF
GET /api/v1/wnba/runtime/deployment             → 200
GET /api/v1/wnba/runtime/release                → 200 + pre_activation_ready
GET /api/v1/wnba/runtime/hosting                → 200 + host_contract_ready
GET /api/v1/wnba/runtime/health                 → 503 (required before activation)
GET /api/v1/wnba/rankings/player-props/current → 200 or 409
```

That 503 is intentional during Step 5U: it proves the web service is alive while the production scheduler remains disarmed. Every Step 5U remote request is GET-only; the verifier never calls the manual refresh endpoint and does not intentionally trigger sportsbook collection or Monte Carlo.

A non-auto-sync Render staging Blueprint template is provided at:

```text
sports_api/hosting/render.staging.yaml.template
```

It is deliberately not named `render.yaml` and contains placeholders so committing the API code cannot create a paid external resource by accident. Before a real staging deployment, replace every `__TOKEN__`, pin the container by digest, create exactly one Render web-service instance, attach a persistent disk at `/var/lib/kyre-sports-api`, and store the real provider credential in Render's secret environment configuration.

The first external deployment remains a separate operator action because it requires access to the hosting account and may create billable infrastructure. Step 5U's code, CI contract, and verification tooling can be completed without creating that external resource.

Use `sports_api/production.env.example` as the deployment template. Real provider credentials and HMAC secrets belong in the deployment secret manager, never in Git.

## Architecture

```text
sports_api/
├── api/
├── collectors/
├── database/
├── hosting/
├── models/
├── simulation/
├── tools/
├── validation/
├── Dockerfile
├── main.py
└── requirements.txt
```

This foundation is intentionally isolated from the existing Streamlit application so API work can be developed and tested without changing the production app.
