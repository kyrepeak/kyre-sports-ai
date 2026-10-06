# API 2 Task 16 Final Mobile + System Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close API 2 Task 16/16 with verification-only mobile/browser and full-system certification for the final NFL Game Totals V10 route, without changing product/model/runtime behavior.

**Architecture:** Add one deterministic certification owner that audits the frozen Game Totals runtime chain, mobile-recovery contract, routing, sportsbook firewall, and Runless fallback/protection state. Add one regression test and one task ledger. Browser proof is evidence-only and must not modify runtime code; any defect discovered must stop certification and be separately scoped before repair.

**Tech Stack:** Python 3, pytest, Playwright/Chromium for responsive proof, GitHub protected-main, Runless Proof Plane.

**Spec:** `docs/superpowers/specs/2026-09-15-nfl-game-totals-multisource-data-router-design.md`

## Global Constraints

- Verification-only Task 16; no product/runtime/model/router change unless a certification test proves a narrowly scoped defect.
- `sports_api/nfl_game_totals_total_projection_v1.py` stays frozen at blob `0738d4f9e995c9d1423118b8fc9a95a799c8c55d`.
- `nfl_hub_v18.py` stays frozen at blob `dfcf29636a10c798de037378624188f245f657e2`.
- Task-15 owners stay frozen: V9 `0f9e48384daf8b4f79f2edabdf9d234f90d19076`, V10 `c22485c186e2f53c3b0a6b1302375dd9bb25468a`, market-read helper `ca86561ffbb329f686df752afdfc95da1f210ba3`, V36 `97bd832a46cf5bdab1b8a1e6162a8c9282dfeb01`, Router V97 `e5fffd68c08365a1abd7c449c1aa1a98aef177a6`.
- V8.1 mobile recovery stays frozen at blob `686cbe7eac7b35398dc754a04f8cdec218f76c6a`.
- Sportsbook projection influence remains exactly `0.0%`; stake sizing OFF; wager actions OFF.
- Adjacent NFL Moneyline, Spread, Passing, Rushing, and Receiving behavior remains untouched.
- Exact-head `runless-final-gate` must be SUCCESS before merge; merged-main identity and protection must be read back before GREEN + FROZEN.

## Review Focus

- Empty-today mobile state must expose a bounded next-game recovery path instead of a blank dead end.
- Reload must clear only Game Totals/router caches, never global Streamlit state.
- Final V10 route must remain V97 -> V36 -> V10 while all non-Game-Total markets preserve their frozen chain.
- Responsive final-read content must not create horizontal overflow at 390, 768, or 1440 CSS-pixel viewports.
- Any frozen blob drift, sportsbook influence above 0.0%, or enabled wager/stake action must fail certification closed.

---

### Task 1: Add the final deterministic system-cert owner

**Files:**
- Create: `devsystem/api2_task16_final_mobile_system_cert_v1.py`
- Test: `tests/test_api2_task16_final_mobile_system_cert_v1.py`

**Interfaces:**
- Consumes: repository root files from the frozen V8.1/V9/V10/V36/V97 Game Totals chain.
- Produces: `audit(root: Path = Path('.')) -> dict[str, Any]` and CLI `main() -> int`.

- [ ] **Step 1: Write the failing certification test**

Assert the report requires exact frozen blob identities, V8.1 mobile recovery markers, V97 -> V36 -> V10 routing, V10 final-cert flags, Step-9 comparison-only firewall, 30-entry Runless fallback inventory, and zero stake/wager activation.

- [ ] **Step 2: Run the test and confirm RED**

Run: `pytest -q tests/test_api2_task16_final_mobile_system_cert_v1.py`
Expected: FAIL because the certification owner does not exist.

- [ ] **Step 3: Implement the minimal cert owner**

Implement Git-compatible blob hashing, exact source-marker checks, fallback-manifest counting, and a fail-closed report with `ready`, `checks`, `failures`, `sportsbook_projection_influence`, `stake_sizing_enabled`, `wager_actions_enabled`, and `certification_marker`.

- [ ] **Step 4: Run the focused test GREEN and compile**

Run: `pytest -q tests/test_api2_task16_final_mobile_system_cert_v1.py && python -m py_compile devsystem/api2_task16_final_mobile_system_cert_v1.py`
Expected: PASS / exit 0.

---

### Task 2: Run responsive browser evidence without product mutation

**Files:**
- No repository runtime files changed.
- Evidence-only local harness may be generated outside the repository.

**Interfaces:**
- Consumes: frozen V9/V10 responsive HTML/CSS plus the V8.1 mobile-control contract.
- Produces: viewport evidence for 390x844, 768x1024, and 1440x1200 showing no horizontal overflow and visible final-read/mobile-control content.

- [ ] **Step 1: Render the certified final-layer UI in a local Streamlit/browser harness**

Use actual frozen Task-15/V8.1 source contracts; deterministic fixture data only. Do not edit product files.

- [ ] **Step 2: Drive Chromium with Playwright at all three viewports**

Assert document width does not exceed viewport width, the Step-10 final certification banner is visible, OVER/UNDER/PASS market-read content is visible, and mobile recovery controls remain represented by their frozen contract.

- [ ] **Step 3: Stop immediately on any responsive defect**

A browser failure is a Task-16 blocker and does not authorize silent product repair.

---

### Task 3: Freeze ledger, exact-head Runless proof, merge, and merged-main read-back

**Files:**
- Create: `devsystem/task_ledgers/api2-task16-final-mobile-system-cert-v1.json`

**Interfaces:**
- Consumes: Task-1 cert report and Task-2 browser evidence.
- Produces: verification-only Task-16 freeze record.

- [ ] **Step 1: Create the ledger with `product_code_changed=false` and all frozen protections**

Record baseline main, certified candidate, mobile/browser viewport evidence, sportsbook 0.0%, stake/wager OFF, and exact frozen blob identities.

- [ ] **Step 2: Run final focused verification**

Run the Task-16 test, cert CLI, Task-15 contract test, existing V8.1 mobile contract test, and compile of certification-only files.

- [ ] **Step 3: Open one PR and prove zero legacy Actions fan-out**

No automatic legacy proof workflow may launch on the exact candidate.

- [ ] **Step 4: Certify the exact PR head with Runless**

Require `runless-final-gate` SUCCESS from GitHub App ID `5204253` and capture the receipt digest.

- [ ] **Step 5: Merge only the exact certified head**

Reject merge if the PR head moves.

- [ ] **Step 6: Read back merged `main` before claiming completion**

Verify the merge parent contains the certified Task-16 head, branch protection still requires `runless-final-gate`, frozen blobs remain unchanged, and no legacy Actions fan-out occurred on merged main.

- [ ] **Step 7: Declare Task 16 GREEN + FROZEN only from terminal evidence**

The final mission state becomes `16/16 = 100%` only after this read-back.
