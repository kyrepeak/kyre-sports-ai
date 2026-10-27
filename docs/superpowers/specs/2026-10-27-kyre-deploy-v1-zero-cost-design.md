# KYRE DEPLOY V1 Zero-Cost Migration Design

## Intent

Create a provider-neutral deployment path for Kyre Sports that removes Vercel from the development/build critical path without interrupting the existing live site. The immediate goal is $0 build/test compute using the repository's current public GitHub Actions eligibility, with an eventual $0 production bridge on Oracle Always Free behind Cloudflare.

## Goals

- Keep API 2, MONSTER, and KYRE GUARDIAN execution state completely independent.
- Preserve Kyre Sports API as the only application-facing sports data gateway.
- Move build/test proof onto GitHub Actions standard hosted runners.
- Prove the Streamlit site and Kyre Sports API can be packaged and health-checked without Vercel.
- Reuse the existing `sports_api/Dockerfile` rather than replacing certified API packaging.
- Add a provider-neutral Streamlit container image and local/remote compose contract.
- Make deployment identity explicit so Step 2F/2G can later certify KYRE DEPLOY rather than Vercel.
- Keep current production unchanged until the replacement passes side-by-side verification.

## Non-goals for Phase 1

- Do not change DNS.
- Do not disable or delete Vercel projects.
- Do not provision Oracle Cloud resources from this branch.
- Do not modify API 2 or MONSTER private authority/proof/freeze state.
- Do not migrate Supabase.
- Do not claim production GREEN/FROZEN before an external host exists and live convergence is proven.

## Constraints

- Repository remains public during the $0 build phase so standard GitHub-hosted runner minutes remain free under the current GitHub public-repository model.
- No credentials, provider tokens, sportsbook keys, database passwords, or signing secrets may be committed.
- Existing Guardian shared-infrastructure readiness is context only, never API 2/MONSTER execution evidence.
- No SGO/SportsGameOdds, ESPN, or ESPN BET.
- Existing protected `main` and `runless-final-gate` requirements remain untouched.
- The current live Vercel production path remains the rollback anchor until KYRE DEPLOY production proof exists.

## Approaches considered

### A. GitHub Actions + Oracle Always Free + Cloudflare — selected

Use GitHub Actions for build/test compute, publish or transfer provider-neutral containers, run production on Oracle Always Free, and front it with Cloudflare. This directly targets the observed cost driver: build CPU rather than live traffic.

### B. Vercel Hobby bridge only

Lower immediate cost but keeps daily deployment/rate limits and Vercel-specific build semantics in the critical path. Rejected as the long-term migration target.

### C. Private repository + Oracle self-hosted runner

Protects source visibility but shifts heavy build compute onto the same small free VM intended for production. Rejected for the current high-volume workload because build contention would likely slow delivery.

## Architecture

```text
API 2 / MONSTER / GUARDIAN
        |
        v
Public GitHub repository
        |
        v
GitHub Actions standard runners
  - tests
  - container builds
  - provider-neutral verification
        |
        v
KYRE DEPLOY release candidate
        |
        v
Oracle Always Free VM (Phase 2)
  - Streamlit container
  - Kyre Sports API container
        |
        v
Cloudflare Free
  - DNS
  - TLS
  - CDN / edge protection
        |
        v
Kyre Sports production domain
```

## Phase 1 implementation

1. Add a dedicated Streamlit Dockerfile with a non-root runtime and `/_stcore/health` healthcheck.
2. Add a compose file that wires Streamlit and the existing Kyre Sports API container without embedding secrets.
3. Add a provider-neutral deployment contract module and tests that verify image entrypoints, ports, health endpoints, independence rules, and Vercel non-dependence.
4. Add a GitHub Actions workflow that runs the contract tests and builds both containers on standard hosted runners.
5. Do not push images or deploy externally until an Oracle target and registry policy are explicitly activated.

## Phase 2

After Phase 1 is green, provision Oracle Always Free, install the deployment runtime, configure secrets outside git, start both containers, add Cloudflare DNS/TLS, and run side-by-side production proof. Only then may Step 2F/2G be rewritten to certify KYRE DEPLOY and Vercel be retired.

## Success criteria for Phase 1

- Streamlit image builds from the repository without Vercel-specific runtime requirements.
- Existing `sports_api/Dockerfile` still builds unchanged.
- Both images have deterministic health endpoints.
- GitHub Actions can validate/build both services on the authoritative branch/PR.
- No production DNS, Vercel alias, or API 2/MONSTER frozen state is changed.
