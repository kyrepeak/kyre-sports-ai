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

Use `sports_api/production.env.example` as the deployment template. Real provider credentials and HMAC secrets belong in the deployment secret manager, never in Git.

## Architecture

```text
sports_api/
├── api/
├── collectors/
├── database/
├── models/
├── simulation/
├── tools/
├── validation/
├── Dockerfile
├── main.py
└── requirements.txt
```

This foundation is intentionally isolated from the existing Streamlit application so API work can be developed and tested without changing the production app.
