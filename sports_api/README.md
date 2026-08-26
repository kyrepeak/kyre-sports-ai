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

Use `sports_api/production.env.example` as the deployment template. Real credentials and HMAC secrets belong in the deployment secret manager, not in Git.

Production status endpoints:

- `GET /api/v1/wnba/runtime/readiness` — sanitized network-free preflight report
- `GET /api/v1/wnba/runtime/health` — returns HTTP 200 only when scheduler cycles are allowed; otherwise HTTP 503
- `GET /api/v1/wnba/rankings/player-props/current` — fast durable read path; no sportsbook call or Monte Carlo rebuild
- `GET /api/v1/wnba/rankings/player-props/current/status` — scheduler, cross-process lock, and production runtime diagnostics

Required production persistence:

- `WNBA_CURRENT_BOARD_STORE_PATH`
- `WNBA_PROP_FEED_STORE_PATH`
- `WNBA_BACKTEST_STORE_PATH`
- Step 5Q scheduler lock path, either explicit via `WNBA_BOARD_SCHEDULER_LOCK_PATH` or derived beside the board store

The SQLite files must use absolute paths on persistent storage. Every FastAPI worker process for the service must see the same persistent files for Step 5Q cross-process locking and restart recovery to work correctly.

A typical multi-worker start command is:

```bash
uvicorn sports_api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Keep `WNBA_PRODUCTION_RUNTIME_ENABLED=false` while configuring the deployment. Check `/api/v1/wnba/runtime/readiness`; only enable the switch after `preflight_ready` is true.

## Architecture

```text
sports_api/
├── api/
├── collectors/
├── database/
├── models/
├── simulation/
├── validation/
├── main.py
└── requirements.txt
```

This foundation is intentionally isolated from the existing Streamlit application so API work can be developed and tested without changing the production app.
