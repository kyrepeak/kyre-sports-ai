# NBA PRA Slate Completeness V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make NBA PRA Page 1 render correct Phoenix tip times, complete official team logos, stable player identity cards, and safe full-slate market/model coverage without SGO, ESPN, ESPN BET, line averaging, or guessed data.

**Architecture:** Keep Kyre Sports API as the only application-facing gateway. Fix schedule/UI field normalization at the gateway boundary, move team assets to official NBA CDN IDs, and replace Basketball-Reference per-player search fanout with bulk identity indexing plus bounded verified-history fallback. Preserve fail-closed analytics when no approved source can supply history.

**Tech Stack:** Python 3.13, FastAPI, Streamlit presentation helpers, pytest, httpx/requests.

**Spec:** User-approved NBA MULTI-SOURCE ROUTING RULE from the active conversation.

## Global Constraints
- Kyre Sports API is the only application-facing gateway.
- Never use SGO / SportsGameOdds.
- Never use ESPN or ESPN BET in request, fallback, enrichment, verification, assets, or production path.
- Preserve sportsbook, line, price, and timestamp; never average conflicting lines.
- Use only source-specific primary plus at most 1–2 approved secondary sources.
- Never fabricate missing data; explicit unavailable/PASS is valid only when approved sources cannot provide it.
- One branch, one PR, one Runless proof identity, one merge, one freeze chain.

## Review Focus
- Phoenix time conversion across EDT/EST while Arizona remains MST.
- All 30 NBA tricodes resolve to official NBA CDN logos and no ESPN domain appears in active PRA UI.
- Bulk player identity fallback does not create per-player search fanout or 429 storms.
- Every market player retains a stable Kyre ID and visible identity metadata when an approved source supplies it.
- Missing verified history remains fail-closed; no sportsbook line influences projection.

---

### Task 1: Schedule time + team identity contract
**Files:**
- Create: `nba_pra_team_identity_v1.py`
- Modify: `runless_v2/nba_pra_schedule_v1.py`
- Modify: `nba_pra_page1_ui_v2.py`
- Test: `tests/test_api2_nba_pra_slate_completeness_v1.py`

- [ ] Write RED tests for `tip_iso_phoenix` rendering and official NBA logo URLs.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement canonical NBA team IDs, official NBA CDN logo resolution, and Phoenix tip display normalization.
- [ ] Run focused tests until green.

### Task 2: Player identity + 429-safe fallback
**Files:**
- Modify: `runless_v2/nba_pra_player_context_v1.py`
- Test: `tests/test_api2_nba_pra_slate_completeness_v1.py`

- [ ] Write RED tests proving bulk Basketball-Reference identity resolution and no per-player search fanout for identity.
- [ ] Run tests and confirm expected failures.
- [ ] Add bulk season-index parsing and merge identity metadata before any bounded history fallback.
- [ ] Ensure stable Kyre IDs are emitted for every requested market player.
- [ ] Run focused tests until green.

### Task 3: Full-slate fail-closed completeness
**Files:**
- Modify only if required: `nba_pra_page1_api_only_v1.py`, `nba_pra_page1_v2.py`
- Test: `tests/test_api2_nba_pra_slate_completeness_v1.py`

- [ ] Add RED coverage assertions for every market line surviving into the board and explicit safe state when history is unavailable.
- [ ] Implement only the minimal source-of-truth changes required.
- [ ] Run NBA PRA regression suite, banned-provider scans, compile checks, and diff check.

### Task 4: Exact-head proof + freeze
- [ ] Commit exact candidate on the single authority branch.
- [ ] Push branch and open/update one PR only.
- [ ] Run one Runless V2 proof identity for exact head.
- [ ] Merge only after `runless-final-gate` passes.
- [ ] Verify Vercel production READY on merged main.
- [ ] Complete finalization ledger/freeze read-back and report GREEN + FROZEN only after durable `GREEN_FROZEN` state.
