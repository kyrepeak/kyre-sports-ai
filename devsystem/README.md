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

### Anti-Loop V2 authority

After V2 activation, `devsystem/forward_motion_policy_v2.json` is the authoritative forward-motion policy. V1 remains in the repository as historical/reference compatibility and its replay must stay GREEN, but V1 is not the authority for new task progress.

Permanent Anti-Loop V2 rules:

- A DONE checkpoint stays closed unless new contradictory evidence invalidates its closing proof.
- The same exact action cannot advance twice against unchanged relevant inputs.
- The same **root-cause family** cannot be disguised as new work by changing run IDs, timestamps, branch display names, command ordering, or wording.
- Deterministic regressions receive zero unchanged retries.
- Transient-capable failures receive at most one inspected controlled retry.
- Unknown failures receive one evidence-gathering action before a new discriminating hypothesis or a stop.
- Three meaningful actions on the same path without measurable progress trigger a stagnation lock.
- Only one blocker may be active at a time; unrelated findings are deferred rather than becoming side quests.
- An external blocker must name one concrete user action and must genuinely be unresolvable with the available tools.
- Every authoritative state-changing action requires a valid V2 authorization receipt. The action record consumes that receipt exactly once; checkpoint transitions reference the resulting authorized action-event ID instead of consuming the receipt again.
- Receipt history is hash-chained and tamper-evident. Missing, mismatched, replayed, or edited receipts/events fail closed.
- A user override must be explicit, exact-action, auditable, and single-use. Monster Mode may consume a valid `user_explicit` override event but may not invent, infer, broaden, or self-authorize one.
- V2 does not claim cryptographic proof that ChatGPT-visible text was authored by a particular human account holder; the override record is an explicit workflow/audit input, not an identity signature.
- Once every declared exit condition is satisfied, the task is terminal (`TASK_COMPLETE`); new implementation checkpoints, cleanup proofs, or re-certification steps may not be invented afterward.

The V2 control plane lives in:

- `devsystem/forward_motion_policy_v2.json` — permanent budgets and decisions;
- `devsystem/forward_motion_v2.py` — authorization and loop/stagnation decisions;
- `devsystem/action_ledger_v2.py` — single-use receipts, action history, PR ledger enforcement, and the self-expiring bootstrap rule;
- `devsystem/checkpoint_ledger_v2.py` — monotonic checkpoint transitions using authorized action-event IDs;
- `devsystem/anti_loop_replay_v2.py` — adversarial regression replay;
- `devsystem/forward_motion_contract_v2.py` — dependency-light permanent V2 validator.

The existing required `permanent-contract` CI lane runs the V2 contract and PR-ledger verifier. After V2 exists on protected `main`, every non-documentation PR must change exactly one valid DONE task ledger under `devsystem/task_ledgers/`. A missing valid receipt chain means the PR cannot claim authoritative progress.

### One-time V2 bootstrap

The initial V2 activation is the only exception because V2 cannot authorize actions performed before V2 exists. That activation uses `activation_mode: v2-bootstrap` and may change only the exact approved V2 control-plane/test/docs/workflow paths. The bootstrap automatically becomes invalid as soon as the base revision contains `devsystem/forward_motion_policy_v2.json`; ordinary future PRs can never reuse it.

The stable aggregate required check remains `devsystem-final-gate`.

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
