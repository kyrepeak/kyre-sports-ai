# Universal Navigation Loading V2 — Implementation Plan

**Goal:** Eliminate visible outgoing-page bleed during slow navigation while skipping the loader for fast transitions.

- [x] Step 1 — Step 2A discovery: pin current main, confirm no competing PR, locate frozen Atomic Navigation V1 owner, and acquire disjoint scope lease.
- [x] Step 2 — TDD RED: add destination-name, delayed-loader, singleton, real Streamlit script-state, and terminal-inheritance regressions; confirm failure before implementation.
- [x] Step 3 — Add pure V2 helper with page-name mapping, 140 ms delay contract, opaque browser controller, and server fallback.
- [x] Step 4 — Add Runtime V2 preserving Runtime V5 generation/scope commit guards and disabling background prefetch.
- [x] Step 5 — Activate V2 by changing only the inherited NFL Daily Picks V3 Atomic Navigation runtime import; leave `app.py`, V4, NBA PRA terminal, and V1 parent implementations untouched.
- [x] Step 6 — TDD GREEN: focused local harness and py_compile.
- [ ] Step 7 — Reconcile same branch with latest `main` if required, then open exactly one PR.
- [ ] Step 8 — Run exactly one authoritative Runless V2 proof on the exact reconciled PR head and require `runless-final-gate` SUCCESS from App 5204253.
- [ ] Step 9 — Expected-head merge; verify merged `main`.
- [ ] Step 10 — Append immutable Finalization Ledger V2 successor freeze, read it back, Runless closeout to `GREEN_FROZEN`, release exact scope lease, and stop.

**Freeze token:** `MONSTER_UNIVERSAL_NAVIGATION_LOADING_V2_FROZEN`

**Parent freeze:** `MONSTER_UNIVERSAL_ATOMIC_NAVIGATION_V1_FROZEN`
