# NFL Spread Dedicated Canonical Router V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make NFL Spread a first-class canonical API 2 runtime route owned directly by the certified V10 Spread page, with no shared `_nfl_adapter` path.

**Architecture:** Keep the existing Spread V10 product stack untouched. Change only canonical route ownership and runtime resolution: Step 2E points to V10, base Universal Runtime V5 gains `_nfl_spread_adapter`, and the current production terminal chain delegates NFL Spread to that canonical resolver.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, Streamlit runtime adapters, Vercel proof/deployments.

**Spec:** `docs/superpowers/specs/2026-10-25-nfl-spread-dedicated-canonical-router-v1-design.md`

## Global Constraints
- API 2 only; MONSTER untouched.
- Step 2A: one authoritative branch, one PR, one run/deployment/proof path.
- Anti-Loop: no duplicate PRs/runs/deployments or repeated unfinished polling.
- Step 2B: acceptance criteria and requirement→proof map locked before production edits.
- Step 2C: classify failures before strategy changes and repair only root cause.
- Step 2D: Kyre Sports API remains the only application-facing gateway; no SGO, ESPN, ESPN BET; direct provider frontend access false.
- Step 2E: explicit route coverage and registry validation stay green.
- Spread V10 UI/model/Line Lab/history/projection behavior remains unchanged.

## Review Focus
- Production terminal must not bypass canonical Spread ownership through the old V23 shared `_nfl_adapter` override.
- Dedicated Spread adapter must call `render_nfl_hub("Spread")`, not a generic market label path.
- Registry target must be V10, not stale V8.
- Spread V10 must retain 0.0% sportsbook projection influence and settlement-only Line Lab behavior.
- Rushing, Receiving, Moneyline, Game Total, Passing Yards, Receptions, Passing TDs, Anytime TD, Daily Picks, CFB/NBA/WNBA routes must remain unchanged.

---

### Task 1: Lock the RED canonical-ownership contract

**Files:**
- Create: `tests/test_api2_nfl_spread_dedicated_canonical_router_v1.py`
- Create: `.github/workflows/api2-nfl-spread-dedicated-canonical-router-v1.yml`

**Interfaces:**
- Consumes: `ROUTER_REGISTRY`, `universal_runtime_v5_loader.py`, current production terminal chain, `nfl_spread_hub_v10.py`.
- Produces: failing assertions that define V10 canonical ownership, dedicated adapter behavior, and production-terminal delegation.

- [ ] **Step 1: Write failing tests**
Require `adapter_kind == "nfl-spread"`, target `nfl_spread_hub_v10`, `_nfl_spread_adapter`, direct V10 import/render, production-terminal delegation to canonical Spread resolution, preserved Step 2D metadata, preserved V10 isolation, and valid Step 2E registry.

- [ ] **Step 2: Add focused workflow**
Compile route boundary and run the new contract plus Spread V10, Step 2D/2E, and existing dedicated NFL route regressions.

- [ ] **Step 3: Open the single authoritative PR and verify RED**
Expected: RED only because registry is stale V8, dedicated adapter is missing, and current terminal still reaches the legacy/shared Spread route.

### Task 2: Minimal root-cause repair

**Files:**
- Modify: `api2_universal_sports_router_registry_v1.py`
- Modify: `universal_runtime_v5_loader.py`
- Modify: `streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py`
- Modify: `universal_runtime_v5_loader_v23.py` only if necessary to eliminate its direct shared Spread ownership while preserving compatibility.

**Interfaces:**
- Produces: `_nfl_spread_adapter(route: RuntimeRoute) -> DestinationAdapter` and canonical V10 ownership.

- [ ] **Step 1: Promote registry ownership to V10**
Set `nfl/spread` to kind `nfl-spread`, target `nfl_spread_hub_v10`.

- [ ] **Step 2: Add dedicated base adapter**
Load `nfl_spread_hub_v10`, render `render_nfl_hub("Spread")`, TTL 20s, and resolve it before generic NFL handling.

- [ ] **Step 3: Route the current production terminal to canonical Spread resolution**
Extend the existing terminal canonical delegation so NFL Spread uses `canonical_loader.resolve_destination(route)` while unrelated routes preserve prior behavior.

- [ ] **Step 4: Neutralize stale V23 shared ownership if required by contract**
Make V23 delegate NFL Spread to canonical base resolution rather than calling `_nfl_adapter` directly.

- [ ] **Step 5: Verify focused GREEN**
Expected: new contract and Spread V10 regressions pass.

### Task 3: Exact-head control-plane proof and freeze

**Files:** verification only unless a classified root-cause repair is needed.

- [ ] **Step 1: Run full required exact-head regressions**
New Spread canonical proof, Spread V10 tests, Step 2A/Anti-Loop, Step 2D, Step 2E, and existing NFL route regressions.

- [ ] **Step 2: Inspect diff/scope and exact candidate SHA**
Reject unrelated changes or a moved head.

- [ ] **Step 3: Merge only exact proven head**
Use expected-head protection.

- [ ] **Step 4: Require post-merge terminal proof**
Confirm `api2-main` points to merge SHA, Step 2D push proof succeeds, Kyre Sports API and Runless Proof deployments from that SHA are READY, and live universal-router health reports no failures.

- [ ] **Step 5: Freeze**
Declare `API2_NFL_SPREAD_DEDICATED_CANONICAL_ROUTER_V1_FROZEN` only after all terminal evidence is green.