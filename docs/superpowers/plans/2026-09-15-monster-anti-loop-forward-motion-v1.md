# Monster Anti-Loop / Forward-Motion Control V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic anti-loop control plane that prevents duplicate proof, closed-checkpoint reopening, retry churn, approval churn, side-quest derailment, and post-finish step invention while preserving existing DevSystem safety.

**Architecture:** Add a small machine-readable policy, a checkpoint-ledger validator/state-transition module, and a forward-motion controller that consumes ledger/action context and returns deterministic decisions. Reuse existing failure triage and final gate; add one lightweight `forward-motion-contract` CI lane and a deterministic A9 replay regression.

**Tech Stack:** Python 3.12 stdlib, JSON, pytest/unittest-style assertions already used by the repo, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-09-15-monster-anti-loop-forward-motion-v1-design.md`

## Global Constraints

- Additive only; do not alter sports projection/model logic.
- Preserve sportsbook influence and official-ID contracts.
- Do not weaken `devsystem-final-gate`.
- Do not replace failure triage, failure history, regression shields, or production certification.
- Deterministic failure: 0 unchanged retries.
- Transient-capable failure: at most 1 controlled retry after inspection.
- Exactly one active blocker.
- Closed checkpoints remain closed unless contradictory evidence is supplied.
- Same proof fingerprint cannot repeat unless relevant inputs changed.
- Once exit conditions are satisfied, decision is `TASK_COMPLETE` and no new checkpoint may be created.

---

### Task 1: Checkpoint ledger contract

**Files:**
- Create: `devsystem/checkpoint_ledger_v1.py`
- Create: `tests/test_devsystem_checkpoint_ledger_v1.py`

**Interfaces:**
- Produces `validate_ledger(ledger: dict) -> dict`
- Produces `transition_checkpoint(ledger: dict, checkpoint_id: str, new_state: str, *, evidence: dict | None = None, contradictory_evidence: bool = False) -> dict`
- Enforces one ACTIVE checkpoint for sequential tasks, DONE immutability, remaining counts, active blocker uniqueness, and terminal task closure.

- [ ] Write failing tests for valid ledger, two ACTIVE checkpoints, reopening DONE without contradiction, reopening with contradiction, and terminal closure.
- [ ] Run `python -m pytest tests/test_devsystem_checkpoint_ledger_v1.py -q` and verify RED.
- [ ] Implement minimal ledger validation and transition logic.
- [ ] Re-run focused tests and verify GREEN.
- [ ] Commit.

### Task 2: Forward-motion policy and controller

**Files:**
- Create: `devsystem/forward_motion_policy_v1.json`
- Create: `devsystem/forward_motion_v1.py`
- Create: `tests/test_devsystem_forward_motion_v1.py`

**Interfaces:**
- Produces `fingerprint_action(action: dict) -> str`
- Produces `decide(ledger: dict, action: dict, history: list[dict], policy: dict | None = None) -> dict`
- Decision values: `ALLOW_ADVANCE`, `ALLOW_NEW_HYPOTHESIS`, `ALLOW_CONTROLLED_RETRY`, `REJECT_DUPLICATE_PROOF`, `REJECT_CLOSED_CHECKPOINT_REOPEN`, `DEFER_SIDE_QUEST`, `STOP_EXTERNAL_BLOCKER`, `TASK_COMPLETE`.

- [ ] Write failing tests for duplicate proof rejection, changed-input allowance, deterministic zero-retry, transient one-retry, side-quest deferral, external blocker stop, and task-complete terminal behavior.
- [ ] Run focused tests and verify RED.
- [ ] Implement policy schema and minimal deterministic controller.
- [ ] Re-run focused tests and verify GREEN.
- [ ] Commit.

### Task 3: A9 anti-loop replay regression

**Files:**
- Create: `tests/test_monster_a9_anti_loop_replay_v1.py`

**Interfaces:**
- Consumes `checkpoint_ledger_v1` and `forward_motion_v1`.
- Replays the A9 sequence from certified implementation -> identity drift -> one blocker -> stale test contract -> changed runtime -> GREEN witness -> identity pin -> final gate -> `TASK_COMPLETE`.

- [ ] Write replay test that fails if duplicate unchanged production proof is allowed, a second blocker opens, in-scope approval is required, DONE checkpoint reopens, or a post-finish checkpoint is added.
- [ ] Run replay and verify RED until controller behavior is complete.
- [ ] Make only minimal controller/ledger changes required by replay.
- [ ] Re-run all three focused test files and verify GREEN.
- [ ] Commit.

### Task 4: Permanent CI integration

**Files:**
- Modify: `.github/workflows/devsystem-targeted-ci.yml`
- Modify: `devsystem/README.md`
- Modify if required by existing final-gate test contract: tests covering DevSystem workflow/final-gate structure.

**Interfaces:**
- Adds `forward-motion-contract` lightweight job.
- Job runs policy/ledger/controller/A9 replay tests.
- `devsystem-final-gate` requires the job result whenever present, without changing existing sport lanes.

- [ ] Add failing structural/self-test expectations first where the repo has workflow contract tests.
- [ ] Add `forward-motion-contract` job before expensive sport lanes.
- [ ] Add the job to final-gate `needs` and aggregate payload.
- [ ] Update README with Monster Auto-Continue/anti-loop contract.
- [ ] Run focused DevSystem tests and YAML-relevant checks.
- [ ] Commit.

### Task 5: Final certification, merge, and freeze

**Files:**
- No temporary workflow files unless permanent CI cannot exercise the branch; if temporary machinery becomes necessary, remove it before merge.

- [ ] Open PR to protected `main`.
- [ ] Verify exact changed-file scope.
- [ ] Run `DevSystem targeted CI`; require `forward-motion-contract` and `devsystem-final-gate` GREEN.
- [ ] Fix only genuine failures that block declared exit conditions; no unrelated side quests.
- [ ] Merge with expected-head protection.
- [ ] Verify protected `main` points to merge commit and permanent files exist.
- [ ] Confirm post-merge production verification remains GREEN where triggered/applicable.
- [ ] Declare Anti-Loop V1 `DONE`; do not create another implementation checkpoint.
