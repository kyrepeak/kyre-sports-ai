# Runless Dynamic Finalization Authority V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Step 1 of the shared Vercel finalizer resolve exactly one current authoritative Runless V2 candidate dynamically instead of using historical PR #1526 / `ALLOWED_BRANCH`.

**Architecture:** Reuse the existing Supabase-backed `runless_v2.proof_runs` + `workstream_leases` state through a focused read-only authority resolver. The finalizer request identifies the workstream/task/candidate/fencing generation; the resolver returns one immutable authority snapshot or fails closed, and GitHub corroborates the resolved PR/head only where applicable. Step 1 does not execute proofs, publish gates, merge, freeze, or mutate the current NBA lane.

**Tech Stack:** Python, FastAPI, httpx, Pydantic, Supabase/PostgREST Runless V2 durable state, GitHub App 5204253, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-runless-dynamic-finalization-authority-v1-design.md`

## Global Constraints

- Existing durable Runless V2 state is the single authority; do not add a second authority registry.
- Remove hard-coded PR #1526 and `ALLOWED_BRANCH` as finalization authority.
- Required invariant: requested candidate SHA == durable Runless authoritative candidate SHA == candidate being finalized.
- Missing, ambiguous, stale, or mismatched authority fails closed.
- Preserve current NBA candidate `0caf4fd0728b5ff666653b385a63d1c8ced9f154`; no NBA restart or mutation in Step 1.
- No duplicate PRs, deployments, proof executions, gates, leases, or async jobs.
- GitHub Actions fallback remains 0.
- Step 1 does not implement Steps 2–6 behavior.

## Review Focus

- Multiple durable rows for one workstream/task/candidate must fail as ambiguous rather than pick newest.
- Terminal/failed historical rows must not silently supersede the one current authoritative row.
- A fencing generation that differs from the authoritative durable row must fail closed.
- Durable-store transport/auth failure must fail closed and must not fall back to PR #1526 or environment defaults.
- A request whose task/workstream is valid but whose candidate SHA belongs to another run must fail closed.

---

### Task 1: Read-only durable authority resolver

**Files:**
- Create: `vercel_finalizer/authority.py`
- Create: `vercel_finalizer/test_authority.py`

**Interfaces:**
- Consumes: existing Supabase URL/service-role environment configuration and Runless V2 `proof_runs` / `workstream_leases` schema.
- Produces: `AuthoritySnapshot` and `resolve_authority(client, *, supabase_url, service_role_key, workstream, task_id, candidate_sha, fencing_generation) -> AuthoritySnapshot`.

- [ ] **Step 1: Write failing resolver tests**

Add tests named `test_resolves_exact_current_authority`, `test_rejects_wrong_candidate`, `test_rejects_wrong_task`, `test_rejects_stale_fence`, `test_rejects_missing_authority`, `test_rejects_ambiguous_authority`, and `test_store_failure_fails_closed`. Assert exact typed failure markers and that no fallback authority is returned.

- [ ] **Step 2: Run resolver tests and verify RED**

Run: `python -m pytest -q vercel_finalizer/test_authority.py`
Expected: FAIL because `vercel_finalizer.authority` does not exist.

- [ ] **Step 3: Implement focused resolver**

In `vercel_finalizer/authority.py`, define immutable `AuthoritySnapshot` containing `proof_id`, `task_id`, `workstream`, `candidate_sha`, `fencing_generation`, `proof_fingerprint`, `state`, `scope_lease_id`, and optional resolved PR/branch metadata only if already present in durable authority. Define typed `FinalizerAuthorityError`. Query Runless V2 durable state read-only and require exactly one matching current authority row plus matching fencing generation. Never choose by recency and never synthesize PR/branch authority.

- [ ] **Step 4: Run resolver tests and verify GREEN**

Run: `python -m pytest -q vercel_finalizer/test_authority.py`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Commit message: `feat: resolve finalizer authority from Runless V2 state`

### Task 2: Replace historical finalizer authority boundary

**Files:**
- Modify: `vercel_finalizer/app.py`
- Modify: `vercel_finalizer/test_app.py` if present; otherwise create `vercel_finalizer/test_dynamic_authority.py`

**Interfaces:**
- Consumes: `resolve_authority(...) -> AuthoritySnapshot` from Task 1.
- Produces: Step-1 finalizer request validation that cannot proceed unless request identity matches the durable snapshot.

- [ ] **Step 1: Write failing integration tests**

Add tests asserting: the request carries `workstream`, `task_id`, `candidate_sha`, and `fencing_generation`; exact authority succeeds through validation; wrong SHA/workstream/task/fence returns conflict; store failure returns failure; and no code path calls `/pulls/1526` or compares against historical `ALLOWED_BRANCH`.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `python -m pytest -q vercel_finalizer/test_dynamic_authority.py vercel_finalizer/test_authority.py`
Expected: FAIL against the historical authority implementation.

- [ ] **Step 3: Modify `vercel_finalizer/app.py`**

Remove `ALLOWED_BRANCH` and `_pr_head()` hard-coding of PR #1526. Extend the request model with `workstream`, `task_id`, and `fencing_generation`. Resolve authority before any gate-related behavior and require exact candidate/workstream/task/fence equality. For Step 1 proof mode, keep gate publication disabled in tests and expose the validated snapshot boundary without implementing Step 3 gate semantics.

- [ ] **Step 4: Run integration tests and verify GREEN**

Run: `python -m pytest -q vercel_finalizer/test_dynamic_authority.py vercel_finalizer/test_authority.py`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Commit message: `fix: remove historical finalizer PR authority`

### Task 3: Remove build/test hard-coding and add regression lock

**Files:**
- Modify: `vercel_finalizer/publish_gate_build.py`
- Modify: `vercel_finalizer/test_publish_gate_build.py`
- Create: `vercel_finalizer/test_no_historical_authority.py`

**Interfaces:**
- Consumes: dynamic request/authority contract from Tasks 1–2.
- Produces: build tooling and regression tests with no historical PR/branch authority.

- [ ] **Step 1: Write regression test**

Assert authority-bearing finalizer source contains neither `DEFAULT_PR_NUMBER = 1526`, `/pulls/1526`, nor `ALLOWED_BRANCH = "api2-universal-sports-source-finalization-v1-step1"`; build helpers require dynamic workstream/task/candidate/fence input instead of historical defaults.

- [ ] **Step 2: Run regression test and verify RED**

Run: `python -m pytest -q vercel_finalizer/test_no_historical_authority.py vercel_finalizer/test_publish_gate_build.py`
Expected: FAIL on existing historical constants/defaults.

- [ ] **Step 3: Update build helper and tests**

Remove historical PR/branch defaults from `publish_gate_build.py` and its tests. Preserve GitHub App ID `5204253`, `runless-final-gate`, and GitHub Actions fallback 0. Do not add a latest-PR heuristic or environment-based replacement authority.

- [ ] **Step 4: Run regression suite and verify GREEN**

Run: `python -m pytest -q vercel_finalizer/test_no_historical_authority.py vercel_finalizer/test_publish_gate_build.py vercel_finalizer/test_dynamic_authority.py vercel_finalizer/test_authority.py`
Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Commit message: `test: lock dynamic finalizer authority contract`

### Task 4: Step-1 exact-head proof and freeze evidence

**Files:**
- Modify only Step-1 control/evidence files required by the repository's existing Runless proof-plan/task-ledger conventions; do not touch NBA Step-1 files.

**Interfaces:**
- Consumes: exact Step-1 candidate from Tasks 1–3.
- Produces: one authoritative exact-head Step-1 proof result and durable GREEN + FROZEN read-back.

- [ ] **Step 1: Verify mutation scope and exact head**

Confirm one architecture branch, one PR if needed, one exact candidate SHA, and no overlap with the six NBA PR #1541 files.

- [ ] **Step 2: Run deterministic local/static Step-1 tests before any remote proof**

Run the Task 1–3 pytest suite once. Expected: PASS with no historical authority regression.

- [ ] **Step 3: Create/reuse exactly one Step-1 Runless proof plan**

Bind it to the exact candidate SHA and Step-1 workstream. Do not create a duplicate deployment/proof/lease when a live authoritative one already exists.

- [ ] **Step 4: Execute one authoritative exact-head proof**

Expected: terminal success for the exact candidate. On failure: classify, patch root cause on the same path, then rebind candidate before any later proof.

- [ ] **Step 5: Read back Step-1 completion evidence**

Verify exact candidate, dynamic-authority tests, durable proof identity, and Step-1 freeze token/read-back according to existing repository governance. Do not use deployment success alone as proof.

- [ ] **Step 6: Mark Step 1 GREEN + FROZEN only after read-back**

Required evidence: exact-head proof PASS, no historical authority, no NBA mutation, durable completion read-back.
