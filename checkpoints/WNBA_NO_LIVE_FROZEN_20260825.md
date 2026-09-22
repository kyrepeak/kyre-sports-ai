# WNBA NO-LIVE FROZEN CHECKPOINT — 2026-08-25

## Status
WNBA Live Games has been retired from the running Streamlit application.

The active `app.py` now restores the exact pre-live application checkpoint:

`235d7ddc47de93657910a1f0cf9928f2a9f0f758`

## Frozen WNBA routes preserved
- Points
- Rebounds
- Assists
- Rebounds + Assists
- PRA
- Spread
- Moneyline
- Game Total
- Daily Picks

## Removal contract
- `Live Games` is not present in WNBA navigation.
- No `wnba_live_*` module is imported by the active entrypoint.
- Stale Live-Games session-state payloads are purged on first run after deployment.
- Stale `wnba_live_*` module references from a hot-reloaded worker are removed.
- A clean Streamlit process restart guarantees the retired Live Games module tree is absent from runtime memory.
- Historical live-game source files may remain in the repository only as rollback/archive material; repository files do not consume running Python memory unless imported.

## Production freeze contract
No existing WNBA projection, probability, sportsbook transport, Monte Carlo, calibration, convergence, qualification, ranking, grading, or presentation logic is changed by this removal.

Existing MLB and NFL routes are also preserved exactly through the same pre-live checkpoint.

## Reactivation rule
WNBA Live Games must not be reintroduced without an explicit future build decision and a new checkpoint.
