# CFB Moneyline Gateway Startup Repair R1 — Implementation Plan

1. Add failing regression tests for Streamlit-free FastAPI startup and dependency isolation.
2. Add API-only Streamlit compatibility helper.
3. Install compatibility helper before router imports in `kyre_sports_api_vercel_v1.py`.
4. Remove Streamlit from FastAPI `pyproject.toml`; retain frontend `requirements.txt` unchanged.
5. Run focused tests, API import/health smoke, CFB Moneyline tests, Game Total regression tests, and compile checks.
6. Commit once to the authoritative repair branch, open one PR, request one Runless proof, merge only after terminal proof, verify production, freeze, close out, and release the scope lease.
