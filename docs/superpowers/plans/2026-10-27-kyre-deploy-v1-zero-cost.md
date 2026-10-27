# KYRE DEPLOY V1 Zero-Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-neutral, $0-build migration path that packages and validates the Streamlit site plus existing Kyre Sports API without changing live production.

**Architecture:** GitHub Actions standard hosted runners perform tests and container builds. The existing `sports_api/Dockerfile` remains authoritative for the API; a new Streamlit Dockerfile and compose contract provide a host-neutral runtime. Oracle/Cloudflare activation is a later phase and is intentionally not performed here.

**Tech Stack:** Python 3.13/3.12, Streamlit, FastAPI/Uvicorn, Docker, Docker Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-27-kyre-deploy-v1-zero-cost-design.md`

## Global Constraints

- Do not change DNS, Vercel aliases/projects, or the live site.
- Do not modify API 2 or MONSTER private branch/proof/freeze state.
- Reuse `sports_api/Dockerfile` unchanged.
- Commit no credentials or secrets.
- Preserve protected `main` and `runless-final-gate` behavior.
- Guardian shared readiness is context only, never execution evidence.

## Review Focus

- Streamlit container healthcheck must use `/_stcore/health` and bind `0.0.0.0`.
- Compose must not embed credentials and must allow API base URL injection.
- CI must build both containers without publishing/deploying them.
- API packaging must remain the existing certified Dockerfile.
- New deployment files must not require Vercel environment variables to start.

---

### Task 1: Provider-neutral deployment contract tests

**Files:**
- Create: `tests/test_kyre_deploy_v1_contract.py`
- Create: `devsystem/kyre_deploy_v1_contract.py`

**Interfaces:**
- Produces: `validate_kyre_deploy_v1(repo_root: Path) -> dict[str, object]`
- Consumes: repository deployment files created by Tasks 2-3.

- [ ] **Step 1: Write failing tests** for required paths, Streamlit entrypoint/healthcheck, API Dockerfile preservation, compose wiring, and no Vercel runtime dependency.
- [ ] **Step 2: Run** `pytest -q tests/test_kyre_deploy_v1_contract.py` and confirm RED because implementation/deployment files are missing.
- [ ] **Step 3: Implement** `devsystem/kyre_deploy_v1_contract.py` with deterministic static validation only; no network calls.
- [ ] **Step 4: Run** the focused test and confirm remaining failures are only missing Task 2-3 files.

### Task 2: Streamlit provider-neutral container

**Files:**
- Create: `deploy/kyre-deploy/streamlit.Dockerfile`
- Create: `deploy/kyre-deploy/streamlit-healthcheck.py`

**Interfaces:**
- Produces: container on port `8501`, command `streamlit run app.py`, health endpoint `/_stcore/health`.
- Consumes: root `requirements.txt` and `app.py`.

- [ ] **Step 1: Extend contract test assertions** for non-root user, port 8501, `0.0.0.0`, and health endpoint.
- [ ] **Step 2: Run focused test and confirm RED.**
- [ ] **Step 3: Add minimal Streamlit Dockerfile and healthcheck helper.**
- [ ] **Step 4: Run focused test and confirm Streamlit assertions GREEN.**

### Task 3: Two-service compose contract

**Files:**
- Create: `deploy/kyre-deploy/compose.yaml`
- Create: `deploy/kyre-deploy/README.md`

**Interfaces:**
- Produces: `kyre-streamlit` and `kyre-sports-api` services with internal API URL and no committed secrets.
- Consumes: Task 2 Streamlit Dockerfile and existing `sports_api/Dockerfile`.

- [ ] **Step 1: Extend contract tests** for service names, Dockerfile paths, ports, healthchecks, and environment-variable-only secret/config injection.
- [ ] **Step 2: Run focused test and confirm RED.**
- [ ] **Step 3: Add compose file and operator README.**
- [ ] **Step 4: Run focused test and confirm GREEN.**

### Task 4: Free GitHub Actions build gate

**Files:**
- Create: `.github/workflows/kyre-deploy-v1-zero-cost-ci.yml`

**Interfaces:**
- Produces: `kyre-deploy-v1` CI check that runs contract tests and builds both images without publishing.
- Consumes: Tasks 1-3.

- [ ] **Step 1: Extend contract tests** to require `ubuntu-latest`, focused pytest, both Docker builds, no registry push, and concurrency cancellation for superseded branch runs.
- [ ] **Step 2: Run focused test and confirm RED.**
- [ ] **Step 3: Add the workflow.**
- [ ] **Step 4: Run focused test and confirm GREEN.**
- [ ] **Step 5: Run repository test suite or the broadest safe test command available; record any unrelated pre-existing failures.**

### Task 5: PR-level proof

**Files:**
- No new production files.

**Interfaces:**
- Produces: one authoritative pull request and exact-head GitHub Actions evidence.
- Consumes: Tasks 1-4.

- [ ] **Step 1: Open one PR from `kyre-deploy-v1-zero-cost-migration` to `main`.**
- [ ] **Step 2: Wait for exact-head workflow result; do not duplicate runs.**
- [ ] **Step 3: If CI fails, classify the first broken boundary before patching.**
- [ ] **Step 4: Stop before merge/cutover; merging shared infrastructure is a separate production-impact decision.**
