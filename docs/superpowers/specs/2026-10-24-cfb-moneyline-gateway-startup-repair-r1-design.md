# CFB Moneyline Gateway Startup Repair R1 — Design

## Problem
The Kyre Sports API production function can build successfully but fail during cold invocation because its FastAPI runtime declares Streamlit. Vercel then installs Streamlit's large UI dependency chain (including PyArrow/Pandas) into the function's ephemeral runtime, exhausting `/tmp`. The Streamlit CFB Moneyline frontend correctly refuses direct-provider fallback, so this API startup failure surfaces as a gateway HTTPError.

## Constraints
- Kyre Sports API remains the only application-facing gateway.
- No direct provider fallback is added to Streamlit.
- Do not modify frozen shared CFB schedule/team modules.
- No provider/model/projection/market-selection behavior changes.
- Keep Streamlit available to the Streamlit application through its existing `requirements.txt`.

## Design
1. Remove Streamlit from the FastAPI `pyproject.toml` dependency set.
2. Before importing API routers, install a tiny API-only `streamlit` compatibility module when real Streamlit is unavailable. It supports the import-time cache decorator surface used by legacy shared modules and inert UI helpers for server execution.
3. Keep shared frozen CFB modules byte-identical.
4. Add a regression test that blocks external Streamlit import, imports the FastAPI entrypoint, and proves `/health` still returns 200.
5. Verify CFB Moneyline route and production health after deployment.

## Success criteria
- FastAPI entrypoint imports with external Streamlit unavailable.
- `pyproject.toml` has no Streamlit dependency.
- `/health` returns 200 in production.
- CFB Moneyline Page 1 returns a Kyre Sports API response without direct frontend fallback.
- Frozen CFB shared files are untouched.
