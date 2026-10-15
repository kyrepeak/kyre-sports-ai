# CFB Game Total Shell Integration Step 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep College Football -> Game Total Page 1 inside the shared KYRE SPORTS AI College Football shell without changing Game Total analytics or selected-event Page 2.

**Architecture:** Reuse the already-certified direct-shell pattern used by CFB Over/Under and Top Picks. The final Game Total wrapper will run the shared V1 shell only for the exact active CFB Game Total Page-1 route, temporarily adapt the shared CFB selector and exact Game Total renderer, and restore every patched seam in `finally`. All other routes continue through the frozen parent chain and selected-event Page 2 remains untouched.

**Tech Stack:** Python, Streamlit, pytest, existing MONSTER Runless final gate.

**Spec:** `docs/superpowers/specs/2026-10-14-cfb-game-total-shell-integration-step1-v1.md`

## Global Constraints

- Step 2A: one active problem and one authoritative mutation chain.
- Authoritative branch: `monster-cfb-game-total-shell-integration-step1-v1`.
- Do not modify `app.py` because an unrelated CFB Top Picks workstream currently owns it.
- Page-2 runtime remains `cfb_game_total_page2_step8_final_runtime_v1`.
- Page-1 content remains `cfb_game_total_clean_page_v43`.
- Sportsbook projection influence remains exactly `0.0`.
- No model, projection, probability, schedule, provider, identity, or other-sport changes.
- Use test-first RED -> minimal GREEN. Do not create a second proof path while the authoritative Runless path is valid.

## Review Focus

- Switching from Game Total to Moneyline/Over/Under/Top Picks must not leave stale Game Total query ownership behind; the selected CFB market must win.
- Exact selected-event Page 2 must bypass the new Page-1 shell bridge and keep its existing Step-8 runtime pointers.
- Root `st.selectbox`, `_render_nfl`, and route-module-prefix seams must restore even if the Page-1 render raises.
- The CFB market dropdown must include all four current options, not regress to the older three-market V77 tuple.
- Non-CFB and non-Game-Total routes must delegate to the frozen parent without invoking the new Game Total renderer.

---

### Task 1: Exact Game Total Page-1 shell ownership

**Files:**
- Create: `tests/test_cfb_game_total_shell_integration_step1_v1.py`
- Modify: `streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py`
- Create: `devsystem/task_ledgers/monster-cfb-game-total-shell-integration-step1-v1.json`

**Interfaces:**
- Consumes: `streamlit_memory_lazy_router_v1.render_app`, `streamlit_memory_lazy_router_v77._selectbox_v77`, current CFB market identities, `cfb_game_total_clean_page_v43.render_cfb_hub`, and existing Game Total route-query helpers from `streamlit_memory_lazy_router_v181`.
- Produces: an exact Page-1 bridge that preserves the shared CFB shell and delegates only College Football -> Game Total to V43; Page-2 behavior is unchanged.

- [ ] **Step 1: Write the failing regression test**

Add tests that require the final Game Total wrapper to:
- import/use the shared V1 shell and CFB selector adapter for Page 1;
- expose the four current CFB market options including Top Picks;
- route only exact CFB Game Total to `PAGE1_NATIVE_ROUTE` V43;
- delegate other routes to the frozen parent;
- restore root shell seams in `finally`;
- preserve the existing Page-2 pointer assignments unchanged.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_shell_integration_step1_v1.py`

Expected: FAIL because the current final router does not run Game Total Page 1 through the shared V1 shell and has no shell bridge/renderer restoration contract.

- [ ] **Step 3: Implement the minimal Page-1 shell bridge**

In `streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py`, add only the exact helpers necessary to:
- detect the active Game Total Page-1 route;
- run the shared V1 shell with a CFB selectbox bridge whose market options are `Moneyline`, `Over/Under`, `Game Total`, `Top Picks`;
- persist Game Total query identity while Game Total remains selected and clear it when another CFB market is selected;
- dispatch only exact College Football -> Game Total to `PAGE1_NATIVE_ROUTE` V43;
- restore the patched root shell functions/prefixes in `finally`;
- otherwise use the current frozen parent route unchanged.

Do not modify Page 2.

- [ ] **Step 4: Run focused + protected regression proof and verify GREEN**

Run at minimum:
`python -m pytest -q tests/test_cfb_game_total_shell_integration_step1_v1.py tests/test_cfb_game_total_native_routing_step1_v1.py tests/test_cfb_game_total_step8_page1_event_guard_r1.py tests/test_cfb_game_total_step8_route_pointer_lock_r1.py`

Expected: PASS. The repository-required `runless-final-gate` must also pass on the exact candidate head before merge.

- [ ] **Step 5: Record finalization state**

Create the task ledger with workstream ID, base SHA, authoritative branch/PR/head, exact scope, thaw/lease scope, RED evidence, GREEN proof, freeze token, protected surfaces, and finalization checklist. The final candidate head including the ledger must be re-proven by the same authoritative Runless path.

- [ ] **Step 6: Exact-head finalization**

Verify exact PR head -> required Runless proof -> merge exact head -> verify merged-main contains the intended files and no cross-workstream changes -> canonical read-back -> record Step 1 GREEN + FROZEN. Do not begin Step 2 automatically.
