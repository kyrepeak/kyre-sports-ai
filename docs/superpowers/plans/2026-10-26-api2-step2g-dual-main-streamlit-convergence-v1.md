# API2 Step 2G Dual-Main + Streamlit Convergence V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permanently prevent API2 `GREEN_FROZEN` closeout until approved workstream artifacts match on `main` and `api2-main` and the configured Streamlit production page proves the expected live markers.

**Architecture:** Add an API2-only pure convergence validator plus a reusable Playwright Streamlit certificate. Wire API2 Runless closeout to read an immutable Step 2G sidecar and compare it against the pre-merge receipt artifact map and live GitHub branch trees before durable `GREEN_FROZEN` is allowed. Non-API2 closeout remains unchanged.

**Tech Stack:** Python 3.13, FastAPI/Runless V2, GitHub App authority, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-api2-step2g-dual-main-streamlit-convergence-v1-design.md`

## Global Constraints
- API2 only; no MONSTER authority/state dependency.
- One authoritative branch/PR/proof path.
- Feature-scoped artifact parity, not whole-branch equality.
- `main` + `api2-main` + live Streamlit proof are mandatory for 100%.
- Missing Step 2G evidence caps completion below 100% and blocks `GREEN_FROZEN`.
- Streamlit hostname comes only from `devsystem/production_targets_v1.json`.

## Review Focus
- `main` and `api2-main` have unrelated commit history but identical approved artifacts: must pass.
- One approved artifact missing/stale on either branch: must fail closed.
- Streamlit auth/login/stale marker/forbidden runtime marker: must fail closed.
- Sidecar identity differs from receipt/freeze/workstream: must fail closed.
- Non-API2 closeout must remain unchanged.

---

### Task 1: Convergence contract and RED tests
**Files:**
- Create: `tests/test_api2_step2g_dual_main_streamlit_convergence_v1.py`
- Create: `runless_v2/api2_step2g_convergence_v1.py`

**Interfaces:**
- Produces `validate_convergence_evidence(...) -> dict[str, Any]` and `require_step2g_closeout(...) -> dict[str, Any]`.

- [ ] Write failing tests for dual-main parity, missing branch artifact, stale sidecar identity, Streamlit marker proof, and non-whole-branch equality.
- [ ] Run focused test and confirm RED because Step 2G module does not exist.
- [ ] Implement minimal validator.
- [ ] Re-run focused test to GREEN.

### Task 2: Reusable Streamlit browser certificate
**Files:**
- Create: `devsystem/api2_step2g_streamlit_cert_v1.py`
- Extend: `tests/test_api2_step2g_dual_main_streamlit_convergence_v1.py`

**Interfaces:**
- Produces `evaluate_rendered_body(...)` and a CLI that writes canonical live-render evidence.

- [ ] Add RED tests for required markers, forbidden runtime markers, and canonical production target.
- [ ] Implement the Playwright certificate using `devsystem/production_targets_v1.json`.
- [ ] Re-run focused tests to GREEN.

### Task 3: Permanent Runless closeout enforcement
**Files:**
- Modify: `runless_v2/app.py`
- Modify: `runless_v2/api2_authority_isolation_v1.py`
- Extend: `tests/test_api2_step2g_dual_main_streamlit_convergence_v1.py`

**Interfaces:**
- API2 closeout reads Step 2G sidecar from `api2-step2g-convergence-evidence`; non-API2 closeout bypasses Step 2G.

- [ ] Add RED tests proving API2 closeout calls Step 2G before finalization closeout and legacy workstreams do not.
- [ ] Implement isolated evidence read + validation.
- [ ] Re-run focused tests to GREEN.

### Task 4: Permanent deployment marker + certification lane
**Files:**
- Modify: `app.py`
- Create: `.github/workflows/api2-step2g-dual-main-streamlit-convergence-v1.yml`
- Create: `devsystem/runless_proof_plans/api2-step2g-dual-main-streamlit-convergence-v1.json`
- Create: `devsystem/task_ledgers/api2-step2g-dual-main-streamlit-convergence-v1.json`

- [ ] Add hidden DOM deployment marker `API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1`.
- [ ] Add focused workflow and Runless plan.
- [ ] Run compile + focused tests + broader Runless/API2 tests.
- [ ] Exact-head Runless proof, merge to `main`, sync the approved Step 2G artifacts to `api2-main`, run live Streamlit certificate, write sidecar, and require final `GREEN_FROZEN` readback.
