# NFL RB/WR Render Repair Step 1 — Root Cause Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Certify and freeze the exact root cause of the broken NFL Rushing Yards and Receiving Yards card presentation without mutating product runtime.

**Architecture:** Treat Step 1 as a diagnostic-only control-plane change. Prove current route ownership, map the screenshot text to the existing card builders, prove those cards depend on Markdown-injected CSS for block/grid layout, and pin the existing browser-verifier gap that allows DOM/text presence to pass while computed presentation is broken. Step 2 owns the presentation transport repair; Step 1 must not patch RB/WR runtime files.

**Tech Stack:** Python, pytest, Streamlit source contracts, Runless Proof Plane, MONSTER frozen registry.

**Spec:** User-visible NFL RB/WR render regression shown in the 2026-10-08 mobile screenshots; five-step repair mission, Step 1 = root-cause/rendering diagnosis.

## Global Constraints

- Repository: `kyrepeak/kyre-sports-ai`.
- Exact source main: `a1dfac558c76253f99e2279dd7cb45e944d913a6`.
- Frozen registry baseline: revision `206`, state hash `cca4b20727ef97ef8e720c2bd0b1905e85b3de383331fc862a6fda4b273b7cd6`.
- Step 2A scope lease: `SCOPE-LEASE-28512CFB5B1FCAD2EF7399E6`.
- Product-runtime mutations in Step 1: `0`.
- Frozen-source mutations in Step 1: `0`.
- GitHub Actions fallback: `0`.
- Required proof check: `runless-final-gate`, GitHub App ID `5204253`.
- One authoritative branch, PR, Runless proof chain, merge, and freeze chain only.
- Preserve all unrelated active thaws exactly.
- Do not claim a specific Streamlit release caused the regression without evidence.

## Review Focus

- Rushing route ownership must still resolve to the V15 surface that inherits the V4 compact cards.
- Receiving route ownership must still resolve to V16, which preserves V15/V13 presentation ancestry.
- Screenshot signatures must map to the exact existing card labels, proving this is not a data/API substitution bug.
- CSS declarations must be the elements that convert the card metric `<b>` and `<span>` children from browser-default inline flow into the intended block/grid layout.
- Existing browser proof must be shown to lack a computed-style assertion, explaining how DOM/text presence could pass while presentation regressed.

---

### Task 1: Characterize route and screenshot ownership

**Files:**
- Create: `tests/test_nfl_rb_wr_render_repair_step1_root_cause.py`
- Read only: `streamlit_memory_lazy_router_v111.py`
- Read only: `streamlit_memory_lazy_router_v147.py`
- Read only: `nfl_rushing_yards_hub_v4.py`
- Read only: `nfl_receiving_yards_hub_v13.py`
- Read only: `nfl_receiving_yards_hub_v16.py`

**Interfaces:**
- Consumes: current main route modules and frozen presentation owners.
- Produces: deterministic source-level proof that the screenshots came from the current RB/WR render chain.

- [ ] Assert Rushing routes to `nfl_rushing_yards_hub_v15` and the V4 owner contains every broken-screen metric label.
- [ ] Assert Receiving routes to `nfl_receiving_yards_hub_v16`, V16 preserves V15, and V13 contains every broken-screen matchup/metric label.

### Task 2: Prove presentation-transport failure class

**Files:**
- Test: `tests/test_nfl_rb_wr_render_repair_step1_root_cause.py`
- Read only: `nfl_rushing_yards_hub_v4.py`
- Read only: `nfl_receiving_yards_hub_v13.py`
- Read only: `nfl_prop_analytics_page2_responsive_polish_v1.py`

**Interfaces:**
- Consumes: card CSS and the repository's already-certified hardened HTML transport precedent.
- Produces: root-cause classification `STREAMLIT_MARKDOWN_PRESENTATION_TRANSPORT`.

- [ ] Assert RB and WR cards rely on CSS `display:block` / grid declarations for their visual hierarchy.
- [ ] Assert both broken owners inject their CSS through `st.markdown(..., unsafe_allow_html=True)`.
- [ ] Assert the previously repaired NFL Prop Analytics surface uses `st.html(...)` for presentation CSS transport.

### Task 3: Pin the verifier gap

**Files:**
- Test: `tests/test_nfl_rb_wr_render_repair_step1_root_cause.py`
- Read only: `devsystem/nfl_rushing_yards_html_render_browser_v1.py`

**Interfaces:**
- Consumes: existing browser witness.
- Produces: proof that current certification checks DOM/text presence but not computed layout/style.

- [ ] Assert the existing witness does not call `getComputedStyle`.
- [ ] Record the secondary root cause as `COMPUTED_STYLE_VERIFIER_GAP`.

### Task 4: Run one exact-head Runless proof

**Files:**
- Create: `devsystem/execution_plans/nfl-rb-wr-render-repair-step1-root-cause.json`
- Create: `devsystem/runless_proof_plans/nfl-rb-wr-render-repair-step1-root-cause.json`
- Create: `devsystem/task_ledgers/nfl-rb-wr-render-repair-step1-root-cause.json`

**Interfaces:**
- Consumes: exact candidate head, live Step 2A lease, frozen registry revision 206.
- Produces: one immutable Runless receipt and successful `runless-final-gate` on the exact candidate.

- [ ] Compile the source owners and run only the focused diagnostic test through Runless.
- [ ] Do not dispatch GitHub Actions or a duplicate proof request.
- [ ] Merge only the exact Runless-certified head.

### Task 5: Freeze and release authority

**Files:**
- Control-plane only; no product runtime mutation.

**Interfaces:**
- Consumes: exact merged-main identity and Runless terminal receipt.
- Produces: frozen registry checkpoint `NFL_RB_WR_RENDER_REPAIR_V1_STEP1_ROOT_CAUSE_FROZEN` plus released diagnostic scope authority.

- [ ] Verify merged main is the exact authorized merge result.
- [ ] Transactionally register/read back the Step 1 frozen checkpoint.
- [ ] Release the Step 1 scope lease after terminal truth is durable.
- [ ] Mark Step 1 GREEN + FROZEN only after exact registry read-back succeeds.

## Step 2 Handoff

Step 2 may repair presentation transport and add computed-style mobile proof. It must use a fresh Step 2A authorization/lease and must not inherit mutation authority from Step 1.
