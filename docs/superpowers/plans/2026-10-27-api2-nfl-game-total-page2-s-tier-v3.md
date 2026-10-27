# API2 NFL Game Total Page 2 S-Tier V3 Implementation Plan

**Goal:** Ship a compact, best-in-class NFL Game Total Page 2 command center without changing Page 1, model math, provider routing, or certified projection owners.

**Architecture:** Add V13 as a presentation-only successor over frozen V12/V11. V13 consumes the same selected-game item contract and existing Kyre Sports API display-context helpers. The universal Game Total adapter loads V13 with explicit V12 and Page1 compatibility anchors.

**Spec:** `docs/superpowers/specs/2026-10-27-api2-nfl-game-total-page2-s-tier-v3-design.md`

### Task 1 — RED: V13 presentation contract
- Create `tests/test_api2_nfl_game_total_page2_s_tier_v3.py` before production code.
- Prove V13 is absent, then require semantic market/history/availability/team-split states, matchup edges, total drivers, environment, non-overlapping range callout lanes, compact mobile CSS, and 0.0 influence invariants.
- Require no direct new provider imports and no ESPN/ESPN BET/SGO dependency in V13.

### Task 2 — GREEN: additive V13 owner
- Create `nfl_game_totals_hub_v13.py`.
- Reuse V12 utility/context contracts and V11 Page1 delegation.
- Implement S-tier V3 hierarchy and semantic zero-blank rules.
- Never synthesize projected team points or recent form.
- Run Task 1 tests to GREEN.

### Task 3 — Route ownership
- RED test the universal adapter still points to V12.
- Change only the NFL Game Total adapter to V13, retaining V12/V11/Page1 compatibility anchors.
- Do not preemptively modify shared `app.py`; only classify and repair a live cache issue if Step 2G proves one.

### Task 4 — Regression and quality verification
- Run V3 tests plus all existing V12/state-date/cache-bust/Kyre-gateway regressions.
- Run compile and diff-check gates.
- Run broader NFL Game Total tests, then full project pytest when practical; classify pre-existing/infra failures explicitly.

### Task 5 — API2 proof and Step 2G convergence
- One authoritative branch/PR/proof path only.
- Create feature-scoped Runless proof plan/ledger using V13 and its tests as frozen artifacts; shared mutable entrypoints remain dependencies, not frozen feature artifacts unless the control contract requires otherwise.
- Obtain runless-final-gate, merge protected main, feature-sync approved artifacts to `api2-main`, verify live Streamlit Page 2 markers/behavior, update finalization ledger atomically, close out to durable `GREEN_FROZEN`, release scope lease.
