# CFB Player Props Page 1 Live Slate R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CFB Player Props Page 1 automatically render the first verified upcoming CFB slate and its games instead of selecting a date through fallback discovery and then rendering zero games from a different schedule source.

**Architecture:** Keep official game identity strict, but make next-date discovery and returned games come from one resilient schedule pipeline. Prefer the current Schedule V4 owner; if the authoritative loader is temporarily empty, continue the bounded date scan instead of returning a date with no renderable games.

**Tech Stack:** Python, Streamlit, existing CFB schedule stack, pytest, Runless V2.

**Spec:** User-approved repair direction in conversation plus `docs/superpowers/plans/2026-10-19-cfb-player-props-page1-v1.md`.

## Global Constraints
- Page 1 only; no Page 2 or Page 3 implementation.
- Do not fabricate games, players, props, probabilities, or sportsbook observations.
- Game cards must render even when sportsbook prop feeds are empty.
- Preserve official/verified identity requirements and 0.0 sportsbook influence on projection.
- Hard Step 2A, anti-loop, exact-head proof, merge, freeze/read-back, and lease release are mandatory.

## Review Focus
- Off-day today with a valid slate later in the scan window must skip forward and return the later games.
- A successful schedule read must never be discarded by a second fetch for the same selected date.
- Provider outage on one date must not abort the bounded date scan.
- Schedule V4 team/event IDs and rankings must survive normalization.
- Games with zero posted props must still render as games with truthful empty prop coverage.

---

### Task 1: Reproduce and pin the empty-slate boundary bug
**Files:**
- Create: `tests/test_cfb_player_props_page1_live_slate_r1.py`
- Modify: `cfb_player_props_page1_slate_v1.py`

**Interfaces:**
- Consumes existing schedule loaders and `normalize_page1_game`.
- Produces `load_next_player_prop_slate()` returning one internally consistent `{state, slate_date, games, source}` object.

- [x] Write failing tests proving Page 1 uses the current schedule owner and a successful schedule read is preserved.
- [x] Run RED and verify the failure is the current V1/two-pass behavior.
- [x] Implement the minimal one-pipeline resolver using Schedule V4.
- [x] Run focused tests GREEN.

### Task 2: Live schedule regression and Page-1 compatibility
**Files:**
- Modify: `tests/test_cfb_player_props_page1_integration_v1.py`
- Modify: `tests/test_cfb_player_props_page1_slate_v1.py`
- Test: `tests/test_cfb_player_props_page1_live_slate_r1.py`

- [x] Verify current upcoming date scan returns a non-empty verified slate when providers expose one.
- [x] Run Page-1 slate/handoff/composition + current CFB schedule regressions.
- [x] Verify no Page 2/3 or model math changes.

### Task 3: Control-plane closeout
**Files:**
- Create: `devsystem/runless_proof_plans/monster-cfb-player-props-page1-live-slate-r1.json`
- Create: `devsystem/task_ledgers/monster-cfb-player-props-page1-live-slate-r1.json`

- [x] Seal exact proof commands and local evidence.
- [ ] One PR, one exact-candidate proof, expected-head merge.
- [ ] Finalization Ledger V2 freeze/read-back, thaw/forward-port only if required.
- [ ] Runless `GREEN_FROZEN`, release lease, read back absent.
