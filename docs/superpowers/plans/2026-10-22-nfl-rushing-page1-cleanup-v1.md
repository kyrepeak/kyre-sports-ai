# NFL Rushing Yards Page 1 Cleanup V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the frozen NFL Rushing Yards Page 1 into a compact, team-coded RB Market Board without changing its Kyre Sports API data contract or Page 2 architecture.

**Architecture:** Keep `nfl_rushing_yards_simple_rb_grid_v1.py` as the Page 1 owner. Add deterministic team-presentation metadata and semantic display helpers in that file, then render a single compact analytics strip and scouting strip per card. Preserve the existing gateway call, canonical query handoff, RB1/RB2 content, and upcoming-game behavior.

**Tech Stack:** Python, Streamlit HTML/CSS rendering, pytest, existing Kyre Sports API gateway.

**Spec:** `docs/superpowers/specs/2026-10-22-nfl-rushing-page1-cleanup-v1-design.md`

## Global Constraints
- Kyre Sports API remains the only application-facing NFL data gateway.
- Do not add SGO, ESPN, or ESPN BET anywhere in the production path.
- Do not change projection, probability, ranking, sportsbook selection, canonical identity, roster role, schedule filtering, or Page 2 analytics.
- Never convert missing/not-posted data into numeric zero.
- Preserve sportsbook-specific market integrity and semantic empty states.
- Preserve Page 1 upcoming-games-only and automatic weekly rollover behavior.
- Preserve canonical player/game query routing to Page 2.

## Review Focus
- Unknown or alias team abbreviation must use a safe glacier-blue fallback rather than malformed CSS.
- Very dark team colors must remain visible against the Kyre dark background.
- `MARKET_NOT_POSTED`, off-board, and unavailable market states must never fabricate line, edge, or model confidence.
- Mobile cards must keep four analytics values readable without horizontal scrolling.
- Whole-card navigation must retain exact canonical player/game/date query parameters after the visual rewrite.

---

### Task 1: Visual contract and team-theme helpers

**Files:**
- Modify: `nfl_rushing_yards_simple_rb_grid_v1.py`
- Create: `tests/test_api2_nfl_rushing_page1_cleanup_v1.py`

**Interfaces:**
- Consumes: existing `build_rb_card_html(card: Mapping[str, Any]) -> str`
- Produces: `team_theme(team_abbr: Any) -> dict[str, str]`, semantic class helpers, updated card HTML contract.

- [ ] **Step 1: Write the failing test**
  - Assert all 32 current NFL team abbreviations resolve to `primary`, `secondary`, and visible `accent` hex values.
  - Assert unknown teams return the glacier-blue fallback.
  - Assert an ATL card emits team CSS variables, a team accent rail class, one analytics strip, one scouting strip, and canonical Page 2 query parameters.
  - Assert the card suppresses inherited text decoration.

- [ ] **Step 2: Run the focused test to verify RED**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nfl_rushing_page1_cleanup_v1.py`
  - Expected: FAIL because the team theme and compact visual contract do not exist yet.

- [ ] **Step 3: Implement the smallest visual helper layer**
  - Add deterministic team theme metadata for all 32 teams and a safe fallback.
  - Add semantic CSS classes for positive, negative, pending, and rush-defense difficulty states.
  - Keep these presentation-only; do not make network calls.

- [ ] **Step 4: Run the focused test to verify GREEN**
  - Run the same pytest command.
  - Expected: PASS.

- [ ] **Step 5: Commit**
  - Commit message: `feat: add rushing team visual contract`

---

### Task 2: Compact RB Market Board card hierarchy

**Files:**
- Modify: `nfl_rushing_yards_simple_rb_grid_v1.py`
- Modify: `tests/test_api2_nfl_rushing_page1_cleanup_v1.py`

**Interfaces:**
- Consumes: `team_theme`, existing card payload fields and canonical handoff keys.
- Produces: compact identity row, analytics strip, scouting strip, semantic pending note.

- [ ] **Step 1: Extend the failing test**
  - Assert header copy is `KYRE AI · NFL RUSHING YARDS` and `RB Market Board`.
  - Assert verified cards show Market / Kyre / Edge / Model in one strip.
  - Assert `MARKET_NOT_POSTED` renders `LINE PENDING`, `WAIT`, and `Projection ready • sportsbook market not posted` with no `0`, `N/A`, or generic `Unavailable`.
  - Assert positive and negative edge/model states receive different semantic classes.
  - Assert only intentional action/name styling remains and general card content has no inherited underline.

- [ ] **Step 2: Run focused test to verify RED**
  - Expected: FAIL on current box-on-box card markup/header/pending state.

- [ ] **Step 3: Implement compact card/header CSS and markup**
  - Replace four standalone metric boxes with one `.kry1analytics` strip containing four cells separated by dividers.
  - Replace separate chips with one compact `.kry1scout` strip.
  - Move team logo/abbr into the identity row.
  - Add semantic pending note only when the market is not verified.
  - Reduce padding/gaps/card height while preserving mobile readability.

- [ ] **Step 4: Run focused test to verify GREEN**
  - Expected: PASS.

- [ ] **Step 5: Commit**
  - Commit message: `feat: compact rushing rb market board`

---

### Task 3: Frozen architecture regression and proof packaging

**Files:**
- Modify: `tests/test_api2_nfl_rushing_page1_cleanup_v1.py`
- Reuse: `tests/test_api2_nfl_rushing_yards_simple_rb_grid_v1.py`
- Create: `devsystem/runless_proof_plans/api2-nfl-rushing-page1-cleanup-v1.json`
- Create: `devsystem/task_ledgers/api2-nfl-rushing-page1-cleanup-v1.json`

**Interfaces:**
- Consumes: final Page 1 file and existing frozen architecture tests.
- Produces: exact-head Runless proof request inputs and freeze token `API2_NFL_RUSHING_PAGE1_CLEANUP_V1_FROZEN`.

- [ ] **Step 1: Add regression assertions**
  - Confirm no game selector is introduced.
  - Confirm `load_rushing_yards_slate` remains the only Page 1 data gateway.
  - Confirm banned provider strings are absent from the modified production path.
  - Confirm canonical Page 2 query handoff remains intact.

- [ ] **Step 2: Run focused + inherited frozen tests**
  - Run: `python -m pytest --noconftest -q tests/test_api2_nfl_rushing_page1_cleanup_v1.py tests/test_api2_nfl_rushing_yards_simple_rb_grid_v1.py`
  - Expected: all PASS.

- [ ] **Step 3: Add Runless proof plan and task ledger**
  - Bind commands, artifacts, source main SHA, one workstream, no GitHub Actions fallback, and freeze token.

- [ ] **Step 4: Request one exact-head Runless proof**
  - Require App 5204253 `runless-final-gate` success on the exact candidate SHA.
  - Do not issue duplicate proof requests or blind polling.

- [ ] **Step 5: Merge exact proven head and verify merged main**
  - Merge only the proven candidate head.
  - Verify merged-main Page 1 source still contains the team-theme/compact-card contract and the canonical routing owner still resolves Rushing Yards to the same Page 1.

- [ ] **Step 6: Finalize and freeze**
  - Bind the merged-main SHA, proof receipt, artifact map, and freeze token in Finalization Ledger V2.
  - Close out Runless to durable `GREEN_FROZEN`.
  - Release the execution lease.
