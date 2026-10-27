# MONSTER Step 2G Pre-Render Runtime Identity Regression R2 Design

Authority: MONSTER ONLY.

## Intent
Restore the already-proven Step 2G runtime-identity invariant on the current protected-main lineage so production identity is emitted before any page renderer can interrupt execution.

## Goals
- Keep exactly one `emit_runtime_identity_marker()` call and place it before the single `render_app()` call.
- Preserve the current NBA PRA Page 2 V4 module-cache eviction repair and all current renderer/data behavior.
- Reuse the existing regression contract that already failed on the current candidate baseline.
- Require exact-head Runless App 5204253 proof before merge.
- Require current-main live production read-back and MONSTER-only frozen checkpoint before 100% GREEN + FROZEN.

## Non-goals / anti-goals
- No sportsbook, provider, model, projection, router, page layout, or data changes.
- No weakening or bypassing the pre-render identity regression test.
- No duplicate proof lane, blind rerun, broad entrypoint rewrite, or foreign-system evidence.

## Approaches
1. **Chosen — restore the two-line call order.** Smallest change; directly repairs the proven boundary and preserves current main.
2. **Rejected — weaken/remove the test.** Would make the gate green without making production identity reachable before rendering.
3. **Rejected — refactor the entrypoint.** Unnecessary blast radius for a two-line regression and risks disturbing frozen page/runtime behavior.

## Constraints
- Base exactly `e319e5c73980736ca3e5da71316e018e025eb52c`.
- One successor branch and one PR for this regression.
- MONSTER-only evidence; API 2 state is not evidence.
- Runless App 5204253 exact-head gate is mandatory.

## Acceptance
1. Existing focused pre-render contract turns from `1 failed, 5 passed` to all passing.
2. NBA PRA Page 2 module-cache/CSS/S-tier focused regressions remain green.
3. Exact candidate receives `runless-final-gate` success from App 5204253 with MONSTER-only authority.
4. Expected-head merge succeeds and protected-main tree contains the tested order.
5. Fresh 390x844 production browser reaches NBA PRA Page 2 READY, exposes current MONSTER runtime identity before renderer interruption, and shows no leaked V4 CSS text.
6. MONSTER-only final checkpoint is written and independently read back before status becomes 100% GREEN + FROZEN.
