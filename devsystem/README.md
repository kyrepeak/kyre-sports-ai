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

## Monster Auto-Continue / forward-motion contract

When an approved task is running in **Monster Mode**, `Go ahead Monster Mode` means strict auto-continue through normal implementation, tests, branches, PRs, CI diagnosis, and in-scope repairs until the declared finish line is reached or one genuine external blocker requires the user.

Permanent anti-loop rules:

- A DONE checkpoint stays closed unless new contradictory evidence invalidates its closing proof.
- The same proof fingerprint may not run again against unchanged relevant inputs.
- Deterministic regressions receive zero unchanged retries.
- Transient-capable failures receive at most one inspected controlled retry.
- Unknown failures receive one evidence-gathering action before a new discriminating hypothesis or a stop.
- Only one blocker may be active at a time; unrelated findings are deferred rather than becoming side quests.
- An external blocker must name one concrete user action and must genuinely be unresolvable with the available tools.
- Once every declared exit condition is satisfied, the task is terminal (`TASK_COMPLETE`); new implementation checkpoints may not be invented afterward.

The machine-readable policy lives in `devsystem/forward_motion_policy_v1.json`. `devsystem/checkpoint_ledger_v1.py` enforces checkpoint state, `devsystem/forward_motion_v1.py` makes next-action decisions, and `devsystem/forward_motion_contract_v1.py` certifies the permanent invariants. The existing required `permanent-contract` CI lane executes that validator through `tests/test_devsystem_permanent_gate_v1.py`, so these protections are enforced without adding another CI fan-out job.

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
