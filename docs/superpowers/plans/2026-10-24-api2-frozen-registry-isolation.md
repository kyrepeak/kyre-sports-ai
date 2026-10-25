# API2 Frozen Registry Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make API 2 freeze authority completely independent from MONSTER while preserving exact-head frozen-artifact verification.

**Architecture:** Give API 2 its own registry implementation, constants, state ref, state path, lifecycle dependency, and workflow fetch. Keep the existing registry contract behavior, but remove every MONSTER authority dependency from the API 2 freeze chain.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, Git refs.

**Spec:** User control contract in the current API 2 execution: API 2 and MONSTER must never reuse or depend on each other's branches, registry state, proof artifacts, execution state, or GREEN/FROZEN evidence.

## Global Constraints

- API 2 authoritative code branch: `api2-main`.
- API 2 registry ref: `refs/heads/api2-frozen-registry`.
- API 2 registry state path: `devsystem/api2_frozen_registry_state_v1.json`.
- No API 2 freeze module/workflow may import, fetch, inspect, or verify a MONSTER registry/ref/state file.
- Fail closed on invalid state, mismatched blobs, wrong-head thaws, tampering, or ambiguous registry progress.
- One repair branch and one PR only.

## Review Focus

- MONSTER strings or imports surviving anywhere in API 2 freeze authority.
- Workflow fetching the wrong registry ref/path.
- Registry validator accepting the wrong version/ref/path.
- Exact-head thaw semantics regressing.
- Lifecycle planner producing a state that its API 2 validator rejects.

---

### Task 1: Lock isolation with a failing contract test

**Files:**
- Create: `tests/test_devsystem_api2_frozen_registry_isolation_v1.py`

**Interfaces:**
- Consumes: current API 2 lifecycle/workflow.
- Produces: failing proof that API 2 has no independent registry implementation yet.

- [ ] Add tests for API 2 registry constants, lifecycle import isolation, workflow ref/path isolation, and registry self-test.
- [ ] Run the test and verify RED on the missing API 2 registry module / existing MONSTER dependency.

### Task 2: Add independent API 2 registry and rewire lifecycle

**Files:**
- Create: `devsystem/api2_frozen_artifact_registry_v1.py`
- Modify: `devsystem/api2_frozen_registry_lifecycle_v1.py`
- Modify: `tests/test_devsystem_api2_frozen_registry_lifecycle_v1.py`

**Interfaces:**
- Produces: `validate_registry`, `_hash`, `_payload_without_hash`, exact-head evaluation, and API 2-only registry constants.

- [ ] Implement the independent API 2 registry contract.
- [ ] Change lifecycle/test imports to API 2 registry only and change sample registry metadata to API 2 values.
- [ ] Run focused tests and verify GREEN.

### Task 3: Rewire workflow and prove zero MONSTER authority dependency

**Files:**
- Modify: `.github/workflows/api2-proof-architecture-v1-step6-frozen-registry-lifecycle.yml`
- Test: `tests/test_devsystem_api2_frozen_registry_isolation_v1.py`

**Interfaces:**
- Consumes: `refs/heads/api2-frozen-registry`, `devsystem/api2_frozen_registry_state_v1.json`.

- [ ] Fetch only `api2-frozen-registry` and verify only with `api2_frozen_artifact_registry_v1.py`.
- [ ] Run lifecycle + isolation tests and compile proof.
- [ ] Open one PR to `api2-main`; require terminal exact-head CI before merge/freeze.

### Task 4: Freeze and read back the API 2 checkpoint

**Files:**
- Create/update on `api2-frozen-registry`: `devsystem/api2_frozen_registry_state_v1.json`.

**Interfaces:**
- Consumes: merged exact API 2 SHA and Git blob SHAs for the protected Step 2A/Anti-Loop/2B/2C/2D artifacts.
- Produces: independent API 2 FROZEN checkpoint with tamper-evident state hash.

- [ ] Write registry state only after merged-head CI and deployment/runtime proof are GREEN.
- [ ] Read back the API 2 registry and validate exact version/ref/path/state hash.
- [ ] Mark GREEN + FROZEN only after readback succeeds.
