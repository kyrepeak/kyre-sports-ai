# API2 NFL Receptions Canonical Router V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give NFL Receptions dedicated canonical API2 route ownership while preserving Step 2D/2E rules and fail-closed data truth.

**Architecture:** Add one Receptions-only runtime module, point the canonical registry directly at it, and add a dedicated Universal Runtime V5 destination adapter. The runtime performs no direct provider access and cannot fall through the legacy NFL foundation.

**Tech Stack:** Python 3.12, Streamlit, pytest, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-10-25-api2-nfl-receptions-canonical-router-v1-design.md`

## Global Constraints
- API 2 only; MONSTER is untouched.
- Exactly one authoritative branch/PR/proof lane.
- Kyre Sports API remains the only application-facing data gateway.
- No SGO, ESPN, ESPN BET, or direct sportsbook frontend access.
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- Existing Step 2E coverage must remain valid.

## Review Focus
- Receptions must not resolve through `nfl_hub_v18` or `nfl_hub_v1`.
- Registry target and Universal Runtime adapter must agree exactly.
- Dedicated runtime must not add direct provider/network dependencies.
- Unknown/unavailable Receptions data must remain semantic/fail-closed, never fabricated.
- Other NFL routes must retain their existing resolver behavior.

---

### Task 1: Dedicated Receptions route contract

**Files:**
- Create: `tests/test_api2_nfl_receptions_canonical_router_v1.py`
- Create: `.github/workflows/api2-nfl-receptions-canonical-router-v1.yml`

**Interfaces:**
- Consumes: Step 2E `ROUTER_REGISTRY` and Universal Runtime V5 loader source.
- Produces: failing contract for `nfl_receptions_runtime_v1`, dedicated registry ownership, and explicit loader adapter.

- [ ] **Step 1:** Write tests asserting registry target `nfl_receptions_runtime_v1`, adapter kind `nfl-receptions`, Step 2D/2E metadata, isolated runtime source, and explicit loader adapter.
- [ ] **Step 2:** Run focused workflow and verify RED because dedicated Receptions runtime/ownership does not yet exist.

### Task 2: Implement dedicated runtime and routing

**Files:**
- Create: `nfl_receptions_runtime_v1.py`
- Modify: `api2_universal_sports_router_registry_v1.py`
- Modify: `universal_runtime_v5_loader.py`

**Interfaces:**
- Produces: `render_nfl_receptions_runtime() -> None` and `_nfl_receptions_adapter(route) -> DestinationAdapter`.

- [ ] **Step 1:** Create Receptions-only runtime with frozen marker, 0.0 sportsbook projection influence, no provider calls, and semantic fail-closed copy.
- [ ] **Step 2:** Change canonical registry Receptions target/kind.
- [ ] **Step 3:** Add dedicated Universal Runtime V5 adapter and route selection.
- [ ] **Step 4:** Run focused Receptions contract and Step 2E contract to GREEN.

### Task 3: Exact-head proof and integration

**Files:**
- Verify only unless a proven defect requires a narrowly scoped patch.

**Interfaces:**
- Consumes: exact branch head from Tasks 1-2.
- Produces: PR exact-head proof suitable for merge.

- [ ] **Step 1:** Open/reuse exactly one PR to `api2-main`.
- [ ] **Step 2:** Confirm focused workflow success on exact PR head.
- [ ] **Step 3:** Confirm Step 2A/Anti-Loop, Step 2D, and Step 2E checks are successful or unchanged where applicable.
- [ ] **Step 4:** Merge only with expected-head SHA after terminal proof.
- [ ] **Step 5:** Verify merged `api2-main` contains the dedicated Receptions registration and production deployment reaches terminal success.
