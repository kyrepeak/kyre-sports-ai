# Kyre Sports AI DevSystem

This folder is the permanent development operating system around the sports app. It is intentionally separate from sports projection/model logic.

## Normal change flow

1. Create a small branch from the current green `main`.
2. Change the smallest necessary files.
3. Open a PR.
4. `DevSystem targeted CI` classifies the change.
5. The permanent contract and regression shield run first.
6. Only the affected active sport lanes run.
7. Shared browser QA runs when UI/core/CFB routing is affected.
8. `devsystem-final-gate` becomes GREEN only when every required lane is success or intentionally skipped.
9. Merge only after the final gate is green.
10. Relevant pushes to `main` run production verification.
11. Keep a green rollback branch after meaningful system milestones.

## Domain activation rule

A sport is not allowed to become a normal development lane until it has:
- an `active` entry in `devsystem_manifest_v1.json`;
- a dedicated critical CI job;
- at least one real critical test;
- deliberate browser/production coverage notes.

Today CFB, MLB, and WNBA are active. NFL code exists but is intentionally fail-closed for new changes until its dedicated test lane is built. NBA, NHL, and soccer are reserved for future activation.

## Failure order

When something turns red, diagnose in this order:

**classifier -> permanent contract -> regression shield -> affected sport lane -> browser QA -> production verification**

Do not change projection math to fix infrastructure, deployment, browser, or workflow failures. Fix the layer that actually failed.

## Safety rules

- Frozen model/runtime blobs remain frozen unless a deliberate new version is created.
- CFB sportsbook data remains context-only at 0% projection weight unless a deliberate future model version changes that contract.
- Official IDs stay authoritative; do not silently replace exact identity with fuzzy/synthetic matching.
- Never hide missing production data by inventing values.
- Prefer additive versions and small reversible changes.
- A failed verifier is evidence to inspect, not a reason to weaken the verifier until it turns green.

## Stable CI check

The permanent aggregate check is named:

`devsystem-final-gate`

That name should stay stable so repository protection can point at one durable result even as individual sport lanes evolve.
