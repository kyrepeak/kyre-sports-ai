# API 2 NFL Spread Professional Intelligence V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the NFL Spread matchup card into a compact, professional, decision-first information surface while preserving the frozen V6 date repair, V4/V3 model stack, deterministic 5M Monte Carlo, market transport, and 0.0% sportsbook projection influence.

**Architecture:** Add a pure presentation renderer and an additive V7 hub above frozen V6. V7 installs the already-certified V136 HTML guard, temporarily replaces only V4's matchup-card renderer for the duration of the render, and restores the frozen renderer afterward. The existing mobile overlay remains the production entry seam and keeps the tap-only NFL market picker.

**Tech Stack:** Python, Streamlit, HTML/CSS, pytest, Runless V2 proof authority.

**Spec:** User-approved 2026-10-16 NFL Spread cleanup: professional hierarchy, substantially more information, compact mobile presentation, no model/math changes.

## Global Constraints
- One authoritative branch/PR/proof path.
- No GitHub Actions fallback; final proof uses Runless V2.
- Preserve V6 repeatable empty-date auto-advance and tap-only mobile NFL market navigation.
- Do not modify Spread V1-V6, Spread Model V1, or Spread MC V1.
- Sportsbook projection influence remains exactly 0.0%.
- No stake sizing or wager actions.
- Display fair lines at professional one-decimal precision; retain full internal precision unchanged.
- Fail closed when analytics or a certified market line is unavailable.

## Review Focus
- Market-unavailable games must not fabricate a model edge.
- Unready analytics must render a gated verdict rather than synthetic probabilities.
- Home/away fair-line and edge signs must be correct.
- Mobile layout must avoid the old tall repeated metric-card stack.
- V7 must restore V4's original matchup renderer after every render.

---

### Task 1: Professional matchup renderer

**Files:**
- Create: `nfl_spread_professional_intelligence_v1.py`
- Test: `tests/test_nfl_spread_professional_intelligence_v1.py`

**Interfaces:**
- Consumes: certified `game`, `market`, `analytics`, and normalized first-book dictionaries.
- Produces: `render_matchup_card(...) -> str` and presentation CSS.

- [x] Write focused failing tests for decision hierarchy, precision cleanup, information sections, and fail-closed states.
- [x] Verify RED because the renderer does not exist.
- [x] Implement the pure renderer.
- [x] Verify GREEN locally.

### Task 2: Additive V7 activation

**Files:**
- Create: `nfl_spread_hub_v7.py`
- Modify: `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py`
- Test: `tests/test_nfl_spread_professional_intelligence_v1.py`

**Interfaces:**
- Consumes: frozen V6 render/date behavior and V4 matchup-card seam.
- Produces: production NFL Spread V7 while preserving all non-Spread and mobile-nav behavior.

- [x] Add source-contract tests for additive V7 ownership and renderer restoration.
- [x] Implement V7 wrapper and preserve the tap-only overlay.
- [x] Verify focused suite locally.

### Task 3: Runless proof and finalization

**Files:**
- Create: `devsystem/runless_proof_plans/api2-nfl-spread-pro-intelligence-v1.json`

- [ ] Acquire isolated scope lease and exact thaw only for the previously frozen production overlay.
- [ ] Run exact-head Runless proof with focused + prior mobile/date regressions.
- [ ] Merge the exact certified candidate.
- [ ] Forward-port frozen registry, retire thaw, append canonical finalization ledger record, close durable Runless state to GREEN_FROZEN, release lease, and independently read back all terminal state.
