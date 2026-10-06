# Runless Proof Plane Operations

## Permanent operating rule
API 2 / MONSTER GREEN + FROZEN must not depend on GitHub Actions. Normal proof executes through the Runless Proof Plane. GitHub receives proof status only. GitHub Actions is a manual emergency fallback and may run only with explicit Kyre authorization.

## Health
`GET /health` must return `status=healthy`, service `runless-proof-plane`, and `github_actions_enabled=false`. Bootstrap mode permits health only; proof mutation fails closed.

## Proof submission
Submit one authenticated `/prove` request for one task/workstream/exact candidate SHA/lease. Missing plans fail closed with `RUNLESS_PLAN_REQUIRED`. One workstream may have only one active proof chain.

## WAIT states
WAIT is valid for identity movement, registry reconciliation, deployment freshness, external exact-head merge, or explicit human branch-protection handoff. WAIT never triggers a generic retry loop.

## Failure classes
PLAN, IDENTITY, LEASE, REGISTRY, STATIC_PROOF, PUBLIC_PROOF, INFRA, and SECURITY are distinct. A repeated unchanged failed request is blocked until a new authorization receipt or changed evidence identity exists.

## Receipts
`GET /receipts/{proof_id}` returns the immutable terminal receipt. Receipts are stored on `runless-proof-receipts` beneath `devsystem/runless_proof_receipts/` and chained by digest.

## Restart behavior
After restart, reconstruct only from durable receipt/registry truth. Never invent terminal state or re-execute unchanged static proof automatically.

## GitHub App rotation
Create the replacement private key in GitHub, update the Render secret directly, deploy once, verify `/health` and a read-only lookup, then revoke the old key. Never place private-key material in chat, repository files, logs, receipts, or status descriptions.

## Render outage
Fail closed. Do not fall back to GitHub Actions automatically. Restore Render, verify deployment identity, then resume from durable receipt/registry state.

## Emergency Actions fallback
GitHub Actions is manual emergency fallback only. It requires explicit Kyre authorization for the specific incident/run. Automatic `pull_request` or proof `push` triggers are forbidden after cutover.

## GREEN + FROZEN
GREEN + FROZEN requires exact candidate proof, required live proof, exact-head merge, post-merge/deployment identity verification, transactional registry write, and exact registry read-back. A successful write without matching read-back is not GREEN + FROZEN.
