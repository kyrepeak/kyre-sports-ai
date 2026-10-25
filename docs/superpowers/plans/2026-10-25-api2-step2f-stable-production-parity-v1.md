# API2 Step 2F — Stable Production Parity Gate V1

## Intent
Step 2F closes the gap between a GREEN exact-head/preview proof and the code actually served by stable production. Step 2E proves canonical router ownership; Step 2F proves the stable production service is serving the exact frozen commit and that every visible sports page is accounted for by the correct stable gateway.

## Scope
- Derive the visible page surface from `universal_sports_nav_registry_v1.visible_sports()`; do not create a second page registry.
- Cover all 39 currently visible pages across NFL, CFB, NBA, MLB, and WNBA.
- Reuse Step 2E registrations for NFL/CFB/NBA/WNBA canonical ownership.
- Preserve MLB's existing stable Render service boundary; Step 2F verifies stable-service parity without silently migrating MLB hosting.
- Add a non-secret Kyre Sports API deployment receipt exposing Vercel environment, target environment, Git SHA/ref, and runtime URL metadata.
- Stable Vercel production alias: `https://kyre-sports-api.vercel.app`.
- MLB stable service: `https://kyre-sports-api.onrender.com`.

## Acceptance gates
1. Step 2A: one authoritative branch/PR/proof/deployment path.
2. Anti-Loop: no duplicate branch, PR, production deployment, alias mutation, or proof run.
3. Step 2B: page surface, gateway ownership, production dependencies, and proof mapping locked before implementation.
4. Step 2C: terminal failures classified as code, route, stable-alias, deployment-environment, SHA, branch, or service drift before repair.
5. Step 2D remains required and unchanged.
6. Step 2E remains required and unchanged for its existing NFL/CFB/NBA/WNBA scope.
7. Step 2F requires stable-production receipt parity: `VERCEL_ENV=production`, production target, exact expected Git SHA, and `api2-main` ref.
8. Preview/`target:null` deployments can never satisfy final Step 2F.
9. All visible pages must map to one stable service and one proof mode.
10. A frozen receipt records page key, stable service, canonical owner/target when Step 2E applies, deployment SHA/environment, and proof result.

## Proof model
PR proof is static/TDD: 39-page surface, ownership mapping, deployment-receipt policy, rejection of preview/stale SHA, and FastAPI receipt mount. Final post-merge proof is live: create exactly one production deployment from the exact merge SHA, verify the stable alias serves that deployment, verify `/api/v1/system/deployment-receipt`, `/health`, and `/api/v1/router/coverage`, then verify the full 39-page matrix has zero unresolved pages.

## Completion rule
A page may only be called GREEN + FROZEN when Step 2E (where applicable) and Step 2F are GREEN. A READY preview is never final production evidence.
