# CFB Top Picks Page 2 Analytics Lab V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one adaptive, professional CFB Top Picks Page 2 that opens from a frozen Page 1 pick and provides verified market-specific analysis for Moneyline, Spread, Total, and Player Prop selections through Kyre Sports API only.

**Architecture:** Preserve Page 1 V4 ranking/selection/probability/price behavior and strengthen only its tap handoff with the already-owned `candidate_id` and selected slate date. Page 2 resolves that exact candidate first, then Kyre Sports API orchestrates narrowly scoped collectors for team/player analysis, sportsbook context, availability, model-owned Line Lab scenarios, verdict/drivers/risks, and source freshness. Streamlit is presentation-only for probabilities and scenarios.

**Tech Stack:** Python 3.13, FastAPI/APIRouter, Streamlit, existing Kyre Sports API collector patterns, pytest, Runless V2 proof/finalization, Vercel Runless deployment path.

**Spec:** `docs/superpowers/specs/2026-10-22-cfb-top-picks-page2-analytics-lab-v1-design.md`

## Global Constraints

- Kyre Sports API is the only application-facing API/data gateway.
- Never request, enrich, verify, fall back to, or ship SGO, ESPN, or ESPN BET.
- Preserve sportsbook, market, selection, line, price, and observed timestamp independently; never average conflicting sportsbook lines.
- Never convert missing/null/unknown data into numeric zero.
- Never fabricate projections, history, availability, line movement, or alternate-line probabilities.
- Page 1 V4 ranking, selection, probability, sportsbook quote, and identity enrichment stay frozen except for the sanctioned candidate-ID/slate-date handoff change.
- Page 2 identity is candidate-first; URL player/team strings are display-only and never canonical identity.
- Each module uses one strongest primary source class and at most 1–2 appropriate fallback/verification sources when needed.
- Streamlit never recomputes model probabilities; Line/Price Lab switches only among API/model-owned scenarios.
- Weather does not influence V1 verdicts until an approved Kyre Sports API weather-provider contract exists.
- Step 2A: one active workstream, one branch/PR, one authoritative proof path, exact-head verification, no duplicate proof submissions, classify failures before patching, then only one successor proof.
- Vercel Runless only; do not introduce Render.

## Review Focus

1. **Tampered handoff:** a valid-looking event/player URL with an invalid `candidate_id` must stop at `IDENTITY_UNAVAILABLE`, never fuzzy-match another pick. Task 1 pins this.
2. **Provider degradation:** one unavailable sportsbook/stat/availability provider must degrade only the owned module while unrelated Page 2 modules remain renderable. Tasks 3–6 pin this.
3. **Real zero vs missing:** `0` reported by an approved source must survive, while `None`/missing must stay unavailable and never normalize to zero. Tasks 2–6 pin this.
4. **Cross-book movement contamination:** opening/current movement from different sportsbooks must never be combined into one movement claim. Task 5 pins this.
5. **Page 1 regression:** adding `candidate_id` to the handoff must not change the frozen top-10 rows, ordering, probability, price, or rendering outside the URL. Tasks 1 and 8 pin this.

---

### Task 1: Candidate-First Handoff and Canonical Page 2 Identity

**Files:**
- Modify: `cfb_top_picks_page_v15.py`
- Create: `sports_api/collectors/cfb_top_picks_page2_identity_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_identity_v1.py`
- Regression: `tests/test_api2_cfb_top_picks_page1_cleanup_v4.py`

**Interfaces:**
- Consumes: Page 1 V4 rows containing `candidate_id`, `event_id`, selected date, market/selection/book/price, and verified player/team identity.
- Produces: `resolve_selected_candidate(candidate_id: str, selected_date: str) -> dict[str, Any]` with exact `selection_snapshot`, canonical game/team/player IDs, or `IDENTITY_UNAVAILABLE`.

- [ ] **Step 1: Write failing tests**
  - `test_page1_handoff_includes_exact_candidate_id_and_selected_date`
  - `test_exact_candidate_resolves_from_page1_v4_inventory`
  - `test_tampered_candidate_id_returns_identity_unavailable`
  - `test_player_url_text_cannot_override_verified_candidate_identity`
  - `test_real_zero_values_survive_identity_normalization`

- [ ] **Step 2: Run the identity tests and confirm RED**
  - Run: `python -m pytest --noconftest -q tests/test_api2_cfb_top_picks_page2_identity_v1.py`
  - Expected: failures because resolver/handoff contract does not yet exist.

- [ ] **Step 3: Implement the minimum candidate-first resolver and Page 1 handoff update**
  - Add `top_pick_id=<candidate_id>` and `top_pick_date=<selected_date>` to V15 handoff.
  - Resolve only by exact candidate ID within Page 1 V4 inventory for the supplied slate date.
  - Never infer identity from player/team/selection query strings.

- [ ] **Step 4: Run identity + Page 1 frozen regression tests**
  - Run: `python -m pytest --noconftest -q tests/test_api2_cfb_top_picks_page2_identity_v1.py tests/test_api2_cfb_top_picks_page1_cleanup_v4.py`
  - Expected: PASS; Page 1 ordering/probability/price assertions unchanged.

- [ ] **Step 5: Commit Task 1**
  - Commit message: `feat: add exact Top Picks Page 2 handoff identity`

### Task 2: Page 2 API Contract and Module Status Orchestrator

**Files:**
- Create: `sports_api/api/cfb_top_picks_page2_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_contract_v1.py`

**Interfaces:**
- Consumes: `resolve_selected_candidate(candidate_id, selected_date)` from Task 1.
- Produces: `build_page2_payload(candidate_id: str, selected_date: str) -> dict[str, Any]` and `router = APIRouter(prefix="/api/v1/cfb/top-picks", tags=["cfb"])` with `GET /page2`.

- [ ] **Step 1: Write failing contract tests**
  - Require schema `cfb_top_picks_page2_v1`, service `Kyre Sports API`, `selection_snapshot`, and all 15 deep-analysis modules from the spec.
  - Require each module status to be one of `READY`, `PARTIAL`, `DATA_UNAVAILABLE`, `NOT_APPLICABLE`, `SOURCE_DEGRADED`, `IDENTITY_UNAVAILABLE`.
  - Require `None` to remain unavailable and explicit source zero to remain `0`.

- [ ] **Step 2: Run contract tests and confirm RED**
  - Run: `python -m pytest --noconftest -q tests/test_api2_cfb_top_picks_page2_contract_v1.py`

- [ ] **Step 3: Implement the orchestration skeleton**
  - Return identity-backed `selection_snapshot` first.
  - Expose module envelopes with explicit statuses; do not invent placeholder numeric values.
  - Stop deep collection on identity failure while preserving safe Back-to-Top-Picks response metadata.

- [ ] **Step 4: Run contract tests to GREEN**

- [ ] **Step 5: Commit Task 2**
  - Commit message: `feat: add CFB Top Picks Page 2 API contract`

### Task 3: Game-Pick Analysis, Projection, Drivers, and Risks

**Files:**
- Create: `sports_api/collectors/cfb_top_picks_page2_team_analysis_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_team_analysis_v1.py`

**Interfaces:**
- Consumes: canonical game/team identity and frozen selected market from `selection_snapshot`.
- Produces: `build_team_analysis(snapshot: Mapping[str, Any]) -> dict[str, Any]` containing market-aware `projection`, `drivers`, `matchup`, `recent_form`, `history`, `risks`, `flip_conditions`, plus diagnostics/source timestamps.

- [ ] **Step 1: Write failing tests for Moneyline, Spread, and Total**
  - Moneyline emphasizes win probability/fair price/team matchup.
  - Spread emphasizes projected margin/fair spread/cover context.
  - Total emphasizes projected total/pace/scoring environment.
  - Missing source values remain unavailable; approved-source real zero stays zero.
  - One degraded source must not erase other ready modules.
  - No ESPN/SGO provider names may appear in routing/diagnostics.

- [ ] **Step 2: Run team-analysis tests and confirm RED**

- [ ] **Step 3: Implement minimum routed analysis using existing approved-source collectors where safe**
  - Reuse calculations/data only if they are provider-compliant and identity-safe.
  - Do not reuse the old ESPN-bound Top Picks detail identity transport.

- [ ] **Step 4: Run tests to GREEN**

- [ ] **Step 5: Commit Task 3**
  - Commit message: `feat: add market-aware Top Picks game analysis`

### Task 4: Player Prop Analysis and Current-Roster Verification

**Files:**
- Create: `sports_api/collectors/cfb_top_picks_page2_prop_analysis_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_prop_analysis_v1.py`

**Interfaces:**
- Consumes: canonical player/current-team/opponent identity from Task 1 plus selected prop market/line/side.
- Produces: `build_prop_analysis(snapshot: Mapping[str, Any]) -> dict[str, Any]` with projection, recent form, usage, matchup, relevant history, availability inputs, drivers, risks, and flip conditions.

- [ ] **Step 1: Write failing prop tests**
  - Current roster identity must match selected game.
  - Historical stats preserve historical school identity.
  - Only market-relevant usage metrics render.
  - Similar-name/cross-team player contamination is rejected.
  - Missing optional history stays unavailable, not zero/fabricated.

- [ ] **Step 2: Run tests and confirm RED**

- [ ] **Step 3: Implement prop analysis with field-specific approved routing/fallback**

- [ ] **Step 4: Run tests to GREEN**

- [ ] **Step 5: Commit Task 4**
  - Commit message: `feat: add verified Top Picks player prop analysis`

### Task 5: Sportsbook Market Board and Line Movement

**Files:**
- Create: `sports_api/collectors/cfb_top_picks_page2_market_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_market_v1.py`

**Interfaces:**
- Consumes: exact selected game/player market identity.
- Produces: `build_market_context(snapshot: Mapping[str, Any]) -> dict[str, Any]` with independent sportsbook quotes, like-for-like best price, and sportsbook-specific movement observations.

- [ ] **Step 1: Write failing market-integrity tests**
  - Preserve independent FanDuel/DraftKings/etc. quotes; never average.
  - Best price compares like-for-like line/selection only.
  - Movement requires same sportsbook + event + market + selection identity.
  - Cross-book opening/current pair must return movement unavailable.
  - Provider failure falls to only the next appropriate approved provider.

- [ ] **Step 2: Run tests and confirm RED**

- [ ] **Step 3: Implement market board/movement collector**

- [ ] **Step 4: Run tests to GREEN**

- [ ] **Step 5: Commit Task 5**
  - Commit message: `feat: add exact-book Top Picks market context`

### Task 6: Availability, Kyre Verdict, and Price/Line Lab Scenarios

**Files:**
- Create: `sports_api/collectors/cfb_top_picks_page2_availability_v1.py`
- Create: `sports_api/collectors/cfb_top_picks_page2_decision_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_decision_v1.py`

**Interfaces:**
- Consumes: selection snapshot + Tasks 3/4/5 analysis + approved current availability.
- Produces:
  - `build_availability_context(snapshot: Mapping[str, Any]) -> dict[str, Any]`
  - `build_decision_modules(snapshot: Mapping[str, Any], analysis: Mapping[str, Any], market_context: Mapping[str, Any], availability: Mapping[str, Any]) -> dict[str, Any]`
  - Decision modules: `kyre_verdict`, `line_lab`, normalized drivers/risks/flip conditions.

- [ ] **Step 1: Write failing decision tests**
  - Outcome confidence is distinct from market value.
  - `PASS AT THIS PRICE` is possible even for a high-probability favorite.
  - Moneyline Price Lab changes implied/value context but never model win probability.
  - Spread/Total/Prop Line Lab exposes only model-owned supplied scenarios.
  - If no certified scenario generator exists, status is `DATA_UNAVAILABLE`.
  - High-impact availability used in verdict must carry verified source/freshness metadata.

- [ ] **Step 2: Run tests and confirm RED**

- [ ] **Step 3: Implement availability and decision/scenario modules**

- [ ] **Step 4: Run tests to GREEN**

- [ ] **Step 5: Commit Task 6**
  - Commit message: `feat: add Top Picks verdict and model-owned line lab`

### Task 7: Complete Page 2 API Assembly and Provider-Failure Isolation

**Files:**
- Modify: `sports_api/api/cfb_top_picks_page2_v1.py`
- Test: `tests/test_api2_cfb_top_picks_page2_integration_v1.py`

**Interfaces:**
- Consumes: collectors from Tasks 1, 3, 4, 5, 6.
- Produces: final `cfb_top_picks_page2_v1` payload matching the spec for all four market families.

- [ ] **Step 1: Write failing integration tests**
  - One fixture each for ML, Spread, Total, Player Prop.
  - Module status isolation under one-provider failure.
  - No forbidden providers in source graph.
  - No silent blank required fields.
  - Source/freshness audit covers every material rendered claim.

- [ ] **Step 2: Run integration tests and confirm RED**

- [ ] **Step 3: Wire the collectors into the orchestrator**
  - Do not call prop collectors for game picks or team collectors for props when not applicable.

- [ ] **Step 4: Run all Page 2 API tests to GREEN**

- [ ] **Step 5: Commit Task 7**
  - Commit message: `feat: assemble adaptive Top Picks Page 2 payload`

### Task 8: Adaptive Streamlit Analytics Lab and Back Navigation

**Files:**
- Create: `cfb_top_picks_page_v16.py`
- Create: `streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v1.py`
- Modify under sanctioned thaw only if required: `app.py`
- Test: `tests/test_api2_cfb_top_picks_page2_ui_v1.py`
- Regression: `tests/test_api2_cfb_top_picks_page1_cleanup_v4.py`

**Interfaces:**
- Consumes: `GET /api/v1/cfb/top-picks/page2?candidate_id=...&selected_date=...`.
- Produces: adaptive Page 2 UI with the exact section order from the spec and a slate-preserving Back to Top Picks route.

- [ ] **Step 1: Write failing UI tests**
  - Exact selected hero renders identity/book/price/probability.
  - ML uses Price Lab; Spread/Total/Prop use appropriate Line Lab labels/data.
  - Deep WHY appears only on Page 2.
  - Unavailable optional modules collapse cleanly without raw `None`/`0` substitution.
  - Back route preserves slate date.
  - No indented top-level HTML tags/raw HTML leakage.
  - Tablet/mobile responsive contract markers exist.

- [ ] **Step 2: Run UI tests and confirm RED**

- [ ] **Step 3: Implement V16 Page 2 presentation and runtime dispatch**
  - Staged loading: identity/hero first, then deep analytics.
  - Streamlit only displays API-owned scenario values; no model math in renderer.

- [ ] **Step 4: Run UI + Page 1 regression tests to GREEN**

- [ ] **Step 5: Commit Task 8**
  - Commit message: `feat: render CFB Top Picks adaptive analytics lab`

### Task 9: Shared Registration, Source Policy, Runless Proof, and GREEN + FROZEN Closeout

**Files:**
- Modify under scope lease: `kyre_sports_api_vercel_v1.py`
- Modify under scope lease/thaw only if required: `app.py`
- Create: `devsystem/cfb_top_picks_page2_analytics_source_policy_v1.py`
- Create: `devsystem/runless_proof_plans/api2-cfb-top-picks-page2-analytics-lab-v1.json`
- Create/update task ledger for `api2-cfb-top-picks-page2-analytics-lab-v1`
- Test: all Page 2 tests + bounded frozen Page 1/navigation regressions.

**Interfaces:**
- Consumes: completed candidate from Tasks 1–8.
- Produces: registered production endpoint/UI route, source-policy proof, Runless authorization, exact-head merge, finalization-ledger record, frozen-registry forward-port, durable `GREEN_FROZEN`, released lease.

- [ ] **Step 1: Acquire one Step 2A scope lease from then-current exact main**
  - Scope only Page 2 files plus the shared registration resources actually required.
  - If another workstream owns `app.py`, API router, or `vercel:kyre-sports-api`, enter WAIT-NOT-FAIL; never steal an active lease.

- [ ] **Step 2: Open sanctioned thaw(s) for any frozen files that must change**
  - Expected likely thaw: `cfb_top_picks_page_v15.py` handoff-only change.
  - Open `app.py` thaw only if registration requires changing its frozen blob.
  - Preserve all unrelated active thaws byte-for-byte.

- [ ] **Step 3: Register Page 2 API/router/runtime on the same one branch/PR**

- [ ] **Step 4: Run the authoritative local proof plan fresh**
  - Page 2 unit/integration/UI tests.
  - Frozen Page 1 V4/V3 regressions.
  - Navigation regressions.
  - Source policy: fail on SGO/ESPN/ESPN BET, forbidden scope, line averaging, null-to-zero, or Streamlit probability recompute patterns.
  - `py_compile` all changed Python files.
  - Expected: 0 failures.

- [ ] **Step 5: Verify exact candidate preview**
  - Exercise one live ML pick, one Spread/Total game pick if available, and one Player Prop from verified Page 1 inventory.
  - Verify exact candidate identity, Kyre Sports API ownership, source statuses, no forbidden providers, exact sportsbook preservation, and no raw HTML leakage.

- [ ] **Step 6: Submit exactly one canonical Runless proof for the exact candidate SHA**
  - Wait for terminal result; no duplicate polling/submission.
  - On deterministic failure: classify root cause, patch same branch, rerun local proof, then submit exactly one successor proof.

- [ ] **Step 7: Merge only the Runless-authorized exact head**
  - Require protected `runless-final-gate` success and expected-head merge guard.

- [ ] **Step 8: Forward-port frozen registry + write one atomic finalization-ledger transaction**
  - Freeze token: `API2_CFB_TOP_PICKS_PAGE2_ANALYTICS_LAB_V1_FROZEN`.
  - Record exact candidate SHA, merged-main SHA, artifact blobs, proof receipt, source-policy state, and preserved unrelated thaws.

- [ ] **Step 9: Run Runless closeout and fresh independent readback**
  - Require durable `state=GREEN_FROZEN`, `failure_class=NONE`, matching merged-main SHA/freeze token/manifest hash.
  - Verify production Kyre Sports API/Runless/finalizer deployments are READY on exact merged main.

- [ ] **Step 10: Release only this workstream's scope lease and verify holder removal**

- [ ] **Step 11: Final completion verification**
  - Fresh Page 2 tests + frozen Page 1 regressions + source policy + compile.
  - Fresh finalization manifest, frozen registry, lease state, durable Runless row, and production exact-SHA readback.
  - Only then report `100% GREEN + FROZEN`.

## Implementation Order / Checkpoints

1. Identity + Page 1 handoff — candidate authority exists.
2. API skeleton — stable response/status contract exists.
3. Game analysis — ML/Spread/Total deep modules work.
4. Prop analysis — player-specific deep modules work.
5. Market board/movement — exact-book context works.
6. Verdict/availability/Line Lab — decision layer works without UI-owned math.
7. API integration — all four market families produce one schema.
8. UI — adaptive analytics lab renders safely.
9. Shared registration/proof/freeze — production becomes authoritative.

No task may claim GREEN + FROZEN independently. The only terminal GREEN + FROZEN claim is Task 9 after exact-head merge, finalization ledger, registry, closeout, lease release, production verification, and fresh completion tests.
