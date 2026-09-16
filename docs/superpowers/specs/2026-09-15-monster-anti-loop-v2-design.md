# Monster Anti-Loop V2 — Hard-Gate Design

Date: 2026-09-15
Status: Design approved in chat; implementation not started
Repository: `kyrepeak/kyre-sports-ai`

## 1. Purpose

Monster Anti-Loop V2 strengthens the existing V1 forward-motion controls so repeated work, stale retries, checkpoint backtracking, approval churn, side quests, and invented post-finish work cannot become authoritative project progress.

V1 remains valuable: it already detects exact duplicate proof fingerprints, protects DONE checkpoints, caps deterministic/transient retries, enforces one active blocker, defers unrelated work, and treats `TASK_COMPLETE` as terminal. V2 keeps those guarantees and adds a hard authorization layer, root-cause-level stagnation detection, tamper-evident action history, and CI verification.

The goal is not merely to tell Monster Mode not to loop. The goal is to make a rejected looping action incapable of advancing the DevSystem ledger or passing the protected certification path.

## 2. Scope

V2 is an additive DevSystem/control-plane upgrade. It may touch only DevSystem files, DevSystem tests, documentation, and the existing DevSystem CI/permanent-gate wiring required to certify the new contract.

Frozen sports/model/runtime behavior is out of scope. In particular, this design does not modify NFL Game Totals, NFL Spread, NFL Moneyline, Passing Yards, Rushing Yards, Receiving Yards, CFB, MLB, WNBA projection logic, market logic, sportsbook behavior, or production data-provider behavior.

V1 remains present during migration. V2 becomes authoritative only after its contract and integration tests are green and the existing permanent gate requires it.

## 3. Design principles

1. **Monotonic progress.** A task advances through declared checkpoints in one direction. A closed checkpoint cannot reopen without new contradictory evidence tied to the original closing proof.
2. **Progress or stop.** Every authorized action must create new evidence, materially change relevant inputs, narrow a root cause, resolve/defer the active blocker, or close/advance a checkpoint.
3. **Root-cause awareness.** Loop detection groups actions by underlying failure family, not only exact command text or action fingerprint.
4. **No disguised retries.** Changing run IDs, timestamps, branch names, command wording, ordering, or other superficial metadata does not create fresh evidence.
5. **One blocker.** Only one active blocker may control the task at a time. Unrelated findings are deferred.
6. **No approval churn.** Routine in-scope repairs continue automatically under Monster Mode. User approval is required only for previously declared hard boundaries or a user-only override.
7. **Terminal means terminal.** Once every declared exit condition is satisfied, the task is `TASK_COMPLETE`; no new checkpoints, proofs, cleanup steps, or re-certification may be invented.
8. **Fail closed.** Missing or invalid authorization evidence cannot be treated as progress.
9. **User retains the emergency key.** A blocked action may be overridden only after explicit user authorization for that exact action. The override is single-use and does not disable V2 globally.
10. **No false security claims.** Repository hashes can prove integrity and sequencing of recorded data, but not cryptographically prove that a ChatGPT-visible instruction came from the human account holder. V2 therefore treats user override authorship as an explicit workflow input/audit requirement, not a cryptographic identity proof.

## 4. Architecture

V2 uses a two-layer hard gate: preventive authorization before authoritative progress, plus independent CI verification before certification/merge.

### 4.1 `devsystem/forward_motion_policy_v2.json`

Machine-readable permanent policy defining:

- strict auto-continue mode;
- deterministic retry budget: `0` unchanged retries;
- transient-capable retry budget: `1` controlled retry after evidence inspection;
- unknown-failure evidence budget: `1` evidence-gathering action before a new discriminating hypothesis is required;
- stagnation window: `3` meaningful actions without measurable progress;
- one active blocker maximum;
- closed-checkpoint immutability;
- root-cause recurrence rules;
- terminal-task immutability;
- user-only, single-use override requirements;
- hard boundaries that still require explicit user approval.

### 4.2 `devsystem/forward_motion_v2.py`

The authoritative decision engine. It evaluates a proposed action against the current task ledger, action history, V2 policy, root-cause history, evidence history, and any valid user override event.

Primary decisions:

- `AUTHORIZED`
- `AUTHORIZED_NEW_HYPOTHESIS`
- `AUTHORIZED_CONTROLLED_RETRY`
- `DENIED_LOOP`
- `DENIED_STAGNATION`
- `DENIED_BACKTRACK`
- `DENIED_STALE_FAILURE`
- `DENIED_CLOSED_CHECKPOINT`
- `DENIED_UNAUTHORIZED_OVERRIDE`
- `DEFER_SIDE_QUEST`
- `STOP_EXTERNAL_BLOCKER`
- `TASK_COMPLETE`

Every positive decision returns an authorization receipt. Denied decisions do not.

### 4.3 `devsystem/action_ledger_v2.py`

Owns the append-only logical action history for a task and validates receipt use.

Each meaningful recorded action includes:

- task ID;
- checkpoint ID;
- action type and target;
- action fingerprint;
- root-cause fingerprint;
- evidence fingerprint;
- relevant-input fingerprint;
- authorization receipt ID/hash;
- prior receipt-chain hash;
- outcome;
- progress class;
- failure class if applicable;
- blocker relation;
- override reference if applicable.

A state-changing ledger transition is invalid unless it references an unused valid authorization receipt that matches the same task, checkpoint, action, relevant inputs, and evidence basis.

Receipt reuse is rejected.

The ledger maintains a hash chain so later edits to earlier recorded events are detectable during validation. This provides tamper evidence, not human-identity proof.

### 4.4 `devsystem/checkpoint_ledger_v2.py`

Extends the V1 checkpoint invariants with receipt-aware transitions and strict monotonicity.

Rules:

- exactly one ACTIVE checkpoint for an ACTIVE sequential task;
- DONE checkpoints remain immutable unless new contradictory evidence explicitly invalidates their closing proof;
- backward checkpoint movement without such evidence is denied;
- the next checkpoint is the only ordinary advancement target;
- terminal tasks have no current checkpoint, no blocker, and zero remaining checkpoints;
- a terminal task cannot accept a new progress event.

### 4.5 `devsystem/forward_motion_contract_v2.py`

Dependency-light permanent validator covering the V2 policy, controller, ledgers, receipt-chain rules, stagnation rules, override rules, and regression replays.

It must fail closed on contract drift.

### 4.6 Regression replay

Add a V2 replay, either as `devsystem/anti_loop_replay_v2.py` or a clearly named successor to the V1 A9 replay. It must replay both the historical A9 failure pattern and new adversarial cases designed to bypass V1 through superficial changes.

## 5. Fingerprints and loop detection

V2 uses three independent fingerprints.

### 5.1 Action fingerprint

Represents the exact requested action and relevant inputs. It catches exact duplicate proof attempts.

### 5.2 Root-cause fingerprint

Represents the normalized underlying failure family. It intentionally ignores superficial run metadata so these examples remain the same root cause:

- same failed assertion with a new workflow run ID;
- same endpoint mismatch with different timestamps;
- same CI failure rerun with reordered command flags;
- same production identity mismatch described with different prose.

The normalizer must use stable failure evidence such as failing lane, failure signal/class, target subsystem, assertion/error family, and relevant identity fields. It must not treat volatile metadata as root-cause identity.

### 5.3 Evidence fingerprint

Represents genuinely new diagnostic information or a materially changed relevant input. New evidence may include:

- a changed commit affecting the suspected layer;
- a changed deployment identity;
- a different deterministic error/assertion;
- a newly captured log/trace that narrows the failure;
- a new provider/runtime response relevant to the hypothesis;
- an explicit contradictory proof invalidating a previously closed checkpoint.

Run number, timestamp, retry counter, command wording, branch display name, or reordered flags alone are not new evidence.

## 6. Automatic stop rules

### 6.1 Deterministic failures

A deterministic regression gets zero unchanged retries. The same proof may run again only after a relevant input changes or a new discriminating hypothesis requires a materially different proof.

### 6.2 Transient-capable failures

One controlled retry is allowed after evidence inspection. If it fails again under the same relevant inputs/root cause, that path locks and requires a new hypothesis, a relevant repair, or an external blocker.

### 6.3 Unknown failures

One evidence-gathering action is allowed. A subsequent action must test a new discriminating hypothesis or stop. Repeating broad inspection is denied.

### 6.4 Root-cause recurrence

If the same root-cause fingerprint recurs without a new evidence fingerprint or changed relevant-input fingerprint, V2 returns `DENIED_STALE_FAILURE` or `DENIED_LOOP` even when the exact action fingerprint differs.

### 6.5 Stagnation window

Three meaningful actions without measurable progress trigger `DENIED_STAGNATION` for that path.

Measurable progress is one or more of:

- new evidence;
- materially changed relevant input;
- narrowed root cause;
- blocker resolved or deliberately deferred;
- checkpoint closed;
- checkpoint advanced;
- a genuinely new discriminating hypothesis validated or falsified.

Read-only noise or superficial metadata change does not reset the window.

### 6.6 Closed root causes

A root cause marked resolved and certified stays closed. It can become active again only when new contradictory evidence directly challenges the prior closing evidence.

### 6.7 Terminal lock

When the task ledger reaches all declared exit conditions, every ordinary proposed action returns `TASK_COMPLETE`. The controller cannot create a new checkpoint after closure.

A genuinely new user request creates a new task/ledger rather than extending the completed task.

## 7. Authorization receipts

A positive controller decision creates a deterministic receipt payload containing at least:

- policy version;
- task ID;
- checkpoint ID;
- action fingerprint;
- root-cause fingerprint;
- evidence fingerprint;
- relevant-input fingerprint;
- decision;
- previous receipt-chain hash;
- receipt nonce/unique event ID;
- receipt hash.

The exact encoding must be canonical before hashing.

A checkpoint/action-ledger transition validates that:

1. the receipt hash is valid for the canonical payload;
2. the receipt belongs to the same task/checkpoint/action;
3. its relevant-input/evidence fingerprints match the attempted transition;
4. the previous-chain reference matches the current ledger head;
5. the receipt has not already been consumed;
6. the decision is one of the authorized decision classes.

Missing, mismatched, replayed, or tampered receipts fail closed.

## 8. User-only override

An override is deliberately narrow.

Requirements:

- the exact denied action is identified;
- the checkpoint is identified;
- the prior denial decision/receipt context is referenced;
- an explicit user authorization event is recorded;
- the reason is recorded;
- the override is single-use;
- the override does not alter retry budgets, policy, or future decisions;
- the controller itself cannot infer an override from silence, previous approvals, or its own reasoning.

The controller may consume an override event only for the exact blocked action it references.

### Security limitation

Without an external user-signing mechanism or identity-bound secret outside the agent's authority, repository code cannot cryptographically prove that a text instruction was authored by the human rather than generated by an agent. V2 must not claim otherwise.

The practical guarantee is therefore:

- Monster Mode is prohibited by contract from self-authorizing an override;
- override use is explicit, narrow, single-use, auditable, and CI-validated;
- protected certification fails if the override record is missing, malformed, mismatched, reused, or broader than the denied action.

A future system with a platform-provided human-approval token could strengthen this to cryptographic user-only authorization without changing the rest of the V2 design.

## 9. Data flow

Normal path:

1. A task starts with declared checkpoints and exit conditions.
2. Monster proposes the next meaningful action.
3. V2 normalizes action, root-cause, evidence, and relevant-input fingerprints.
4. V2 evaluates retry budgets, stagnation history, checkpoint position, blocker state, and terminal state.
5. If denied, no authorization receipt is issued and the action cannot advance the authoritative ledger.
6. If authorized, V2 issues a receipt tied to the exact action and current ledger head.
7. The action runs.
8. Result/evidence is recorded in the action ledger by consuming that receipt.
9. Any checkpoint transition validates the same receipt chain and resulting evidence.
10. CI independently revalidates the full committed task ledger/receipt chain before protected certification can pass.

Override path:

1. V2 denies an action.
2. The user explicitly authorizes that exact denied action.
3. A single-use override event referencing the denial is recorded.
4. V2 reevaluates only that action with the override event.
5. If structurally valid, V2 issues a one-action override authorization receipt.
6. Normal recording and CI validation continue; V2 remains fully active afterward.

## 10. CI and permanent-gate integration

V2 integrates into the existing DevSystem instead of adding a broad new fan-out workflow.

The existing `permanent-contract` lane remains the main permanent enforcement point. Implementation should:

- make `devsystem/permanent_gate_v1.py` require the V2 permanent files once migration is complete;
- extend `tests/test_devsystem_permanent_gate_v1.py` to execute the V2 contract validator;
- keep the existing stable `devsystem-final-gate` name unchanged;
- reuse the existing targeted CI flow rather than creating redundant sport jobs;
- add only the minimum workflow markers needed to prove the V2 validator is actually executed;
- fail the permanent contract if V2 files, rules, or workflow wiring drift.

CI must verify at minimum:

- policy version/mode;
- deterministic zero-retry behavior;
- transient single-retry behavior;
- unknown evidence budget;
- root-cause recurrence blocking;
- stagnation lock;
- monotonic checkpoints;
- closed-checkpoint protection;
- one-blocker rule;
- side-quest deferral;
- receipt validity and single-use consumption;
- receipt-chain tamper detection;
- terminal-task immutability;
- user-override structural validity, narrowness, and single use;
- no self-declared/broad override path;
- V1 historical anti-loop replay still passes during migration;
- new V2 adversarial replay passes.

## 11. Adversarial certification cases

V2 tests must deliberately try to bypass the rules.

Required cases:

1. Exact duplicate action with unchanged inputs is denied.
2. Same root cause under a new run ID is denied.
3. Same root cause with reordered command arguments is denied.
4. Deterministic failure retry with no repair is denied.
5. A first inspected transient retry is authorized; a second is denied.
6. Unknown failure gets one evidence action; another broad evidence action is denied.
7. Three no-progress actions trigger stagnation lock.
8. Materially changed relevant input resets the appropriate proof path and allows a fresh action.
9. A genuinely new discriminating hypothesis is allowed without resetting unrelated budgets.
10. Attempting to activate an earlier DONE checkpoint without contradictory evidence is denied.
11. Valid contradictory evidence permits a controlled reopen.
12. A second simultaneous blocker is deferred.
13. An unrelated finding is deferred.
14. A receipt cannot be consumed twice.
15. A receipt cannot authorize a different action/checkpoint/input set.
16. Editing an earlier ledger event breaks the hash chain and fails validation.
17. A controller-generated/self-declared override record is rejected by contract rules.
18. A structurally valid explicit user override applies to only one exact denied action.
19. Reusing the same override is denied.
20. After `TASK_COMPLETE`, an attempted extra proof returns `TASK_COMPLETE` and creates no checkpoint.

## 12. Error handling

V2 is fail-closed for malformed control-plane state.

Examples that raise a contract/validation failure instead of defaulting to permission:

- unknown policy version;
- missing required fingerprint inputs;
- malformed ledger;
- broken receipt chain;
- missing current checkpoint for an active task;
- multiple active checkpoints;
- multiple active blockers;
- invalid progress classification;
- override without a referenced denial;
- receipt/action mismatch;
- unrecognized decision class.

Control-plane errors must never be fixed by modifying sports projection/model logic.

## 13. Migration strategy

1. Keep V1 unchanged as the green baseline.
2. Add V2 policy/controller/action ledger/checkpoint ledger/contract and tests in isolation.
3. Run V1 and V2 replay/contract tests together.
4. Wire V2 into the existing permanent-contract lane.
5. Update the permanent gate's required-file/workflow invariants.
6. Certify that protected sports/runtime files are untouched.
7. Merge only after the existing `devsystem-final-gate` is green.
8. After merge, V2 is the authoritative forward-motion contract; V1 remains historical compatibility/reference until a separate approved cleanup task removes it.

No automatic deletion or rewrite of V1 is part of this task.

## 14. What V2 can and cannot enforce

### V2 can enforce

Within the repository/DevSystem authority path, V2 can make unauthorized work incapable of becoming valid project state or passing protected certification. It can detect stale root-cause repetition, reject invalid checkpoint movement, prevent receipt replay, and make CI fail on control-plane bypasses represented in the committed task history.

### V2 cannot enforce

Repository code cannot modify the ChatGPT model or physically prevent an arbitrary external/read-only tool call that occurs outside the DevSystem protocol. It also cannot cryptographically establish human authorship of a user instruction without a platform-provided signing mechanism outside the agent's control.

Therefore the strongest practical guarantee is: **a disallowed action cannot become authoritative DevSystem progress or pass the protected certification workflow, and Monster Mode's operating contract requires every meaningful project action to use the V2 path.**

## 15. Success criteria

The implementation is complete only when all of the following are freshly proven:

- V2 policy/controller/action-ledger/checkpoint-ledger/contract exist and pass tests;
- root-cause-level loop detection works against superficial action changes;
- the three-action stagnation rule works;
- authorization receipts are required, bound to the exact action, single-use, and tamper-evident;
- denied actions cannot advance the authoritative ledger;
- valid contradictory evidence is the only ordinary path to reopen DONE work;
- terminal tasks reject invented follow-up work;
- user overrides are exact-action, explicit, single-use, and auditable;
- the permanent DevSystem CI lane executes V2 validation;
- `devsystem-final-gate` remains the stable required aggregate check;
- V1 historical regression replay remains green during migration;
- the V2 adversarial replay is green;
- frozen sports/runtime logic remains untouched;
- the final diff is limited to the approved DevSystem/docs/tests/workflow surfaces.

## 16. Non-goals

This task does not:

- redesign sports models;
- change sportsbook providers or weights;
- modify production projections;
- create a new global CI fan-out architecture;
- replace GitHub branch protection;
- claim cryptographic user identity verification;
- remove V1;
- create additional development work after V2's declared exit conditions are satisfied.
