# Monster Anti-Loop / Forward-Motion Control V1 — Design

Date: 2026-09-15
Status: Design approved in chat; implementation pending written-spec review
Branch: `monster-anti-loop-forward-motion-v1`

## Purpose

Prevent Monster from wasting time in repetitive analysis, duplicate proof checks, approval churn, and side-quest debugging while preserving fail-closed safety around production, frozen sports logic, credentials, destructive operations, and cost-impacting infrastructure changes.

This upgrade applies in two places at once:

1. **Conversation operating behavior** — how Monster responds after the user says `Go ahead Monster Mode`.
2. **Repo/DevSystem enforcement** — deterministic machine-readable state, loop detection, retry budgets, blocker handling, and CI checks.

The two layers must use the same concepts and exit rules so they cannot drift apart.

## Core operating mode

`Go ahead Monster Mode` activates **Strict Auto-Continue with Guardrails** for the approved task.

After activation, Monster continues through normal implementation work without asking for repeated approval for:

- code edits inside the approved scope;
- focused tests and TDD iterations;
- branches and pull requests;
- normal CI investigation;
- non-destructive certification repairs directly required to reach the approved finish line;
- normal merges after required protected gates are GREEN;
- normal deploy/redeploy actions already inherent in the approved task when no secret, cost, destructive, or product-scope change is introduced.

Monster stops only for one of these hard boundaries:

- a material scope or architecture change not implied by the approved finish line;
- destructive data/repository/infrastructure action;
- credential, secret, or authentication change;
- cost-impacting infrastructure change;
- product behavior decision with multiple materially different user outcomes;
- one concrete external blocker that Monster cannot resolve with available tools.

## Anti-loop laws

### Law 1 — Closed means closed

A checkpoint in `DONE` state may not be reopened merely to gather more confidence. It can be reopened only when new evidence directly contradicts the evidence that closed it.

### Law 2 — Every action must advance state

Each tool call or implementation action must do at least one of:

- create or modify the intended artifact;
- run a previously unexecuted verification required by the current exit condition;
- test a new hypothesis that can distinguish between remaining root causes;
- close a checkpoint;
- resolve the active blocker;
- produce evidence required for the next state transition.

A call whose only purpose is to reconfirm unchanged evidence is rejected as `NO_FORWARD_MOTION`.

### Law 3 — No duplicate proof without changed inputs

The same proof target may not be queried twice unless at least one proof input changed, such as:

- commit SHA;
- deployed revision;
- environment/configuration;
- test implementation;
- workflow head;
- runtime activation state;
- time-sensitive external condition explicitly allowed by policy.

### Law 4 — One blocker at a time

Only one blocker may be `ACTIVE`. New observations are attached to that blocker unless they are independent and prevent further work. Monster resolves or definitively externalizes the active blocker before opening another.

### Law 5 — Root cause before retry

Deterministic failures are never retried unchanged. Transient-capable failures receive at most one controlled retry after inspection. A repeated transient-capable failure becomes deterministic until the cause changes.

### Law 6 — No approval churn inside approved scope

Once Strict Auto-Continue is active, implementation substeps do not generate new approval gates unless one of the hard boundaries is crossed.

### Law 7 — Finish line is authoritative

Every task has explicit exit conditions. When all exit conditions are satisfied, the task closes. Monster may not invent another checkpoint, proof pass, certification round, or architectural step afterward.

### Law 8 — Side quests are quarantined

Unrelated defects discovered during execution are recorded as `DEFERRED` and do not interrupt the active task unless they directly prevent the approved exit condition.

## Checkpoint ledger

The permanent ledger model is intentionally small.

Each task contains:

- `task_id`
- `title`
- `mode` (`strict_auto_continue` by default after Monster Mode approval)
- `status`: `ACTIVE | DONE | BLOCKED | FAILED`
- `current_checkpoint`
- `total_checkpoints`
- `completed_checkpoints`
- `remaining_checkpoints`
- `exit_conditions`
- `active_blocker` or `null`
- `deferred_findings`
- `evidence_fingerprints`
- `action_history`

Each checkpoint contains:

- stable checkpoint ID;
- state `PENDING | ACTIVE | DONE | BLOCKED | DEFERRED`;
- entry condition;
- exit condition;
- evidence that closed it;
- immutable closed timestamp/hash when done.

Only one checkpoint may be `ACTIVE` for a sequential task. Parallel lanes must be declared explicitly rather than inferred during debugging.

## Forward-motion controller

A new dependency-light DevSystem module will evaluate a proposed action before execution and an observed result after execution.

The controller uses an **action fingerprint** derived from:

- task ID;
- checkpoint ID;
- action type;
- target resource;
- relevant input revision/config hash;
- intended evidence class.

It rejects a repeated fingerprint when prior execution already produced a valid result and no input changed.

Primary decisions:

- `ALLOW_ADVANCE`
- `ALLOW_NEW_HYPOTHESIS`
- `ALLOW_CONTROLLED_RETRY`
- `REJECT_DUPLICATE_PROOF`
- `REJECT_CLOSED_CHECKPOINT_REOPEN`
- `DEFER_SIDE_QUEST`
- `STOP_EXTERNAL_BLOCKER`
- `TASK_COMPLETE`

## Retry and debugging budget

Default budgets:

- deterministic failure: `0` unchanged retries;
- transient-capable failure: `1` controlled retry after inspection;
- unknown failure: one evidence-gathering action, then classify;
- same evidence source: one read per unchanged revision unless the source is paginated and additional pages are required;
- same workflow/job log: one fetch per run attempt unless the run itself changes;
- same production proof: one check per deployment/runtime activation state.

The controller records why a retry is allowed, preventing accidental repeated retries under different wording.

## Blocker contract

A blocker object contains:

- `blocker_id`
- `checkpoint_id`
- `root_cause_class`
- `evidence`
- `resolvable_with_available_tools`
- `next_action`
- `requires_user`
- `user_action` when required

When `requires_user=true`, Monster reports exactly:

1. the blocker;
2. why available tools cannot resolve it;
3. the single action needed from the user.

It must not continue speculative investigation after externalizing that blocker.

## Conversation behavior contract

During Monster Mode, live updates should show only meaningful state transitions, not every internal read.

Preferred update format:

- current checkpoint;
- what changed;
- resulting state;
- remaining checkpoint count;
- next action.

Monster should never say it is doing another check unless that check is permitted by the forward-motion rules.

If a user asks for live checkpoints, the board remains stable: completed items stay completed, remaining count only decreases unless a genuine scope change is explicitly approved.

## Repo components

V1 should be additive and dependency-light. Proposed permanent files:

- `devsystem/forward_motion_policy_v1.json` — machine-readable limits, hard boundaries, allowed state transitions.
- `devsystem/forward_motion_v1.py` — deterministic controller and fingerprint evaluator.
- `devsystem/checkpoint_ledger_v1.py` — ledger validation and state transitions.
- `tests/test_devsystem_forward_motion_v1.py` — controller laws and retry tests.
- `tests/test_devsystem_checkpoint_ledger_v1.py` — ledger invariants.
- `tests/test_monster_a9_anti_loop_replay_v1.py` — regression replay of the A9 loop pattern.

Existing modules remain authoritative for their current roles:

- `failure_triage_v1.py` classifies failures and retry classes;
- `failure_history_v1.py` stores prior failure evidence;
- `final_gate_v1.py` remains the stable aggregate gate;
- existing production certification remains authoritative for production identity and health.

The new controller orchestrates these systems; it does not replace them.

## CI integration

`devsystem-targeted-ci.yml` will gain one lightweight early lane, proposed name:

`forward-motion-contract`

It validates:

- policy schema;
- allowed checkpoint transitions;
- duplicate-proof rejection;
- retry budget enforcement;
- one-active-blocker rule;
- finish-line closure;
- A9 replay regression.

`devsystem-final-gate` must require this lane whenever DevSystem/control-plane files change. Existing sport-specific lanes remain unchanged.

## A9 regression replay

The V1 stress test replays the failure pattern seen during A9 as deterministic state events:

1. implementation certified GREEN;
2. production proof shows no event;
3. production verification reveals Render identity drift;
4. controller opens exactly one production-identity blocker;
5. duplicate PostHog/Render checks are rejected until runtime/deploy/config changes;
6. cert witness exposes a stale test contract;
7. required test-only repair advances state;
8. controlled deploy changes runtime revision;
9. production witness goes GREEN;
10. immutable production identity pin updates;
11. protected gate passes;
12. task closes.

The replay fails if the controller:

- reopens a closed A9 checkpoint without contradictory evidence;
- issues the same production proof twice on the same runtime state;
- asks for approval for an in-scope repair;
- opens multiple blockers simultaneously;
- adds a checkpoint after all declared exit conditions are satisfied.

## Safety / non-goals

V1 must not:

- alter sports projection math;
- alter sportsbook influence contracts;
- change official-ID matching rules;
- bypass protected `main`;
- weaken `devsystem-final-gate`;
- automatically rotate secrets;
- create paid infrastructure;
- delete production resources or data;
- replace failure triage, production certification, or regression shields.

## Exit conditions

The Anti-Loop / Forward-Motion Upgrade is complete only when all are true:

1. policy and ledger contracts are implemented;
2. duplicate proof and closed-checkpoint reopen attempts fail deterministically;
3. retry budgets are enforced;
4. one-active-blocker invariant is enforced;
5. A9 regression replay passes;
6. permanent DevSystem CI includes the forward-motion contract;
7. `devsystem-final-gate` is GREEN on the exact final head;
8. the PR is merged to protected `main`;
9. post-merge production verification remains GREEN where applicable;
10. temporary test/cert machinery is removed;
11. the upgrade is declared `DONE` and no additional implementation checkpoint is created.

## Eight-step execution board

1. Lock Auto-Continue rules.
2. Define hard anti-loop laws.
3. Build live checkpoint ledger.
4. Build forward-motion controller.
5. Build blocker/debugging limits.
6. Wire into Monster repo/DevSystem.
7. Stress-test against A9 loop pattern.
8. Certify, merge, freeze, activate.

The board is finite. Step 8 is terminal.
