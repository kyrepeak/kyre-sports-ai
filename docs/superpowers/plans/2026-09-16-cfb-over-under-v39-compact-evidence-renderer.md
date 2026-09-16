# CFB Over/Under V39 — Compact Evidence Renderer Implementation Plan

**Date:** 2026-09-16  
**Branch:** `fix/cfb-over-under-v39-compact-evidence-renderer`  
**Base main:** `f7c1594f0f37f785f0a1e48f4b40328c38fe1da5`  
**Approved scope:** presentation/evidence-state cleanup only. Frozen O/U projection/probability math, market influence, Game Total V153, Moneyline, and shared certified backend behavior stay unchanged.

## Goal

Replace the legacy lower-step renderer used by `cfb_over_under_clean_page_v38.py` with an additive V39 renderer that is compact, truthful, and readable on iPad/mobile. V39 must distinguish verified team identity from step-specific metric availability so verified Syracuse/Pittsburgh teams are never mislabeled as having unavailable identity merely because a red-zone/third-down/etc. provider row is missing.

## Frozen boundaries

- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`
- `MAY_MODIFY_PROJECTION = False`
- No projection, probability, threshold, ranking, or frozen step-engine formula changes.
- No Game Total V153 changes.
- No Moneyline changes.
- No shared Over/Under runtime/provider mutation unless a later test proves the presentation layer cannot solve the issue. Default implementation is V39-only.
- V38 remains the frozen presentation predecessor.

## Task 1 — RED contracts: additive/freeze + compact foundation

**Create:** `tests/test_cfb_over_under_v39_compact_evidence.py`

Write failing source/behavior contracts before V39 exists.

Required assertions:

1. `cfb_over_under_clean_page_v39.py` declares:
   - `FROZEN_PRESENTATION = "cfb_over_under_clean_page_v38"`
   - `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`
   - `MAY_MODIFY_PROJECTION = False`
2. V39 delegates analysis to V38/frozen runtime objects rather than implementing projection math.
3. Compact Matchup Foundation has a stable test marker and team logos capped at 56px desktop / smaller mobile.
4. Optional missing coach fields are omitted rather than rendering literal `Coach unavailable`.
5. Kickoff, venue, broadcast, and status are rendered as compact metadata chips/rows.
6. Steps 1–4 no longer call the inherited giant `_step1()` / `_step2()` renderer for the visible foundation.

Expected RED:

```bash
python -m pytest -q tests/test_cfb_over_under_v39_compact_evidence.py
```

Fails because `cfb_over_under_clean_page_v39.py` does not exist.

## Task 2 — RED contracts: truthful evidence-state semantics

**Create:** `tests/test_cfb_over_under_v39_evidence_states.py`

Define a display-only evidence-state adapter API, e.g. `_step_evidence_state(step, title, engine, identity_state)`.

Required behavior:

- Identity verified + engine has usable metrics/data -> `READY` (or preserves a certified non-blocking engine state).
- Identity verified + step-specific metric/provider data absent -> `CHECK`, with copy that says teams are verified and names the missing step evidence. It must not say team identity is unavailable.
- Identity genuinely unresolved -> `GATED` with an identity-specific reason.
- Frozen model engine status/reason is preserved separately as audit metadata; V39 never changes the engine result itself.
- Missing evidence is never fabricated.

Use deterministic Syracuse/Pittsburgh identity fixtures (`Syracuse`, `Pittsburgh`, exact IDs when available in the fixture) and missing red-zone/third-down engine rows to lock the screenshot symptom.

Expected RED:

```bash
python -m pytest -q tests/test_cfb_over_under_v39_evidence_states.py
```

Fails because V39 evidence-state functions do not exist.

## Task 3 — Implement V39 compact Steps 1–4

**Create:** `cfb_over_under_clean_page_v39.py`

Additive structure:

```text
V39
  -> imports/reuses V38 schedule, market, runtime, final-model, hero/quick-read helpers
  -> calls the same frozen runtime analysis
  -> replaces only the lower visible step renderer
```

Build:

- `_compact_foundation_html(game, away, home, ...)`
- compact team identity rows with 44–56px logos
- record/rank/conference retained
- no giant audit logo
- hide optional unavailable coach
- compact kickoff/venue/broadcast/status context
- Steps 2–4 summarized in small rows/cards using already-returned engine/result data

Do not reimplement calculation logic; read the returned result only.

Run Tasks 1–2 tests until the foundation subset turns green.

## Task 4 — Implement V39 truthful compact Steps 5–10

In `cfb_over_under_clean_page_v39.py` add:

- `_identity_state(...)`
- `_step_evidence_state(...)`
- `_compact_step_card(...)`
- `_render_compact_step_expanders(...)`
- one global frozen-model strip:
  `Frozen O/U math • Mutation OFF • Sportsbook 0.0%`

Presentation rules:

- `READY` = verified step evidence and meaningful numbers visible.
- `CHECK` = teams verified but this step's NCAA/provider evidence is unavailable/incomplete; frozen prior preserved.
- `GATED` = genuine identity/model blocker only.
- Each Step 5–10 expander defaults to `expanded=False`.
- Each expander contains a short human-readable summary first.
- Put inherited raw/frozen `_model_step()` output behind a nested collapsed `Model Audit` expander, not as the primary visible card.
- Do not repeat the sportsbook/mutation paragraph inside every step.

## Task 5 — Layout/responsive contracts

Extend `tests/test_cfb_over_under_v39_compact_evidence.py` with source/UI contracts:

- `@media(max-width:760px)` one-column reflow.
- no logo dimensions above 56px inside V39 compact step/foundation CSS.
- Steps 5–10 collapsed by default.
- nested `Model Audit` collapsed by default.
- one global sportsbook/freeze strip.
- no repeated literal `sportsbook projection weight: 0.0%` in each V39 step summary.
- V39 visible section order:
  Matchup Foundation -> What Moves the Total -> compact Step 5–10 expanders -> Steps 11–12 -> full-slate workspace.

## Task 6 — Route exact Over/Under to V39 additively

Identify the current production O/U page handoff from the active Streamlit/router stack and change only that exact Over/Under target from V38 to V39.

Add a route contract test if the handoff is source-addressable. All non-O/U routes must remain delegated unchanged.

No Game Total, Moneyline, MLB, WNBA, or NFL routing changes.

## Task 7 — Browser certification

**Create:** `devsystem/cfb_over_under_v39_browser_qa.py`  
**Create:** `.github/workflows/cfb-over-under-v39-compact-evidence.yml`

Launch the real production entrypoint (`app.py`) and use Playwright to navigate College Football -> Over/Under. For the 2026-09-17 Syracuse @ Pittsburgh target when available:

- verify compact foundation renders;
- verify both logos are visibly bounded, not giant;
- verify records `1-1` / `2-0` when deterministic evidence is available;
- verify no visible `Coach unavailable`;
- verify compact Steps 5–10 area;
- open Red Zone and Third Down expanders;
- if their step data is absent, require `CHECK` + verified-team wording rather than `identity unavailable`;
- verify nested Model Audit is collapsed by default;
- verify sportsbook influence remains `0.0%`;
- capture screenshot + JSON evidence;
- use desktop plus a tablet/mobile viewport contract to catch vertical/overflow regressions.

## Task 8 — Regression, Anti-Loop, merge, production proof

Run the new V39 lane plus relevant existing CFB/O-U regression tests found on current main. Do not resurrect stale historical workflow files that are absent from current main.

Before merge only:

1. Add exactly one changed task ledger under `devsystem/task_ledgers/` for V39, status `DONE`, matching the accepted Anti-Loop schema.
2. Require permanent contract / regression shield / CFB critical / DevSystem final gate green.
3. Merge protected-main PR only from the exact green head.
4. Run post-merge production verification.
5. Verify the deployed O/U lower section visually with screenshot evidence.
6. Close V39; do not recertify without a new contradictory production symptom.

## Finite execution board

1. Design/spec — GREEN
2. Implementation plan — GREEN after this document is committed
3. RED contracts — next
4. V39 implementation — after RED
5. Browser + regression certification
6. Anti-Loop + merge + production proof

## Definition of done

V39 is done only when the deployed O/U page shows compact Steps 1–10, verified team identity is not mislabeled as missing when only a step-specific metric is unavailable, the frozen model output is unchanged, sportsbook projection influence remains 0.0%, and production visual evidence confirms the reduced vertical footprint.