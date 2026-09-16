# Monster Anti-Loop V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and permanently certify Monster Anti-Loop V2 so looping, stale retries, backward checkpoint movement, unauthorized overrides, and post-finish work cannot become authoritative DevSystem progress or pass the protected merge path.

**Architecture:** V2 adds a preventive authorization controller plus a receipt-aware append-only task ledger, then independently revalidates that ledger inside the existing `permanent-contract` CI lane. The first V2 rollout uses a narrowly scoped one-time bootstrap mode because V2 cannot authorize actions taken before V2 exists; bootstrap becomes structurally invalid as soon as protected `main` contains the V2 policy. V1 remains intact as the historical green baseline during migration.

**Tech Stack:** Python 3.12, standard library (`hashlib`, `json`, `re`, `subprocess`, `pathlib`, `copy`, `argparse`), pytest, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md`

## Global Constraints

- This is an additive DevSystem/control-plane upgrade only.
- Do not modify NFL Game Totals, NFL Spread, NFL Moneyline, Passing Yards, Rushing Yards, Receiving Yards, CFB, MLB, WNBA projection logic, market logic, sportsbook behavior, or production data-provider behavior.
- Keep V1 present and green during migration; do not delete or rewrite V1 as part of this task.
- Keep the required aggregate check name exactly `devsystem-final-gate`.
- Do not add a new broad CI fan-out workflow; integrate V2 into the existing `permanent-contract` lane.
- Deterministic unchanged retry budget is exactly `0`.
- Transient-capable retry budget is exactly `1` controlled retry after inspection.
- Unknown-failure evidence budget is exactly `1` evidence-gathering action.
- Stagnation threshold is exactly `3` meaningful no-progress actions for the same path.
- Only one active blocker is permitted.
- DONE checkpoints are immutable unless new contradictory evidence directly invalidates their closing proof.
- `TASK_COMPLETE` is terminal; a new user request starts a new task instead of inventing a new checkpoint.
- A user override is exact-action, explicit, auditable, single-use, and never a global bypass.
- V2 must not claim cryptographic proof of human authorship for ChatGPT-visible override text.
- Authorization receipts are consumed exactly once by the action record; checkpoint transitions reference the resulting authorized action-event ID and do not consume the receipt a second time.
- The rollout bootstrap is permitted only when the base revision does not contain `devsystem/forward_motion_policy_v2.json`; once V2 is on `main`, bootstrap mode must fail closed forever for ordinary future PRs.

## File Structure

### New permanent control-plane files

- `devsystem/forward_motion_policy_v2.json` — machine-readable V2 budgets, decisions, hard boundaries, progress classes, and bootstrap/override constraints.
- `devsystem/action_ledger_v2.py` — canonical serialization, receipt hashing/validation, append-only event-chain validation, single-use receipt consumption, task-ledger validation, and PR-level ledger enforcement.
- `devsystem/checkpoint_ledger_v2.py` — monotonic checkpoint validation and receipt-event-aware transitions.
- `devsystem/forward_motion_v2.py` — fingerprint normalization, retry/stagnation/root-cause decisions, blocker/terminal rules, override consumption rules, and receipt issuance.
- `devsystem/anti_loop_replay_v2.py` — deterministic adversarial replay covering V1 bypass patterns and V2-specific protections.
- `devsystem/forward_motion_contract_v2.py` — permanent V2 contract validator used by required CI.
- `devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json` — one-time activation ledger for the V2 migration itself; valid only because the base revision lacks V2.

### New tests

- `tests/test_devsystem_action_ledger_v2.py` — receipt, chain, replay, tamper, PR-enforcement, and bootstrap-expiry tests.
- `tests/test_devsystem_checkpoint_ledger_v2.py` — monotonic checkpoint and authorized-event transition tests.
- `tests/test_devsystem_forward_motion_v2.py` — retry budgets, root-cause recurrence, stagnation, blocker, terminal, and override tests.
- `tests/test_devsystem_anti_loop_replay_v2.py` — end-to-end adversarial replay test.

### Existing files modified

- `devsystem/permanent_gate_v1.py` — make V2 permanent files and workflow markers required after activation.
- `tests/test_devsystem_permanent_gate_v1.py` — assert the V2 contract is permanently executed/enforced.
- `.github/workflows/devsystem-targeted-ci.yml` — execute the V2 permanent contract and PR ledger verifier inside the existing `permanent-contract` job.
- `devsystem/README.md` — document V2 as authoritative after activation while retaining V1 as migration/history reference.

---

### Task 1: Lock the V2 policy contract

**Files:**
- Create: `devsystem/forward_motion_policy_v2.json`
- Create: `tests/test_devsystem_forward_motion_v2.py`

**Interfaces:**
- Produces policy keys consumed by later tasks: `version`, `mode`, `retry_budgets`, `stagnation`, `proof_rules`, `override_rules`, `bootstrap_rules`, `hard_boundaries`, `authorized_decisions`, `denied_decisions`, `progress_classes`.
- Later `load_policy()` must reject any version other than integer `2` or mode other than `strict_auto_continue_v2`.

- [ ] **Step 1: Write the failing policy-contract tests**

Add the first tests to `tests/test_devsystem_forward_motion_v2.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "devsystem" / "forward_motion_policy_v2.json"


def test_v2_policy_has_exact_retry_and_stagnation_budgets():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["mode"] == "strict_auto_continue_v2"
    assert payload["retry_budgets"] == {
        "deterministic-regression": 0,
        "transient-capable": 1,
        "unknown_evidence_actions": 1,
    }
    assert payload["stagnation"]["max_no_progress_actions"] == 3
    assert payload["proof_rules"]["max_active_blockers"] == 1
    assert payload["proof_rules"]["terminal_task_is_authoritative"] is True


def test_v2_policy_override_is_single_use_user_explicit_only():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["override_rules"] == {
        "allowed_source": "user_explicit",
        "single_use": True,
        "exact_action_only": True,
        "cannot_disable_policy": True,
        "cryptographic_human_identity_claim": False,
    }


def test_v2_bootstrap_self_expires_after_activation():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["bootstrap_rules"]["allowed_only_when_base_lacks_v2_policy"] is True
    assert payload["bootstrap_rules"]["single_activation"] is True
```

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: FAIL because `devsystem/forward_motion_policy_v2.json` does not exist.

- [ ] **Step 3: Create the exact policy**

Create `devsystem/forward_motion_policy_v2.json`:

```json
{
  "version": 2,
  "mode": "strict_auto_continue_v2",
  "retry_budgets": {
    "deterministic-regression": 0,
    "transient-capable": 1,
    "unknown_evidence_actions": 1
  },
  "stagnation": {
    "max_no_progress_actions": 3
  },
  "proof_rules": {
    "reject_duplicate_without_changed_inputs": true,
    "reject_same_root_cause_without_new_evidence": true,
    "closed_checkpoint_requires_contradictory_evidence": true,
    "max_active_blockers": 1,
    "defer_unrelated_findings": true,
    "terminal_task_is_authoritative": true,
    "receipt_required_for_authoritative_action": true,
    "receipt_single_use": true,
    "checkpoint_transition_references_action_event": true
  },
  "override_rules": {
    "allowed_source": "user_explicit",
    "single_use": true,
    "exact_action_only": true,
    "cannot_disable_policy": true,
    "cryptographic_human_identity_claim": false
  },
  "bootstrap_rules": {
    "allowed_only_when_base_lacks_v2_policy": true,
    "single_activation": true
  },
  "hard_boundaries": [
    "material_scope_or_architecture_change",
    "destructive_action",
    "credential_or_secret_change",
    "cost_impacting_infrastructure_change",
    "material_product_behavior_choice",
    "external_blocker_unresolvable_with_available_tools"
  ],
  "authorized_decisions": [
    "AUTHORIZED",
    "AUTHORIZED_NEW_HYPOTHESIS",
    "AUTHORIZED_CONTROLLED_RETRY",
    "AUTHORIZED_USER_OVERRIDE"
  ],
  "denied_decisions": [
    "DENIED_LOOP",
    "DENIED_STAGNATION",
    "DENIED_BACKTRACK",
    "DENIED_STALE_FAILURE",
    "DENIED_CLOSED_CHECKPOINT",
    "DENIED_UNAUTHORIZED_OVERRIDE",
    "DENIED_UNAUTHORIZED_ACTION",
    "DEFER_SIDE_QUEST",
    "STOP_EXTERNAL_BLOCKER",
    "TASK_COMPLETE"
  ],
  "progress_classes": [
    "new_evidence",
    "relevant_input_changed",
    "root_cause_narrowed",
    "blocker_resolved",
    "blocker_deferred",
    "checkpoint_closed",
    "checkpoint_advanced",
    "hypothesis_validated",
    "hypothesis_falsified",
    "no_progress"
  ]
}
```

- [ ] **Step 4: Re-run the policy tests and confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: all current V2 policy tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add devsystem/forward_motion_policy_v2.json tests/test_devsystem_forward_motion_v2.py
git commit -m "feat: lock Monster Anti-Loop V2 policy"
```

---

### Task 2: Build tamper-evident authorization receipts and the append-only action ledger

**Files:**
- Create: `devsystem/action_ledger_v2.py`
- Create: `tests/test_devsystem_action_ledger_v2.py`

**Interfaces:**
- Produces `canonical_json(payload: dict) -> str`.
- Produces `sha256_hex(value: str) -> str`.
- Produces `build_receipt(payload: dict) -> dict`.
- Produces `validate_receipt(receipt: dict) -> dict`.
- Produces `record_authorized_action(task_ledger: dict, receipt: dict, *, outcome: str, progress_class: str, evidence: dict) -> dict`.
- Produces `validate_action_ledger(task_ledger: dict) -> dict`.
- Produces `verify_pr_ledger(base: str, head: str, *, root: Path = ROOT) -> dict` and a CLI subcommand `verify-pr --base <sha> --head <sha>`.
- Receipt consumption happens exactly once in `record_authorized_action`; checkpoint transitions later reference the returned `event_id`.

- [ ] **Step 1: Write failing receipt/chain tests**

Create `tests/test_devsystem_action_ledger_v2.py` with fixtures and these core cases:

```python
from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.action_ledger_v2 import (
    ActionLedgerFailure,
    GENESIS_CHAIN_HASH,
    build_receipt,
    record_authorized_action,
    validate_action_ledger,
    validate_receipt,
)


def _ledger() -> dict:
    return {
        "version": 2,
        "task_id": "anti-loop-v2-test",
        "status": "ACTIVE",
        "action_log": {
            "head_chain_hash": GENESIS_CHAIN_HASH,
            "events": [],
            "consumed_receipts": [],
        },
        "transition_history": [],
        "override_events": [],
    }


def _receipt_payload() -> dict:
    return {
        "policy_version": 2,
        "task_id": "anti-loop-v2-test",
        "checkpoint_id": "2",
        "action_fingerprint": "a" * 64,
        "root_cause_fingerprint": "b" * 64,
        "evidence_fingerprint": "c" * 64,
        "relevant_input_fingerprint": "d" * 64,
        "decision": "AUTHORIZED",
        "previous_chain_hash": GENESIS_CHAIN_HASH,
        "event_nonce": "evt-1",
        "override_event_id": None,
    }


def test_receipt_hash_validates_and_tampering_fails_closed():
    receipt = build_receipt(_receipt_payload())
    assert validate_receipt(receipt)["status"] == "GREEN"
    tampered = deepcopy(receipt)
    tampered["payload"]["checkpoint_id"] = "99"
    with pytest.raises(ActionLedgerFailure, match="receipt hash mismatch"):
        validate_receipt(tampered)


def test_receipt_is_consumed_once_and_chain_advances():
    receipt = build_receipt(_receipt_payload())
    first = record_authorized_action(
        _ledger(),
        receipt,
        outcome="success",
        progress_class="new_evidence",
        evidence={"proof": "green"},
    )
    assert len(first["action_log"]["events"]) == 1
    assert first["action_log"]["head_chain_hash"] != GENESIS_CHAIN_HASH
    with pytest.raises(ActionLedgerFailure, match="receipt already consumed"):
        record_authorized_action(
            first,
            receipt,
            outcome="success",
            progress_class="new_evidence",
            evidence={"proof": "green"},
        )
```

Add tests that mutate an earlier event and expect chain validation to fail, that use a receipt with the wrong task/checkpoint/action identity, and that pass an unrecognized progress class.

- [ ] **Step 2: Run the new test file and confirm RED**

Run:

```bash
python -m pytest -q tests/test_devsystem_action_ledger_v2.py
```

Expected: import/file-not-found failure for `devsystem.action_ledger_v2`.

- [ ] **Step 3: Implement canonical receipt hashing and ledger validation**

Create `devsystem/action_ledger_v2.py` with these exact public shapes:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENESIS_CHAIN_HASH = "0" * 64
AUTHORIZED_DECISIONS = {
    "AUTHORIZED",
    "AUTHORIZED_NEW_HYPOTHESIS",
    "AUTHORIZED_CONTROLLED_RETRY",
    "AUTHORIZED_USER_OVERRIDE",
}
PROGRESS_CLASSES = {
    "new_evidence",
    "relevant_input_changed",
    "root_cause_narrowed",
    "blocker_resolved",
    "blocker_deferred",
    "checkpoint_closed",
    "checkpoint_advanced",
    "hypothesis_validated",
    "hypothesis_falsified",
    "no_progress",
}


class ActionLedgerFailure(RuntimeError):
    pass


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    body = deepcopy(payload)
    if body.get("decision") not in AUTHORIZED_DECISIONS:
        raise ActionLedgerFailure("denied decision cannot issue authorization receipt")
    receipt_hash = sha256_hex(canonical_json(body))
    return {"payload": body, "receipt_hash": receipt_hash}


def validate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        raise ActionLedgerFailure("receipt payload must be an object")
    expected = sha256_hex(canonical_json(payload))
    if receipt.get("receipt_hash") != expected:
        raise ActionLedgerFailure("receipt hash mismatch")
    if payload.get("decision") not in AUTHORIZED_DECISIONS:
        raise ActionLedgerFailure("receipt decision is not authorized")
    return {"status": "GREEN", "receipt_hash": expected}
```

Implement `record_authorized_action()` so it:

1. deep-copies the task ledger;
2. validates the receipt;
3. requires `payload.task_id == task_ledger.task_id`;
4. requires `payload.previous_chain_hash == action_log.head_chain_hash`;
5. rejects a `receipt_hash` already present in `consumed_receipts`;
6. requires `progress_class` in `PROGRESS_CLASSES`;
7. creates `event_id = "ACT-" + sha256_hex(receipt_hash + canonical_json(evidence))[:16].upper()`;
8. stores the immutable receipt payload/hash, outcome, progress class, and evidence in the event;
9. computes `event_chain_hash = sha256_hex(previous_chain_hash + canonical_json(event_without_event_chain_hash))`;
10. appends the event, appends the receipt hash to consumed receipts, and updates `head_chain_hash`.

Implement `validate_action_ledger()` by replaying every event from `GENESIS_CHAIN_HASH`, validating every receipt, receipt uniqueness, event identity, and chain hash. Return:

```python
{
    "status": "GREEN",
    "event_count": len(events),
    "head_chain_hash": computed_head,
    "consumed_receipt_count": len(consumed),
}
```

- [ ] **Step 4: Run receipt/chain tests and confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_devsystem_action_ledger_v2.py
```

Expected: receipt, single-use, and tamper tests PASS.

- [ ] **Step 5: Add RED tests for PR-level enforcement and self-expiring bootstrap**

Use a temporary git repository in the test file. Cover these exact cases:

```python
def test_normal_code_pr_requires_exactly_one_valid_changed_task_ledger(tmp_path):
    # base already contains V2 policy; head changes app code but no task ledger
    # verify_pr_ledger(...) must raise ActionLedgerFailure.
    ...


def test_bootstrap_allowed_only_when_base_lacks_v2_policy(tmp_path):
    # base lacks policy, head adds V2 policy + exact bootstrap ledger => GREEN.
    ...


def test_bootstrap_rejected_after_v2_exists_on_base(tmp_path):
    # base contains policy; head tries activation_mode=v2-bootstrap => fail closed.
    ...
```

The normal future PR rule is: any PR with non-documentation changes must change exactly one `devsystem/task_ledgers/*.json` file whose ledger validates and finishes in `DONE`. Documentation-only changes under `docs/` are exempt from the task-ledger requirement.

- [ ] **Step 6: Implement `verify_pr_ledger()` and CLI**

Implement these helpers:

```python
def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ActionLedgerFailure(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _base_has_v2_policy(base: str, root: Path) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{base}:devsystem/forward_motion_policy_v2.json"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0
```

`verify_pr_ledger()` must:

- get changed files with `git diff --name-only base head`;
- return `{"status": "GREEN", "mode": "docs-only"}` if every changed file is below `docs/`;
- find changed files matching `devsystem/task_ledgers/*.json`;
- if base already has V2 policy: reject `activation_mode == "v2-bootstrap"`; require exactly one changed ledger, validate it, and require `status == "DONE"`;
- if base lacks V2 policy: permit bootstrap only when the head adds the V2 policy, exactly one changed ledger exists, `activation_mode == "v2-bootstrap"`, and `bootstrap_scope` contains only V2 control-plane/test/docs/workflow files declared by this implementation plan;
- fail closed on zero or multiple task ledgers for a non-doc future PR.

Add an `argparse` entry point:

```bash
python devsystem/action_ledger_v2.py verify-pr --base "$BASE_SHA" --head "$HEAD_SHA"
```

- [ ] **Step 7: Run all Task 2 tests and confirm GREEN**

```bash
python -m pytest -q tests/test_devsystem_action_ledger_v2.py
```

Expected: all tests PASS, including bootstrap expiry.

- [ ] **Step 8: Commit Task 2**

```bash
git add devsystem/action_ledger_v2.py tests/test_devsystem_action_ledger_v2.py
git commit -m "feat: add V2 authorization receipt ledger"
```

---

### Task 3: Build the receipt-event-aware monotonic checkpoint ledger

**Files:**
- Create: `devsystem/checkpoint_ledger_v2.py`
- Create: `tests/test_devsystem_checkpoint_ledger_v2.py`

**Interfaces:**
- Produces `validate_checkpoint_ledger(task_ledger: dict) -> dict`.
- Produces `transition_checkpoint(task_ledger: dict, checkpoint_id: str, new_state: str, *, authorized_event_id: str, evidence: dict | None = None, contradictory_evidence: dict | None = None) -> dict`.
- Consumes action events already recorded by `record_authorized_action()`; it never consumes a receipt itself.

- [ ] **Step 1: Write failing monotonic-transition tests**

Create `tests/test_devsystem_checkpoint_ledger_v2.py` covering:

```python
def test_done_checkpoint_cannot_reopen_without_contradictory_evidence():
    with pytest.raises(CheckpointLedgerV2Failure, match="contradictory evidence"):
        transition_checkpoint(
            ledger_with_cp1_done_cp2_active(),
            "1",
            "ACTIVE",
            authorized_event_id="ACT-VALID-FOR-REOPEN",
        )


def test_transition_requires_existing_unused_authorized_action_event():
    with pytest.raises(CheckpointLedgerV2Failure, match="authorized action event"):
        transition_checkpoint(
            ledger_with_cp2_active(),
            "2",
            "DONE",
            authorized_event_id="ACT-MISSING",
            evidence={"proof": "green"},
        )


def test_final_checkpoint_closure_sets_terminal_state():
    updated = transition_checkpoint(
        ledger_with_valid_close_event(),
        "2",
        "DONE",
        authorized_event_id="ACT-CLOSE-2",
        evidence={"contract": "GREEN"},
    )
    assert updated["status"] == "DONE"
    assert updated["current_checkpoint"] is None
    assert updated["remaining_checkpoints"] == 0
```

Also test that one action event cannot transition two checkpoints and that an ACTIVE task has exactly one ACTIVE checkpoint.

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m pytest -q tests/test_devsystem_checkpoint_ledger_v2.py
```

Expected: import/file-not-found failure.

- [ ] **Step 3: Implement checkpoint validation and transitions**

Create `devsystem/checkpoint_ledger_v2.py` with:

```python
CHECKPOINT_STATES = {"PENDING", "ACTIVE", "DONE", "BLOCKED", "DEFERRED"}
TASK_STATES = {"ACTIVE", "DONE", "BLOCKED", "FAILED"}


class CheckpointLedgerV2Failure(RuntimeError):
    pass
```

`validate_checkpoint_ledger()` must enforce:

- non-empty unique checkpoint IDs;
- exact total/completed/remaining counts;
- exactly one ACTIVE checkpoint when task status is ACTIVE;
- current checkpoint points at that ACTIVE checkpoint;
- at most one active blocker;
- DONE task => every checkpoint DONE, current checkpoint null, blocker null, remaining 0;
- every `transition_history.authorized_event_id` exists in `action_log.events` and is unique within transition history.

`transition_checkpoint()` must:

- locate the authorized action event;
- reject if already used by another transition;
- require the action event's receipt payload task/checkpoint to match the target;
- reject backward movement from DONE without non-empty `contradictory_evidence`;
- require closing evidence for DONE;
- auto-activate only the next PENDING checkpoint in declared order;
- set `TASK_COMPLETE` state only when the final checkpoint closes;
- append a transition-history record referencing `authorized_event_id`.

- [ ] **Step 4: Run Task 3 tests and confirm GREEN**

```bash
python -m pytest -q tests/test_devsystem_checkpoint_ledger_v2.py
```

Expected: all checkpoint tests PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add devsystem/checkpoint_ledger_v2.py tests/test_devsystem_checkpoint_ledger_v2.py
git commit -m "feat: enforce monotonic V2 checkpoints"
```

---

### Task 4: Build the V2 forward-motion authorization engine

**Files:**
- Create: `devsystem/forward_motion_v2.py`
- Modify: `tests/test_devsystem_forward_motion_v2.py`

**Interfaces:**
- Produces `load_policy() -> dict`.
- Produces `fingerprint_action(action: dict) -> str`.
- Produces `fingerprint_root_cause(action: dict) -> str`.
- Produces `fingerprint_evidence(action: dict) -> str`.
- Produces `fingerprint_relevant_inputs(action: dict) -> str`.
- Produces `decide(task_ledger: dict, action: dict, history: list[dict], policy: dict | None = None, override_event: dict | None = None) -> dict`.
- Positive decisions contain `receipt`; denied decisions never contain `receipt`.

- [ ] **Step 1: Add failing fingerprint and retry-budget tests**

Append tests proving volatile metadata does not disguise the same root cause:

```python
def test_root_cause_fingerprint_ignores_run_ids_timestamps_and_command_order():
    first = _action(
        failure={
            "job": "browser-qa",
            "layer": "ui-browser",
            "evidence_signal": "browser-selector-race",
            "message": "TimeoutError run 100 at 2026-09-15T10:00:00Z --foo --bar",
        }
    )
    second = _action(
        failure={
            "job": "browser-qa",
            "layer": "ui-browser",
            "evidence_signal": "browser-selector-race",
            "message": "TimeoutError run 999 at 2026-09-15T11:00:00Z --bar --foo",
        }
    )
    assert fingerprint_root_cause(first) == fingerprint_root_cause(second)
```

Add tests for:

- exact duplicate action => `DENIED_LOOP`;
- deterministic unchanged retry => `DENIED_STALE_FAILURE` and no receipt;
- first inspected transient retry => `AUTHORIZED_CONTROLLED_RETRY` with receipt;
- second transient retry => denied;
- unknown failure => one evidence action, second broad evidence action denied;
- unrelated action => `DEFER_SIDE_QUEST`;
- second blocker => `DEFER_SIDE_QUEST`;
- DONE task => `TASK_COMPLETE` without receipt.

- [ ] **Step 2: Run targeted tests and confirm RED**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: failures because V2 engine functions do not exist.

- [ ] **Step 3: Implement stable normalization and fingerprints**

Create `devsystem/forward_motion_v2.py` and include a normalizer that strips only volatile identity while retaining failure semantics:

```python
_VOLATILE_KEYS = {
    "run_id",
    "workflow_run_id",
    "timestamp",
    "created_at",
    "updated_at",
    "retry_counter",
    "display_branch",
}


def _stable_payload(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _stable_payload(item)
            for key, item in sorted(value.items())
            if str(key) not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_stable_payload(item) for item in value]
    if isinstance(value, str):
        text = value.lower().strip()
        text = re.sub(r"https?://\S+", "<url>", text)
        text = re.sub(r"\b[0-9a-f]{7,64}\b", "<hex>", text)
        text = re.sub(r"\b\d{4}-\d{2}-\d{2}t\S+z\b", "<timestamp>", text)
        text = re.sub(r"\brun\s+\d+\b", "run <n>", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    return value
```

Do not sort arbitrary command tokens globally; instead make `fingerprint_root_cause()` derive from structured `failure.job`, `failure.layer`, `failure.evidence_signal`, `failure.error_family`, and normalized `failure.message`. Tests that compare command-order variants must put command flags outside these semantic root-cause fields so superficial command ordering cannot alter the root cause.

Use SHA-256 hex digests for action/root/evidence/relevant-input fingerprints.

- [ ] **Step 4: Implement `decide()` without override support yet**

Decision order must be deterministic:

1. validate task/checkpoint identity;
2. if task DONE => `TASK_COMPLETE`;
3. reject/defer scope/backtrack/blocker violations;
4. compute all four fingerprints;
5. apply deterministic/transient/unknown retry budgets;
6. detect same root cause with unchanged evidence and unchanged relevant inputs;
7. detect exact duplicate action;
8. detect stagnation window;
9. allow a genuinely new discriminating hypothesis;
10. otherwise authorize forward progress.

Use `build_receipt()` from `devsystem.action_ledger_v2` only for positive decisions.

A positive result must look like:

```python
{
    "decision": "AUTHORIZED",
    "reason": "action advances the active checkpoint",
    "action_fingerprint": action_fp,
    "root_cause_fingerprint": root_fp,
    "evidence_fingerprint": evidence_fp,
    "relevant_input_fingerprint": input_fp,
    "receipt": receipt,
}
```

A denied result must omit `receipt`.

- [ ] **Step 5: Run retry/fingerprint tests and confirm GREEN**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: all non-override V2 decision tests PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add devsystem/forward_motion_v2.py tests/test_devsystem_forward_motion_v2.py
git commit -m "feat: add Monster Anti-Loop V2 decision engine"
```

---

### Task 5: Add stagnation lock, closed-root-cause protection, and exact user-only override semantics

**Files:**
- Modify: `devsystem/forward_motion_v2.py`
- Modify: `tests/test_devsystem_forward_motion_v2.py`

**Interfaces:**
- `decide(..., override_event=None)` becomes complete.
- Override event schema is exact and single-use:

```python
{
    "event_id": "OVR-...",
    "source": "user_explicit",
    "task_id": "...",
    "checkpoint_id": "...",
    "blocked_action_fingerprint": "...",
    "denial_fingerprint": "...",
    "reason": "...",
    "consumed": False
}
```

- [ ] **Step 1: Add failing stagnation tests**

Add:

```python
def test_three_same_path_no_progress_actions_trigger_stagnation_lock():
    history = [
        _history(root="ROOT-X", progress_class="no_progress", evidence="E1", inputs="I1"),
        _history(root="ROOT-X", progress_class="no_progress", evidence="E1", inputs="I1"),
        _history(root="ROOT-X", progress_class="no_progress", evidence="E1", inputs="I1"),
    ]
    result = decide(_active_ledger(), _action(root_cause_hint="ROOT-X"), history)
    assert result["decision"] == "DENIED_STAGNATION"
    assert "receipt" not in result
```

Add a complementary test showing a materially changed relevant-input fingerprint resets the proof path and allows a fresh action.

- [ ] **Step 2: Add failing closed-root-cause tests**

Add a `resolved_root_causes` structure to the ledger fixture and verify:

- same resolved root cause + no contradictory evidence => `DENIED_STALE_FAILURE`;
- same root cause + explicit contradictory evidence with a new evidence fingerprint => `AUTHORIZED_NEW_HYPOTHESIS`.

- [ ] **Step 3: Add failing override tests**

Cover all of these:

1. `source != "user_explicit"` => `DENIED_UNAUTHORIZED_OVERRIDE`.
2. wrong task/checkpoint => denied.
3. wrong blocked action fingerprint => denied.
4. missing denial reference => denied.
5. `consumed is True` => denied.
6. valid exact override => `AUTHORIZED_USER_OVERRIDE` and receipt includes `override_event_id`.
7. using the override does not change policy retry budgets.
8. an override cannot authorize a different action.

- [ ] **Step 4: Run tests and confirm RED**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: new stagnation/root-cause/override cases fail.

- [ ] **Step 5: Implement stagnation and resolved-root-cause checks**

Count consecutive meaningful events for the same root-cause/path since the last event whose progress class is not `no_progress` or whose evidence/relevant-input fingerprint changed. At `3` no-progress actions, return `DENIED_STAGNATION`.

A ledger entry under `resolved_root_causes` must have:

```python
{
    "root_cause_fingerprint": "...",
    "closing_evidence_fingerprint": "...",
    "closed_by_event_id": "ACT-..."
}
```

If a proposed action matches one of these and does not provide `contradictory_evidence=True` plus a different non-empty evidence fingerprint, deny it.

- [ ] **Step 6: Implement exact override consumption checks**

Do not provide a helper that invents an override from agent reasoning. `decide()` may only consume the externally supplied `override_event` object after structurally validating all fields against the current denied action context.

When valid, issue a receipt with decision `AUTHORIZED_USER_OVERRIDE` and the override event ID embedded in the receipt payload. The later action record must preserve that ID for CI audit.

- [ ] **Step 7: Run full V2 engine tests and confirm GREEN**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: all V2 engine tests PASS.

- [ ] **Step 8: Commit Task 5**

```bash
git add devsystem/forward_motion_v2.py tests/test_devsystem_forward_motion_v2.py
git commit -m "feat: harden V2 stagnation and override controls"
```

---

### Task 6: Build the V2 adversarial anti-loop replay

**Files:**
- Create: `devsystem/anti_loop_replay_v2.py`
- Create: `tests/test_devsystem_anti_loop_replay_v2.py`

**Interfaces:**
- Produces `run_replay() -> dict`.
- Must use the real V2 controller, action ledger, and checkpoint ledger; no duplicated mock decision logic.

- [ ] **Step 1: Write the failing replay contract test**

Create `tests/test_devsystem_anti_loop_replay_v2.py`:

```python
from devsystem.anti_loop_replay_v2 import run_replay


def test_v2_adversarial_replay_is_green():
    result = run_replay()
    assert result["status"] == "GREEN"
    assert result["exact_duplicates_denied"] >= 1
    assert result["semantic_root_cause_loops_denied"] >= 2
    assert result["stagnation_locks"] >= 1
    assert result["closed_checkpoint_reopens_denied"] >= 1
    assert result["second_blockers_deferred"] >= 1
    assert result["invalid_overrides_denied"] >= 1
    assert result["valid_single_use_overrides"] == 1
    assert result["receipt_replays_denied"] >= 1
    assert result["tamper_attempts_denied"] >= 1
    assert result["final_task_status"] == "DONE"
    assert result["remaining_checkpoints"] == 0
    assert result["post_finish_decision"] == "TASK_COMPLETE"
    assert result["invented_post_finish_checkpoints"] == 0
```

- [ ] **Step 2: Run the replay test and confirm RED**

```bash
python -m pytest -q tests/test_devsystem_anti_loop_replay_v2.py
```

Expected: import/file-not-found failure.

- [ ] **Step 3: Implement the adversarial replay**

The replay must execute, in order, all 20 cases from the approved spec:

1. exact duplicate action;
2. same root cause with new run ID;
3. same root cause with superficial command metadata change;
4. deterministic retry without repair;
5. first transient controlled retry allowed, second denied;
6. unknown failure one evidence action, second broad evidence action denied;
7. three no-progress actions => stagnation;
8. materially changed relevant input => fresh action allowed;
9. genuinely new discriminating hypothesis allowed;
10. DONE checkpoint reopen without contradiction denied;
11. controlled reopen with valid contradictory evidence allowed;
12. second blocker deferred;
13. unrelated finding deferred;
14. receipt replay denied;
15. receipt action/checkpoint/input mismatch denied;
16. edited earlier ledger event breaks chain;
17. self-declared/invalid override denied;
18. exact valid user override allowed once;
19. override reuse denied;
20. post-`TASK_COMPLETE` action returns `TASK_COMPLETE` and creates no checkpoint.

Use the real `record_authorized_action()` and `transition_checkpoint()` functions for allowed paths.

- [ ] **Step 4: Run V1 and V2 replays together**

```bash
python devsystem/a9_anti_loop_replay_v1.py
python devsystem/anti_loop_replay_v2.py
python -m pytest -q tests/test_devsystem_anti_loop_replay_v2.py
```

Expected:

- `MONSTER_A9_ANTI_LOOP_REPLAY_GREEN`
- `MONSTER_ANTI_LOOP_V2_REPLAY_GREEN`
- pytest PASS

- [ ] **Step 5: Commit Task 6**

```bash
git add devsystem/anti_loop_replay_v2.py tests/test_devsystem_anti_loop_replay_v2.py
git commit -m "test: add V2 adversarial anti-loop replay"
```

---

### Task 7: Build the permanent V2 contract validator

**Files:**
- Create: `devsystem/forward_motion_contract_v2.py`
- Modify: `tests/test_devsystem_permanent_gate_v1.py`

**Interfaces:**
- Produces `validate() -> dict` and prints `DEVSYSTEM_FORWARD_MOTION_V2_CONTRACT_GREEN` on success.
- This validator is dependency-light and callable directly by CI.

- [ ] **Step 1: Add a failing permanent-contract test**

Append to `tests/test_devsystem_permanent_gate_v1.py`:

```python
def test_forward_motion_v2_contract_is_permanently_enforced():
    contract = _load(
        "forward_motion_contract_v2",
        "devsystem/forward_motion_contract_v2.py",
    )
    result = contract.validate()
    assert result["status"] == "GREEN"
    assert result["mode"] == "strict_auto_continue_v2"
    assert result["semantic_root_cause_guard"] is True
    assert result["stagnation_guard"] is True
    assert result["monotonic_checkpoint_guard"] is True
    assert result["single_use_receipts"] is True
    assert result["receipt_chain_tamper_guard"] is True
    assert result["terminal_task_authoritative"] is True
    assert result["user_override_exact_single_use"] is True
    assert result["bootstrap_self_expiring"] is True
    assert result["v1_replay_still_green"] is True
    assert result["v2_replay_green"] is True
```

- [ ] **Step 2: Run the permanent-gate test and confirm RED**

```bash
python -m pytest -q tests/test_devsystem_permanent_gate_v1.py::test_forward_motion_v2_contract_is_permanently_enforced
```

Expected: file-not-found failure for V2 contract.

- [ ] **Step 3: Implement `forward_motion_contract_v2.py`**

The validator must:

- load V2 policy and assert exact budgets/mode;
- construct deterministic in-memory task ledgers;
- prove exact duplicate rejection;
- prove deterministic zero retry;
- prove transient single retry;
- prove unknown evidence budget;
- prove semantic root-cause recurrence block;
- prove three-action stagnation lock;
- prove relevant input change permits fresh proof;
- prove monotonic checkpoint rules;
- prove receipt single-use and tamper detection;
- prove one active blocker and side-quest deferral;
- prove terminal task behavior;
- prove invalid override rejection and valid single-use exact override behavior;
- prove bootstrap verifier allows only base-without-V2 activation and rejects bootstrap when base already has V2;
- call V1 `run_replay()` and require GREEN;
- call V2 `run_replay()` and require GREEN.

Return:

```python
{
    "status": "GREEN",
    "mode": "strict_auto_continue_v2",
    "semantic_root_cause_guard": True,
    "stagnation_guard": True,
    "monotonic_checkpoint_guard": True,
    "single_use_receipts": True,
    "receipt_chain_tamper_guard": True,
    "terminal_task_authoritative": True,
    "user_override_exact_single_use": True,
    "bootstrap_self_expiring": True,
    "v1_replay_still_green": True,
    "v2_replay_green": True,
}
```

- [ ] **Step 4: Run the direct validator and permanent test**

```bash
python devsystem/forward_motion_contract_v2.py
python -m pytest -q tests/test_devsystem_permanent_gate_v1.py::test_forward_motion_v2_contract_is_permanently_enforced
```

Expected: direct GREEN marker and pytest PASS.

- [ ] **Step 5: Commit Task 7**

```bash
git add devsystem/forward_motion_contract_v2.py tests/test_devsystem_permanent_gate_v1.py
git commit -m "feat: certify permanent Anti-Loop V2 contract"
```

---

### Task 8: Wire V2 into the existing permanent CI gate and create the one-time activation ledger

**Files:**
- Modify: `devsystem/permanent_gate_v1.py`
- Modify: `tests/test_devsystem_permanent_gate_v1.py`
- Modify: `.github/workflows/devsystem-targeted-ci.yml`
- Modify: `devsystem/README.md`
- Create: `devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json`

**Interfaces:**
- Existing `devsystem-final-gate` name remains unchanged.
- Existing `permanent-contract` job becomes the enforcement point for the V2 contract and PR ledger verifier.
- Bootstrap ledger is accepted only for this activation because the base commit lacks V2 policy.

- [ ] **Step 1: Add failing permanent-file/workflow-marker assertions**

Extend `devsystem/permanent_gate_v1.py` required file list with:

```python
"devsystem/forward_motion_policy_v2.json",
"devsystem/action_ledger_v2.py",
"devsystem/checkpoint_ledger_v2.py",
"devsystem/forward_motion_v2.py",
"devsystem/anti_loop_replay_v2.py",
"devsystem/forward_motion_contract_v2.py",
"tests/test_devsystem_action_ledger_v2.py",
"tests/test_devsystem_checkpoint_ledger_v2.py",
"tests/test_devsystem_forward_motion_v2.py",
"tests/test_devsystem_anti_loop_replay_v2.py",
```

Add required workflow markers:

```python
"python devsystem/forward_motion_contract_v2.py",
"python devsystem/action_ledger_v2.py verify-pr",
```

Add returned permanent flags:

```python
"forward_motion_v2_permanent": True,
"forward_motion_v2_pr_enforcement": True,
```

Update `tests/test_devsystem_permanent_gate_v1.py` to assert both flags.

- [ ] **Step 2: Run the permanent contract and confirm RED**

```bash
python -m pytest -q tests/test_devsystem_permanent_gate_v1.py
```

Expected: marker/required-file assertions fail until workflow wiring and bootstrap ledger are present.

- [ ] **Step 3: Wire V2 into the existing `permanent-contract` job**

Inside `.github/workflows/devsystem-targeted-ci.yml`, after the existing permanent DevSystem validation step and before the permanent-contract pytest step, add:

```yaml
      - name: Validate Monster Anti-Loop V2 hard gate
        env:
          EVENT_NAME: ${{ github.event_name }}
          PR_BASE: ${{ github.event.pull_request.base.sha }}
          PR_HEAD: ${{ github.event.pull_request.head.sha }}
        shell: bash
        run: |
          set -euo pipefail
          python devsystem/forward_motion_contract_v2.py
          if [ "$EVENT_NAME" = "pull_request" ]; then
            python devsystem/action_ledger_v2.py verify-pr \
              --base "$PR_BASE" \
              --head "$PR_HEAD"
          fi
```

Do not add a new workflow or new fan-out job.

- [ ] **Step 4: Create the one-time bootstrap activation ledger**

Create `devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json` with:

```json
{
  "version": 2,
  "task_id": "monster-anti-loop-v2-activation",
  "title": "Monster Anti-Loop V2 activation",
  "activation_mode": "v2-bootstrap",
  "status": "DONE",
  "current_checkpoint": null,
  "total_checkpoints": 6,
  "completed_checkpoints": 6,
  "remaining_checkpoints": 0,
  "active_blocker": null,
  "bootstrap_reason": "V2 cannot authorize actions performed before V2 exists; V1 is the certified migration baseline.",
  "bootstrap_scope": [
    "devsystem/forward_motion_policy_v2.json",
    "devsystem/action_ledger_v2.py",
    "devsystem/checkpoint_ledger_v2.py",
    "devsystem/forward_motion_v2.py",
    "devsystem/anti_loop_replay_v2.py",
    "devsystem/forward_motion_contract_v2.py",
    "devsystem/permanent_gate_v1.py",
    "devsystem/README.md",
    "devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json",
    "tests/test_devsystem_action_ledger_v2.py",
    "tests/test_devsystem_checkpoint_ledger_v2.py",
    "tests/test_devsystem_forward_motion_v2.py",
    "tests/test_devsystem_anti_loop_replay_v2.py",
    "tests/test_devsystem_permanent_gate_v1.py",
    ".github/workflows/devsystem-targeted-ci.yml",
    "docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md",
    "docs/superpowers/plans/2026-09-15-monster-anti-loop-v2-implementation.md"
  ],
  "action_log": {
    "head_chain_hash": "BOOTSTRAP-V2-ACTIVATION",
    "events": [],
    "consumed_receipts": []
  },
  "transition_history": [],
  "override_events": [],
  "checkpoints": [
    {"id": "1", "state": "DONE", "evidence": {"approved_spec": true}},
    {"id": "2", "state": "DONE", "evidence": {"policy_and_receipts": "GREEN"}},
    {"id": "3", "state": "DONE", "evidence": {"checkpoint_monotonicity": "GREEN"}},
    {"id": "4", "state": "DONE", "evidence": {"decision_engine": "GREEN"}},
    {"id": "5", "state": "DONE", "evidence": {"adversarial_replay": "GREEN"}},
    {"id": "6", "state": "DONE", "evidence": {"permanent_contract": "GREEN"}}
  ]
}
```

The bootstrap validator must treat the action-log sentinel as valid only in `activation_mode == "v2-bootstrap"` and only when `_base_has_v2_policy(base)` is false. Normal future ledgers may never use the bootstrap sentinel.

- [ ] **Step 5: Update README with authoritative post-activation behavior**

Document:

- V1 remains historical/reference compatibility;
- V2 is authoritative after activation;
- every non-doc PR after activation needs exactly one valid changed task ledger;
- no valid receipt means no authoritative progress;
- exact root-cause recurrence/stagnation rules;
- user-only override limitation and single-use behavior;
- bootstrap is one-time and self-expiring;
- stable final gate remains `devsystem-final-gate`.

- [ ] **Step 6: Run permanent contract and all V2 tests**

```bash
python devsystem/permanent_gate_v1.py
python devsystem/forward_motion_contract_v2.py
python -m pytest -q \
  tests/test_devsystem_action_ledger_v2.py \
  tests/test_devsystem_checkpoint_ledger_v2.py \
  tests/test_devsystem_forward_motion_v2.py \
  tests/test_devsystem_anti_loop_replay_v2.py \
  tests/test_devsystem_permanent_gate_v1.py
```

Expected: all GREEN/PASS.

- [ ] **Step 7: Verify V1 remains green**

```bash
python devsystem/forward_motion_contract_v1.py
python devsystem/a9_anti_loop_replay_v1.py
```

Expected:

- `DEVSYSTEM_FORWARD_MOTION_CONTRACT_GREEN`
- `MONSTER_A9_ANTI_LOOP_REPLAY_GREEN`

- [ ] **Step 8: Commit Task 8**

```bash
git add \
  devsystem/permanent_gate_v1.py \
  devsystem/README.md \
  devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json \
  tests/test_devsystem_permanent_gate_v1.py \
  .github/workflows/devsystem-targeted-ci.yml
git commit -m "feat: enforce Anti-Loop V2 in permanent CI"
```

---

### Task 9: Final freeze-scope certification, PR gates, merge, and post-merge proof

**Files:**
- No new runtime files.
- Verification only unless a deterministic in-scope defect is found.

**Interfaces:**
- Exit condition: V2 permanent contract is GREEN on the exact PR head, existing required DevSystem lanes are GREEN, diff contains only approved control-plane/test/docs/workflow files, and protected `main` points to the merge result.

- [ ] **Step 1: Run the complete local/dependency-light contract suite**

```bash
python devsystem/forward_motion_contract_v1.py
python devsystem/forward_motion_contract_v2.py
python devsystem/a9_anti_loop_replay_v1.py
python devsystem/anti_loop_replay_v2.py
python devsystem/permanent_gate_v1.py
python -m pytest -q \
  tests/test_devsystem_action_ledger_v2.py \
  tests/test_devsystem_checkpoint_ledger_v2.py \
  tests/test_devsystem_forward_motion_v2.py \
  tests/test_devsystem_anti_loop_replay_v2.py \
  tests/test_devsystem_permanent_gate_v1.py
```

Expected: zero failures.

- [ ] **Step 2: Compile every new/modified Python control-plane file**

```bash
python -m py_compile \
  devsystem/action_ledger_v2.py \
  devsystem/checkpoint_ledger_v2.py \
  devsystem/forward_motion_v2.py \
  devsystem/anti_loop_replay_v2.py \
  devsystem/forward_motion_contract_v2.py \
  devsystem/permanent_gate_v1.py
```

Expected: exit code 0.

- [ ] **Step 3: Verify the exact diff against the latest protected main**

Allowed implementation paths are only:

```text
.github/workflows/devsystem-targeted-ci.yml
devsystem/README.md
devsystem/action_ledger_v2.py
devsystem/anti_loop_replay_v2.py
devsystem/checkpoint_ledger_v2.py
devsystem/forward_motion_contract_v2.py
devsystem/forward_motion_policy_v2.json
devsystem/forward_motion_v2.py
devsystem/permanent_gate_v1.py
devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json
tests/test_devsystem_action_ledger_v2.py
tests/test_devsystem_anti_loop_replay_v2.py
tests/test_devsystem_checkpoint_ledger_v2.py
tests/test_devsystem_forward_motion_v2.py
tests/test_devsystem_permanent_gate_v1.py
docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md
docs/superpowers/plans/2026-09-15-monster-anti-loop-v2-implementation.md
```

Any sports runtime/model/page/provider file in the diff is a hard failure and must be removed before certification.

- [ ] **Step 4: Verify bootstrap really expires against a base that already contains V2**

Create a temporary test ref/repository state where the base includes `forward_motion_policy_v2.json`, then run the PR verifier against a head that attempts `activation_mode=v2-bootstrap`.

Expected: fail closed with a message containing `bootstrap is invalid after V2 activation`.

Then run the same verifier against a normal future-style DONE ledger with a valid receipt chain.

Expected: GREEN.

- [ ] **Step 5: Open/update the PR with the exact contract**

PR body must state:

- V2 is control-plane only;
- sports/runtime/model surfaces are untouched;
- V1 remains intact;
- V2 adds preventive receipts + CI verification;
- root-cause loops and three-action stagnation are blocked;
- user override is exact/single-use and is not falsely presented as cryptographic human identity proof;
- first rollout bootstrap is self-expiring and impossible once V2 is present on base;
- stable final gate remains `devsystem-final-gate`.

- [ ] **Step 6: Wait for the exact required CI lanes and inspect failures once**

Required evidence on the exact PR head:

- `permanent-contract` GREEN;
- `regression-shield` GREEN;
- all affected required lanes GREEN or intentionally skipped under the existing classifier;
- `devsystem-final-gate` GREEN.

If a deterministic failure occurs, do not retry unchanged. Inspect the failed step/log once, form one discriminating hypothesis, repair only the failing control-plane layer, and rerun on changed inputs.

If a transient-capable failure occurs, permit at most one inspected controlled retry.

- [ ] **Step 7: Re-run exact changed-file verification after the final repair commit**

Compare protected `main` to the final PR head again. Require:

- zero sports/runtime/model/provider files changed;
- only approved control-plane/test/docs/workflow paths;
- branch not behind protected main, or deliberately reconcile before merge;
- final head SHA matches the SHA whose required gates are GREEN.

- [ ] **Step 8: Merge only after the existing final gate is GREEN**

Use the repository's normal protected merge path. Do not weaken branch protection or rename the required gate.

- [ ] **Step 9: Verify protected main after merge**

Freshly read `main` and verify:

- merge result is the new main head;
- `devsystem/forward_motion_policy_v2.json` exists on main;
- `devsystem-final-gate` remains the stable required check;
- V2 permanent contract is present;
- no frozen sports surfaces changed.

- [ ] **Step 10: Prove bootstrap is now permanently dead**

Against the new protected main, run/test the PR verifier with `activation_mode=v2-bootstrap`.

Expected: `DENIED`/exception because the base now contains V2.

Record the post-merge proof as the closing evidence for the activation task.

- [ ] **Step 11: Declare terminal state**

Only after all Step 9 exit conditions are verified, report:

```text
MONSTER_ANTI_LOOP_V2_TASK_COMPLETE
Steps remaining: 0
```

Do not invent a V2.1, extra certification step, cleanup checkpoint, or V1 deletion task. Any future improvement is a new explicitly scoped task.

---

## Plan Self-Review Checklist

Before execution begins, verify this plan against the approved spec:

- [ ] Every spec section has an implementation task.
- [ ] No `TBD`, `TODO`, `implement later`, vague error-handling instruction, or unnamed test remains.
- [ ] Receipt is consumed once by the action record, never again by checkpoint transition.
- [ ] Root-cause fingerprint ignores volatile run metadata but retains semantic failure identity.
- [ ] Stagnation threshold is exactly 3.
- [ ] Deterministic/transient/unknown budgets are exactly 0/1/1.
- [ ] Override is exact-action and single-use; no controller self-authorization helper exists.
- [ ] V1 replay remains required during migration.
- [ ] Bootstrap is accepted only when base lacks V2 policy and becomes invalid after merge.
- [ ] Future non-doc PRs require exactly one changed valid DONE task ledger.
- [ ] Existing `devsystem-final-gate` name is unchanged.
- [ ] No sports runtime/model/page/provider file is in the allowed diff.
