# Runless Proof Plane V1 Operations

## Permanent operating rule

API 2 / MONSTER GREEN + FROZEN must not depend on GitHub Actions. Normal proof executes through the Runless Proof Plane. GitHub receives proof status only. GitHub Actions is a manual emergency fallback and may run only with explicit Kyre authorization.

## Health

Use the dedicated `runless-proof-plane` Render service health endpoint. Healthy operation must identify the service, report that GitHub Actions is disabled for normal proof, and never depend on `kyre-sports-api`. A healthy shell is not proof authority by itself; proof endpoints still fail closed when required credentials or a task proof plan are absent.

## Proof submission

Submit one proof request for one workstream, exact candidate SHA, task ID, and scope lease. Step 2A is evaluated before proof execution. A missing plan terminates with `RUNLESS_PLAN_REQUIRED`; it never falls back automatically to Actions.

## WAIT states

WAIT means the proof is intentionally paused, not failed and not GREEN. Typical states are `WAIT_MERGE`, `WAIT_DEPLOYMENT_IDENTITY`, and `WAIT_REGISTRY_RECONCILIATION`. Resume only from a matching external event or fresh authoritative observation. Do not poll repeatedly or create duplicate proof chains.

## Failure classes

Classify failures before any patch: `PRODUCT`, `PROOF_VERIFIER`, `CONTROL_PLANE`, `DEPLOYMENT`, `AUTH`, or `UPSTREAM`. One classified failure owns one surgical correction. Unchanged failed requests must not be retried generically.

## Receipt lookup

A receipt lookup is read-only. Terminal receipts are content-addressed and tamper-evident, bind the exact candidate SHA, workstream, evidence digests, deployment identity where required, and frozen-registry before/after identity. A receipt digest referenced by `runless-final-gate` must match the stored receipt.

## Restart behavior

After a Render restart, reconstruct proof state from durable receipts plus current registry state. Never invent terminal state and never re-execute unchanged static proof simply because the process restarted.

## GitHub App rotation

For GitHub App rotation, install the replacement key in Render secrets first, deploy once, verify health/auth diagnostics, then revoke the old key. Never place private key material in repository files, logs, status descriptions, or receipts. The App must not receive Actions write permission.

## Render outage

During a Render outage, hold the workstream in WAIT. Preserve the last safe receipt, lease, exact candidate identity, and registry snapshot. Do not dispatch GitHub Actions as an automatic substitute. Resume Runless only after service health and identity are restored.

## Manual Actions emergency fallback

GitHub Actions is emergency fallback only. It requires explicit Kyre authorization for that fallback event; lack of that authorization fails closed. The fallback must be manually invoked, scoped, and recorded. It does not become the normal proof path and cannot silently replace Runless.

## Registry read-back and freeze

GREEN + FROZEN is impossible from a successful registry write alone. The system must read the registry back and verify the exact freeze token, merged SHA, revision, state hash, and receipt digest. Any mismatch is `WAIT_REGISTRY_RECONCILIATION`, not success.
