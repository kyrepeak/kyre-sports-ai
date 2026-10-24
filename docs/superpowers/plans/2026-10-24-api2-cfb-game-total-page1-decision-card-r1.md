# CFB Game Total Page 1 Decision Card R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a simple premium selected-matchup decision card with Kyre projection/probability while preserving frozen model and Page 2 behavior.

**Architecture:** Add a read-only Kyre Sports API selected-game decision route that composes existing frozen model outputs. Add an A-tier V6 presentation successor over V5 and point the existing Page 1 bootstrap to V6.

**Tech Stack:** Python, FastAPI, Streamlit, existing CFB Game Total frozen model pipeline.

**Spec:** `docs/superpowers/specs/2026-10-24-api2-cfb-game-total-page1-decision-card-r1-design.md`

## Global Constraints
- Kyre Sports API is the only application-facing gateway.
- No SGO, ESPN, or ESPN BET.
- Frozen model/slate/final owners are read-only.
- Sportsbook projection influence remains 0.0.
- Page 2 remains untouched.

## Review Focus
- Missing model output must render MODEL PENDING rather than market probability.
- Integer market totals may have push probability; Over/Under must not be renormalized deceptively.
- Missing logo must use monogram fallback without hiding logos globally on mobile.
- Selected event must belong to the verified upcoming slate.
- No model/selection mutations may appear in V6 or the decision endpoint.

---

### Task 1: Decision endpoint
**Files:** Create `sports_api/api/cfb_game_total_page1_decision_v1.py`; modify `kyre_sports_api_vercel_v1.py`; test `tests/test_api2_cfb_game_total_page1_decision_card_r1.py`.
- [ ] Write RED API contract tests.
- [ ] Verify RED.
- [ ] Implement selected-game decision payload from frozen model outputs.
- [ ] Register additive router.
- [ ] Verify GREEN.

### Task 2: V6 decision card presentation
**Files:** Create `cfb_game_total_page1_atier_v6.py`; modify `cfb_game_total_page1_api_bootstrap_repair_r1.py`; test same contract file.
- [ ] Write RED presentation/activation assertions.
- [ ] Verify RED.
- [ ] Implement compact decision card and mobile logos.
- [ ] Activate V6 only for Page 1.
- [ ] Verify GREEN and relevant regressions/source policy.
