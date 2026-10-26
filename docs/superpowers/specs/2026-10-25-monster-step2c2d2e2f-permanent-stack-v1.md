# MONSTER Permanent Step 2C + 2D + 2E + 2F Design

## Intent

Extend the existing MONSTER-only Step 2A / Anti-Loop / Step 2B / Step 2C / Step 2D control plane with permanent Step 2E canonical router ownership and Step 2F live production consumption/stable-alias verification. Final GREEN/FROZEN must be MONSTER-owned and must not use foreign-system state as evidence.

## Canonical control sequence

`STEP 2A -> ANTI-LOOP -> STEP 2C -> STEP 2B -> EXECUTE -> STEP 2D -> STEP 2E -> STEP 2F -> FINAL VERIFY -> GREEN -> FROZEN`

Any downstream failure routes through `ANTI-LOOP -> STEP 2C -> STEP 2B -> STEP 2A` before a materially different corrective action is allowed.

## Isolation

- Authority branch: `monster-step2c2d2e2f-permanent-stack-v1` from `monster-main`.
- Only MONSTER-owned ledgers, receipts, registries, branches, PRs, runs, deployment attestations, and freeze records count.
- Repository coexistence with unrelated files does not grant those files authority.
- Proof transport must use exact SHA and a MONSTER proof namespace.

## Step 2C

Preserve the existing autonomous MONSTER root-cause engine as the required failure investigator. A diagnosis must include root cause, evidence, failure class, affected boundary, materially different repair, evidence digest, and next required gate. Technical failures do not stop for the user unless the blocker is genuinely human-only.

## Step 2D

Preserve the existing MONSTER data-truth gate. It remains mandatory after execution and before router/production verification. Empty is not absence; technical failures retain diagnostic state; verified absence requires successful-path proof; field-specific fallbacks are required; fabrication and failure-as-negative-cache are blocked; source -> authoritative value -> final consumer value must match.

## Step 2E — Canonical Router Ownership

Create a MONSTER-owned registry of live sports routes. Each registered route has exactly one canonical sport identity, page/market identity, frontend destination/module, parameter contract, expected consumer owner, and backend endpoint when data is required.

Step 2E fails closed when:

- duplicate canonical ownership exists;
- a route points across sports unexpectedly;
- a frontend destination/module is missing;
- backend-required routes lack an API endpoint or mounted-router attestation;
- required route parameters are not preserved;
- a registered page is orphaned;
- a backend route is orphaned;
- a legacy/generic override can silently own the same production destination;
- a live page is not present in the registry.

A route file existing is not sufficient. Registry evidence must prove reachability through the authoritative routing path.

## Step 2F — Live Production Consumption + Stable Alias

Create a MONSTER-owned production attestation contract. Step 2F compares:

`certified MONSTER SHA -> deployment identity -> stable production alias -> canonical endpoint -> live response -> router/schema/owner -> real website consumer`.

Step 2F fails closed for candidate/deployment mismatch, alias drift, preview-as-production, stale deployment, wrong project/environment, router/endpoint mismatch, schema mismatch, unhealthy runtime, missing smoke coverage, or missing rollback anchor.

Step 2F never blindly redeploys or re-promotes a failed artifact. Failure evidence routes to Anti-Loop -> Step 2C -> Step 2B -> Step 2A before a successor action.

## MONSTER proof authority

GitHub Actions is supporting evidence only. Final GREEN/FROZEN requires a MONSTER-owned proof receipt containing exact candidate SHA, evidence digest, Step 2C/2D/2E/2F results, regression result, deployment identity when applicable, stable alias target when applicable, and rollback anchor. The receipt is bound to the MONSTER proof namespace and one-use scope lease.

## GREEN

GREEN requires Step 2A, Anti-Loop, Step 2C where required, Step 2B, execution, Step 2D, Step 2E, Step 2F, acceptance proof, regressions, exact-head proof, and production proof when applicable.

## FROZEN

FROZEN requires verified final MONSTER state, verified production identity/alias when applicable, rollback anchor, MONSTER-owned freeze record, receipt/evidence digest match, and independent readback. The freeze target is `MONSTER_STEP2C2D2E2F_PERMANENT_STACK_V1_FROZEN`.

## Zero-context resume

The task ledger must preserve active problem, exact authority path/head, last completed gate, latest evidence/failure class, remaining proof, deployment path, proof receipt identity, and freeze target.
