# CFB Game Total Page 1 A-Tier V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace the cluttered CFB Game Total Page 1 presentation with a compact market-first analytical board while preserving Kyre Sports API-only routing and Page 2 behavior.

**Architecture:** Add a new Page 1 successor that consumes only the existing Kyre Sports API Page 1 endpoint, derives no-vig market probabilities from one sportsbook quote, and renders semantic empty states. Add a universal Runtime V5 loader/terminal successor that swaps only Page 1 ownership while leaving Page 2 on `cfb_game_total_page2_market_completeness_r1`.

**Tech Stack:** Python, Streamlit, existing Universal Runtime V5, Runless V2 proof plane.

**Spec:** `docs/superpowers/designs/2026-10-23-cfb-game-total-page1-atier-v1.md`

## Global Constraints
- KYRE SPORTS API is the only application-facing gateway.
- No SGO, ESPN, or ESPN BET in the Page 1 request path.
- Never average sportsbook lines.
- Never convert null to zero.
- Semantic empty states replace blanks/generic unavailable labels where possible.
- Page 2 remains unchanged.
- No projection/model/ranking/selection mutation.

## Review Focus
- Missing one side of an O/U price must not fabricate probability.
- Positive/negative American odds must convert correctly.
- Multiple books must stay preserved separately; Page 1 selects one quote deterministically rather than averaging.
- Missing quotes must render a semantic market state.
- Page 1 Open Analysis must remain same-tab and route to existing Page 2.

---

### Task 1: Lock the Page 1 presentation contract

**Files:**
- Create: `tests/test_api2_cfb_game_total_page1_atier_v1.py`

**Interfaces:**
- Consumes: existing Kyre Sports API Page 1 payload fields.
- Produces: regression contract for Page 1 successor and runtime activation.

- [ ] Write tests for gateway-only source policy, no-vig math, semantic empty states, removed spread/moneyline UI, compact card labels, same-tab Page 2 link, and runtime ownership.
- [ ] Run the focused test and verify RED because successor modules do not yet exist.
- [ ] Commit RED contract.

### Task 2: Implement compact Page 1 successor

**Files:**
- Create: `cfb_game_total_page1_atier_v1.py`

**Interfaces:**
- Consumes: `/api/v1/cfb/game-total/page1` through the bootstrap-repaired Kyre Sports API base resolver.
- Produces: `render_game_total_page1()` and `render_cfb_hub()`.

- [ ] Implement American implied probability + no-vig normalization with fail-closed `None` semantics.
- [ ] Implement deterministic selected quote with no consensus averaging.
- [ ] Implement compact A-tier card and semantic market states.
- [ ] Preserve same-tab Open Analysis handoff.
- [ ] Run focused tests to GREEN.

### Task 3: Activate only Page 1 in Universal Runtime V5

**Files:**
- Create: `universal_runtime_v5_loader_cfb_game_total_page1_atier_v1.py`
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_page1_atier_v1.py`
- Modify after exact thaw: `app.py`

**Interfaces:**
- Page 1 -> `cfb_game_total_page1_atier_v1`.
- Page 2 -> existing `cfb_game_total_page2_market_completeness_r1` unchanged.

- [ ] Add loader successor with Page 1-only ownership change.
- [ ] Add terminal successor.
- [ ] Obtain exact `app.py` thaw and activate terminal.
- [ ] Run focused + universal/CFB regressions.

### Task 4: Runless proof and terminal closeout

**Files:**
- Create/update: `devsystem/execution_plans/api2-cfb-game-total-page1-atier-v1.json`
- Create/update: `devsystem/runless_proof_plans/api2-cfb-game-total-page1-atier-v1.json`
- Create/update: `devsystem/task_ledgers/api2-cfb-game-total-page1-atier-v1.json`

- [ ] Bind exact base/head/lease/thaw identities.
- [ ] Run exact-head Runless proof.
- [ ] Require `runless-final-gate` success from App ID 5204253.
- [ ] Merge one PR only.
- [ ] Verify merged-main Vercel status, frozen registry forward-port, finalization ledger, durable `GREEN_FROZEN`, then release lease.
