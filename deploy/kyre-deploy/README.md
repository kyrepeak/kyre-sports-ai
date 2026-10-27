# KYRE DEPLOY V1

This directory defines the provider-neutral Phase-1 runtime for Kyre Sports.

## Services

- `kyre-streamlit` — the Streamlit website on port `8501`.
- `kyre-sports-api` — the existing Kyre Sports API container on port `8000`.

The API remains the only application-facing sports data gateway. The Streamlit service reaches it through `KYRE_SPORTS_API_BASE_URL`, which defaults to the internal compose hostname `http://kyre-sports-api:8000`.

## Safety

No credentials are committed to these files. API keys, database credentials, sportsbook credentials, provider tokens, signing keys, and production host credentials must be injected by the runtime environment rather than stored in git.

This Phase-1 topology does **not** change DNS, Vercel aliases, production deployment identity, API 2 state, MONSTER state, or Guardian ownership. The existing live deployment remains the rollback anchor until a future Phase-2 host passes side-by-side production verification.

## Local or host-neutral start

From the repository root:

```bash
docker compose -f deploy/kyre-deploy/compose.yaml up --build
```

Expected health surfaces:

- Streamlit: `http://127.0.0.1:8501/_stcore/health`
- Kyre Sports API: `http://127.0.0.1:8000/health`

## Phase 2

Phase 2 will attach this topology to the selected external host, inject production secrets outside git, add Cloudflare DNS/TLS, and run exact deployment/runtime convergence proof before any production cutover.
