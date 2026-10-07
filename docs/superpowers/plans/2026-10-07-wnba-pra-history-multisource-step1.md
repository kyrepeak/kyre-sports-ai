# WNBA PRA History Multi-Source Step 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate `N/A PRA` from Recent Form and same-opponent H2H cards when verified per-game WNBA statistics exist.

**Architecture:** Add one read-only multi-source history adapter for Player Intelligence. ESPN remains one provider, while the official WNBA player profile runs in parallel as an independent verified source; missing PTS/REB/AST/MIN values are backfilled by exact game date/opponent without overwriting an already-present provider value. The existing single hosted Streamlit PRA-detail read remains unchanged and no model, projection, probability, ranking, sportsbook, or other-sport behavior changes.

**Tech Stack:** Python, requests, stdlib HTMLParser, existing WNBA registry helpers, pytest, Runless final gate.

**Spec:** User-approved WNBA Step 1/3 repair in the API2 workstream on 2026-10-07.

## Global Constraints

- Step 2A: one authoritative branch/PR/proof chain only.
- Base main SHA: `7e1d91948caf36e45535259bb5547689f211ce9a`.
- Do not modify WNBA model/projection/market/probability/qualification/ranking/sportsbook behavior.
- Do not modify non-WNBA sports.
- Keep the Streamlit hosted-read count at one.
- Official WNBA data and ESPN are independent history providers; neither may fabricate missing stats.
- Missing data still fails closed to `N/A` only after credible providers are exhausted.

## Review Focus

- Official WNBA HTML table shape changes must fail closed rather than invent values.
- Existing ESPN values must never be overwritten by fallback data.
- Date/opponent matching must prevent cross-game contamination.
- One-provider failure must not erase usable data from the other provider.
- Player/game history changes must not alter any model or sportsbook path.

---

### Task 1: Multi-source history adapter

**Files:**
- Create: `sports_api/wnba_pra_history_multisource_v1.py`
- Test: `tests/test_wnba_pra_history_multisource_v1_step1.py`

**Interfaces:**
- Consumes: `get_step3_espn_player_game_log_dataset(player_id: int, season: int) -> dict`
- Produces: `get_multisource_player_game_log_dataset(player_id: int, season: int) -> dict`

- [ ] Write failing tests for official WNBA recent-game parsing, exact-date/opponent backfill, provider-failure fallback, and no-overwrite behavior.
- [ ] Observe the tests fail because the adapter does not yet exist.
- [ ] Implement the minimal read-only adapter using bounded parallel ESPN + official WNBA profile reads.
- [ ] Run the focused tests and require PASS.
- [ ] Commit.

### Task 2: Activate adapter behind existing PRA-detail contract

**Files:**
- Modify: `sports_api/api/wnba_pra_detail_bundle.py`
- Test: existing `tests/test_wnba_pra_speed_v3_step3.py` plus Task-1 tests.

**Interfaces:**
- Consumes: `get_multisource_player_game_log_dataset(...)`
- Produces: unchanged `/api/v1/wnba/players/{player_id}/pra-detail` payload contract.

- [ ] Replace only the history-provider import with the multi-source adapter, aliased to the existing local callable name for compatibility.
- [ ] Add explicit `history_source_policy` metadata while preserving the existing compatibility source marker.
- [ ] Run focused regression tests and require PASS.
- [ ] Commit.

### Task 3: Runless closeout

**Files:**
- Create: `devsystem/runless_proof_plans/wnba-pra-history-multisource-v1-step1.json`
- Create: `devsystem/task_ledgers/wnba-pra-history-multisource-v1-step1.json`

- [ ] Prove the exact candidate head with the focused static test set.
- [ ] Require `runless-final-gate` SUCCESS on the exact candidate.
- [ ] Merge only the exact certified head.
- [ ] Reuse static proof after merge when content identity is unchanged and require merged-main `runless-final-gate` SUCCESS.
- [ ] Freeze token `WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1_FROZEN` and read back canonical state before claiming GREEN + FROZEN.
