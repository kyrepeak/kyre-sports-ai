# NFL Receiving Yards Canonical Router V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give NFL Receiving Yards first-class canonical Universal Runtime V5 ownership with no shared generic NFL adapter dependency.

**Architecture:** Keep frozen `nfl_receiving_yards_hub_v21` as the presentation owner. Replace only the universal routing boundary: dedicated registry kind, dedicated adapter, and direct resolver branch. Preserve Step 2D/2E data-gateway and validation contracts.

**Tech Stack:** Python, pytest, GitHub Actions, Streamlit runtime modules.

**Spec:** `docs/superpowers/specs/2026-10-25-nfl-receiving-yards-canonical-router-v1-design.md`

## Global Constraints
- API 2 only; MONSTER untouched.
- One authoritative branch/PR/run path.
- TDD RED before production code.
- Kyre Sports API remains the application-facing gateway.
- Receiving Yards V21 UI/model/data behavior is frozen.
- Sportsbook projection influence remains `0.0`.
- No generic NFL hub/slate/schedule imports on the canonical Receiving Yards route.

## Review Focus
- `nfl/receiving-yards` resolves to V21 through `_nfl_receiving_yards_adapter`.
- Registry kind is dedicated and registry validation remains empty.
- Receiving resolver is selected before the shared `_nfl_adapter` fallback.
- V21 invariants remain intact (`SPORTSBOOK_PROJECTION_INFLUENCE == 0.0`, `MULTI_SOURCE_REQUIRED is True`, `DISPLAY_ONLY is True`).
- Existing hardened NFL routes remain unchanged.

---

### Task 1: Dedicated canonical Receiving Yards routing

**Files:**
- Create: `tests/test_api2_nfl_receiving_yards_canonical_router_v1.py`
- Create: `.github/workflows/api2-nfl-receiving-yards-canonical-router-v1.yml`
- Modify: `api2_universal_sports_router_registry_v1.py`
- Modify: `universal_runtime_v5_loader.py`

**Interfaces:**
- Consumes: `RouterRegistration`, `resolve_destination(RuntimeRoute)`, frozen `nfl_receiving_yards_hub_v21.render_nfl_receiving_yards_hub()`.
- Produces: `_nfl_receiving_yards_adapter(route) -> DestinationAdapter`, registry kind `nfl-receiving-yards`.

- [ ] **Step 1: Write the failing test**
  Assert the Receiving registration uses `nfl-receiving-yards`, target `nfl_receiving_yards_hub_v21`, Kyre gateway + Step 2D metadata, no direct provider frontend, V21 invariants, dedicated adapter presence, direct V21 import/render call, resolver selection, and full registry validation `()`.

- [ ] **Step 2: Run the focused test and verify RED**
  Run: `pytest -q tests/test_api2_nfl_receiving_yards_canonical_router_v1.py`
  Expected: FAIL because registry kind is `nfl-dedicated-hub` and `_nfl_receiving_yards_adapter` does not exist.

- [ ] **Step 3: Implement the minimal production change**
  Change only the Receiving registry kind and add the dedicated adapter + resolver branch. Do not alter V21 or provider/model/UI code.

- [ ] **Step 4: Run focused test and relevant regressions**
  Run the focused test plus Step 2E and hardened NFL canonical-router regressions available in the repository.
  Expected: PASS.

- [ ] **Step 5: Exact-head review and merge gate**
  Confirm branch diff is limited to docs/workflow/test plus the two routing files, all required exact-head checks pass, then merge with expected-head protection.

- [ ] **Step 6: Post-merge freeze proof**
  Confirm `api2-main` points at the merge SHA, Step 2D push proof succeeds on that merge, and production deployments are healthy before declaring GREEN + FROZEN.
