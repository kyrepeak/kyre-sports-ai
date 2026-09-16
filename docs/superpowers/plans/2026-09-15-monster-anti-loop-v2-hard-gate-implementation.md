# Monster Anti-Loop V2 Hard-Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and permanently certify Monster Anti-Loop V2 so repeated root causes, stale retries, backward checkpoint movement, unauthorized overrides, receipt bypasses, and post-finish work cannot become authoritative DevSystem progress or pass the protected merge path.

**Architecture:** V2 adds a preventive authorization controller, single-use authorization receipts, an append-only hash-chained action ledger, receipt-event-aware monotonic checkpoints, and independent verification inside the existing `permanent-contract` CI lane. The first V2 rollout uses a narrowly scoped self-expiring bootstrap because V2 cannot authorize actions performed before V2 exists; that mode becomes invalid once the base revision contains the V2 policy. V1 remains untouched as the migration baseline and historical replay.

**Tech Stack:** Python 3.12, Python standard library (`argparse`, `copy`, `hashlib`, `json`, `pathlib`, `re`, `subprocess`, `typing`), pytest, Git, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md`

## Global Constraints

- Control-plane only. Do not change any sports model, projection, market, page, sportsbook, provider, or runtime implementation.
- NFL Game Totals, Spread, Moneyline, Passing, Rushing, Receiving, CFB, MLB, and WNBA behavior remain frozen.
- Keep V1 code and V1 replay intact during migration.
- Keep the required aggregate check name exactly `devsystem-final-gate`.
- Reuse the existing `permanent-contract` lane; do not add a broad fan-out workflow.
- Deterministic unchanged retry budget: `0`.
- Transient-capable controlled retry budget: `1`, after inspection.
- Unknown-failure evidence-gathering budget: `1`.
- Stagnation threshold: `3` same-path actions without measurable progress.
- Maximum active blockers: `1`.
- DONE checkpoints may reopen only with new contradictory evidence tied to the previous closing proof.
- `TASK_COMPLETE` is terminal for that task.
- A user override is exact-action, explicit, auditable, and single-use; it never disables V2 globally.
- V2 must not claim cryptographic proof that ChatGPT-visible override text was authored by the human account holder.
- A receipt is consumed exactly once by the action record. A checkpoint transition references the resulting action-event ID; it never consumes the receipt again.
- The bootstrap is legal only when the base revision lacks `devsystem/forward_motion_policy_v2.json`. After V2 reaches protected `main`, bootstrap mode must fail closed.
- Normal future non-documentation PRs must change exactly one valid task ledger under `devsystem/task_ledgers/`, and that ledger must be terminal `DONE` before the required gate can pass.
- Documentation-only PRs whose changed paths are all below `docs/` are exempt from the task-ledger requirement.

## File Map

### Create

- `devsystem/forward_motion_policy_v2.json` — immutable machine-readable V2 policy.
- `devsystem/action_ledger_v2.py` — canonical hashing, receipts, append-only action chain, bootstrap evaluation, and PR ledger verifier.
- `devsystem/checkpoint_ledger_v2.py` — monotonic checkpoint validation and action-event-authorized transitions.
- `devsystem/forward_motion_v2.py` — stable fingerprints and authorization/denial decisions.
- `devsystem/anti_loop_replay_v2.py` — deterministic adversarial replay.
- `devsystem/forward_motion_contract_v2.py` — dependency-light permanent V2 validator.
- `devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json` — one-time activation record for this migration only.
- `tests/test_devsystem_action_ledger_v2.py`
- `tests/test_devsystem_checkpoint_ledger_v2.py`
- `tests/test_devsystem_forward_motion_v2.py`
- `tests/test_devsystem_anti_loop_replay_v2.py`

### Modify

- `devsystem/permanent_gate_v1.py`
- `tests/test_devsystem_permanent_gate_v1.py`
- `.github/workflows/devsystem-targeted-ci.yml`
- `devsystem/README.md`

---

## Task 1: Policy V2 — lock budgets, decisions, progress classes, override rules, and bootstrap rules

**Files:**
- Create: `devsystem/forward_motion_policy_v2.json`
- Create: `tests/test_devsystem_forward_motion_v2.py`

**Interfaces:**
- Policy version: integer `2`.
- Mode: `strict_auto_continue_v2`.
- Later `load_policy()` rejects any other version/mode.

- [ ] **Step 1: Write the RED policy tests**

Create `tests/test_devsystem_forward_motion_v2.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "devsystem" / "forward_motion_policy_v2.json"


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_v2_policy_exact_retry_and_stagnation_budgets():
    payload = _policy()
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


def test_v2_override_contract_is_exact_single_use_user_explicit():
    assert _policy()["override_rules"] == {
        "allowed_source": "user_explicit",
        "single_use": True,
        "exact_action_only": True,
        "cannot_disable_policy": True,
        "cryptographic_human_identity_claim": False,
    }


def test_v2_bootstrap_contract_self_expires():
    assert _policy()["bootstrap_rules"] == {
        "allowed_only_when_base_lacks_v2_policy": True,
        "single_activation": True,
    }
```

- [ ] **Step 2: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: failure because `forward_motion_policy_v2.json` does not exist.

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

- [ ] **Step 4: Prove GREEN**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add devsystem/forward_motion_policy_v2.json tests/test_devsystem_forward_motion_v2.py
git commit -m "feat: lock Monster Anti-Loop V2 policy"
```

---

## Task 2: Action ledger V2 — single-use receipts, tamper-evident chain, and self-expiring bootstrap

**Files:**
- Create: `devsystem/action_ledger_v2.py`
- Create: `tests/test_devsystem_action_ledger_v2.py`

**Interfaces:**

```python
canonical_json(payload: dict[str, object]) -> str
sha256_hex(value: str) -> str
build_receipt(payload: dict[str, object]) -> dict[str, object]
validate_receipt(receipt: dict[str, object]) -> dict[str, object]
record_authorized_action(task_ledger: dict, receipt: dict, *, outcome: str, progress_class: str, evidence: dict) -> dict
validate_action_ledger(task_ledger: dict) -> dict
validate_bootstrap_ledger(ledger: dict, *, base_has_v2_policy: bool, changed_files: list[str]) -> dict
verify_pr_ledger(base: str, head: str, *, root: Path = ROOT) -> dict
```

- [ ] **Step 1: Write RED receipt and hash-chain tests**

Create the test module with concrete helpers:

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


def ledger() -> dict:
    return {
        "version": 2,
        "task_id": "ledger-contract-test",
        "status": "ACTIVE",
        "action_log": {
            "head_chain_hash": GENESIS_CHAIN_HASH,
            "events": [],
            "consumed_receipts": [],
        },
        "transition_history": [],
        "override_events": [],
    }


def receipt_payload() -> dict:
    return {
        "policy_version": 2,
        "task_id": "ledger-contract-test",
        "checkpoint_id": "2",
        "action_fingerprint": "1" * 64,
        "root_cause_fingerprint": "2" * 64,
        "evidence_fingerprint": "3" * 64,
        "relevant_input_fingerprint": "4" * 64,
        "decision": "AUTHORIZED",
        "previous_chain_hash": GENESIS_CHAIN_HASH,
        "event_nonce": "event-0001",
        "override_event_id": None,
    }


def test_receipt_hash_detects_tampering():
    receipt = build_receipt(receipt_payload())
    assert validate_receipt(receipt)["status"] == "GREEN"
    tampered = deepcopy(receipt)
    tampered["payload"]["checkpoint_id"] = "99"
    with pytest.raises(ActionLedgerFailure, match="receipt hash mismatch"):
        validate_receipt(tampered)


def test_receipt_is_consumed_once():
    receipt = build_receipt(receipt_payload())
    first = record_authorized_action(
        ledger(), receipt, outcome="success", progress_class="new_evidence",
        evidence={"proof": "green"},
    )
    assert len(first["action_log"]["events"]) == 1
    with pytest.raises(ActionLedgerFailure, match="receipt already consumed"):
        record_authorized_action(
            first, receipt, outcome="success", progress_class="new_evidence",
            evidence={"proof": "green"},
        )


def test_editing_recorded_event_breaks_chain():
    receipt = build_receipt(receipt_payload())
    recorded = record_authorized_action(
        ledger(), receipt, outcome="success", progress_class="new_evidence",
        evidence={"proof": "green"},
    )
    recorded["action_log"]["events"][0]["evidence"] = {"proof": "edited"}
    with pytest.raises(ActionLedgerFailure, match="event chain hash mismatch"):
        validate_action_ledger(recorded)
```

- [ ] **Step 2: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_action_ledger_v2.py
```

Expected: import failure because `action_ledger_v2.py` does not exist.

- [ ] **Step 3: Implement receipt primitives and append-only validation**

Start `devsystem/action_ledger_v2.py` with:

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
    required = {
        "policy_version", "task_id", "checkpoint_id", "action_fingerprint",
        "root_cause_fingerprint", "evidence_fingerprint",
        "relevant_input_fingerprint", "decision", "previous_chain_hash",
        "event_nonce", "override_event_id",
    }
    missing = sorted(required.difference(body))
    if missing:
        raise ActionLedgerFailure("receipt missing fields: " + ", ".join(missing))
    return {"payload": body, "receipt_hash": sha256_hex(canonical_json(body))}


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

Implement `record_authorized_action()` in this exact sequence:

```python
def record_authorized_action(
    task_ledger: dict[str, Any],
    receipt: dict[str, Any],
    *,
    outcome: str,
    progress_class: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(task_ledger)
    validated = validate_receipt(receipt)
    receipt_hash = validated["receipt_hash"]
    payload = receipt["payload"]
    log = updated["action_log"]
    if payload["task_id"] != updated["task_id"]:
        raise ActionLedgerFailure("receipt task mismatch")
    if payload["previous_chain_hash"] != log["head_chain_hash"]:
        raise ActionLedgerFailure("receipt chain head mismatch")
    if receipt_hash in log["consumed_receipts"]:
        raise ActionLedgerFailure("receipt already consumed")
    if progress_class not in PROGRESS_CLASSES:
        raise ActionLedgerFailure("invalid progress class")
    event_id = "ACT-" + sha256_hex(receipt_hash + canonical_json(evidence))[:16].upper()
    event = {
        "event_id": event_id,
        "receipt": deepcopy(receipt),
        "outcome": str(outcome),
        "progress_class": progress_class,
        "evidence": deepcopy(evidence),
        "previous_chain_hash": log["head_chain_hash"],
    }
    event["event_chain_hash"] = sha256_hex(
        event["previous_chain_hash"] + canonical_json(event)
    )
    log["events"].append(event)
    log["consumed_receipts"].append(receipt_hash)
    log["head_chain_hash"] = event["event_chain_hash"]
    return updated
```

`validate_action_ledger()` must replay the event list from `GENESIS_CHAIN_HASH`, temporarily remove each event's `event_chain_hash`, recompute it, validate every embedded receipt, require unique receipt hashes and event IDs, require the final computed hash to equal `action_log.head_chain_hash`, and require `consumed_receipts` to equal the receipt hashes in event order.

- [ ] **Step 4: Prove receipt/chain GREEN**

```bash
python -m pytest -q tests/test_devsystem_action_ledger_v2.py
```

Expected: receipt and chain tests PASS.

- [ ] **Step 5: Add RED pure bootstrap tests**

Append:

```python
from devsystem.action_ledger_v2 import validate_bootstrap_ledger


def bootstrap_ledger() -> dict:
    return {
        "version": 2,
        "task_id": "monster-anti-loop-v2-activation",
        "activation_mode": "v2-bootstrap",
        "status": "DONE",
        "bootstrap_scope": [
            "devsystem/forward_motion_policy_v2.json",
            "devsystem/action_ledger_v2.py",
        ],
        "action_log": {
            "head_chain_hash": "BOOTSTRAP-V2-ACTIVATION",
            "events": [],
            "consumed_receipts": [],
        },
    }


def test_bootstrap_allowed_only_before_v2_exists():
    result = validate_bootstrap_ledger(
        bootstrap_ledger(),
        base_has_v2_policy=False,
        changed_files=[
            "devsystem/forward_motion_policy_v2.json",
            "devsystem/action_ledger_v2.py",
            "devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json",
        ],
    )
    assert result["status"] == "GREEN"


def test_bootstrap_rejected_after_v2_exists():
    with pytest.raises(ActionLedgerFailure, match="bootstrap is invalid after V2 activation"):
        validate_bootstrap_ledger(
            bootstrap_ledger(),
            base_has_v2_policy=True,
            changed_files=["devsystem/action_ledger_v2.py"],
        )
```

- [ ] **Step 6: Implement bootstrap validation and PR verifier**

Use this exact allowed-prefix policy for the one-time activation:

```python
BOOTSTRAP_ALLOWED_PREFIXES = (
    ".github/workflows/devsystem-targeted-ci.yml",
    "devsystem/",
    "tests/test_devsystem_",
    "docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md",
    "docs/superpowers/plans/2026-09-15-monster-anti-loop-v2-hard-gate-implementation.md",
)
```

`validate_bootstrap_ledger()` must reject when `base_has_v2_policy` is true, require `activation_mode == "v2-bootstrap"`, status `DONE`, exact sentinel `BOOTSTRAP-V2-ACTIVATION`, empty events/consumed receipts, and reject any changed path not covered by `bootstrap_scope` or `BOOTSTRAP_ALLOWED_PREFIXES`.

Implement git helpers:

```python
def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        raise ActionLedgerFailure(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _base_has_v2_policy(base: str, root: Path) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{base}:devsystem/forward_motion_policy_v2.json"],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return completed.returncode == 0
```

`verify_pr_ledger()` algorithm:

1. `changed_files = _git(root, "diff", "--name-only", base, head).splitlines()`.
2. If every changed file starts with `docs/`, return GREEN/docs-only.
3. Find changed files whose path starts `devsystem/task_ledgers/` and ends `.json`; require exactly one.
4. Load that ledger from the head revision with `git show <head>:<path>` rather than the working tree.
5. If the base lacks V2 policy, call `validate_bootstrap_ledger()` and return its result.
6. If the base has V2 policy, reject any ledger with `activation_mode == "v2-bootstrap"`.
7. For normal mode, require status `DONE`, run `validate_action_ledger()`, lazily import and run `validate_checkpoint_ledger()`, require at least one action event and at least one transition-history event.
8. Return GREEN plus ledger path/event count.

Add CLI parsing so this exact command works:

```bash
python devsystem/action_ledger_v2.py verify-pr --base "$BASE_SHA" --head "$HEAD_SHA"
```

- [ ] **Step 7: Add temp-git integration tests and prove GREEN**

Add one helper that initializes a temporary git repo using `subprocess.run(["git", "init"], ...)`, configures a test identity, commits a base, commits a head, and returns both SHAs. Test:

- normal code change with no task ledger => failure containing `exactly one changed task ledger required`;
- docs-only diff => GREEN/docs-only;
- bootstrap base without V2 => GREEN;
- same bootstrap with V2 in base => failure containing `bootstrap is invalid after V2 activation`.

Run:

```bash
python -m pytest -q tests/test_devsystem_action_ledger_v2.py
```

Expected: all Task 2 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add devsystem/action_ledger_v2.py tests/test_devsystem_action_ledger_v2.py
git commit -m "feat: add V2 authorization receipt ledger"
```

---

## Task 3: Checkpoint ledger V2 — monotonic transitions authorized by action-event IDs

**Files:**
- Create: `devsystem/checkpoint_ledger_v2.py`
- Create: `tests/test_devsystem_checkpoint_ledger_v2.py`

**Interfaces:**

```python
validate_checkpoint_ledger(task_ledger: dict) -> dict
transition_checkpoint(task_ledger: dict, checkpoint_id: str, new_state: str, *, authorized_event_id: str, evidence: dict | None = None, contradictory_evidence: dict | None = None) -> dict
```

- [ ] **Step 1: Write RED tests with complete fixtures**

Create:

```python
from __future__ import annotations

import pytest

from devsystem.checkpoint_ledger_v2 import (
    CheckpointLedgerV2Failure,
    transition_checkpoint,
    validate_checkpoint_ledger,
)


def base_ledger() -> dict:
    return {
        "version": 2,
        "task_id": "checkpoint-test",
        "status": "ACTIVE",
        "current_checkpoint": "2",
        "total_checkpoints": 2,
        "completed_checkpoints": 1,
        "remaining_checkpoints": 1,
        "active_blocker": None,
        "action_log": {
            "events": [{
                "event_id": "ACT-CLOSE-2",
                "receipt": {"payload": {"task_id": "checkpoint-test", "checkpoint_id": "2"}},
                "outcome": "success",
                "progress_class": "checkpoint_closed",
            }],
        },
        "transition_history": [],
        "checkpoints": [
            {"id": "1", "state": "DONE", "evidence": {"proof": "one"}},
            {"id": "2", "state": "ACTIVE", "evidence": {}},
        ],
    }


def test_missing_action_event_cannot_transition_checkpoint():
    with pytest.raises(CheckpointLedgerV2Failure, match="authorized action event"):
        transition_checkpoint(
            base_ledger(), "2", "DONE", authorized_event_id="ACT-MISSING",
            evidence={"contract": "green"},
        )


def test_final_checkpoint_closure_is_terminal():
    updated = transition_checkpoint(
        base_ledger(), "2", "DONE", authorized_event_id="ACT-CLOSE-2",
        evidence={"contract": "green"},
    )
    assert updated["status"] == "DONE"
    assert updated["current_checkpoint"] is None
    assert updated["completed_checkpoints"] == 2
    assert updated["remaining_checkpoints"] == 0


def test_same_action_event_cannot_transition_twice():
    updated = transition_checkpoint(
        base_ledger(), "2", "DONE", authorized_event_id="ACT-CLOSE-2",
        evidence={"contract": "green"},
    )
    with pytest.raises(CheckpointLedgerV2Failure, match="already used for a checkpoint transition"):
        transition_checkpoint(
            updated, "2", "DONE", authorized_event_id="ACT-CLOSE-2",
            evidence={"contract": "green"},
        )
```

Add a second fixture whose checkpoint 1 is DONE and whose action event targets checkpoint 1. Assert DONE->ACTIVE fails without `contradictory_evidence`, and succeeds only when contradictory evidence is non-empty and the action event targets checkpoint 1.

- [ ] **Step 2: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_checkpoint_ledger_v2.py
```

Expected: import failure.

- [ ] **Step 3: Implement validation**

Create `devsystem/checkpoint_ledger_v2.py` with:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

CHECKPOINT_STATES = {"PENDING", "ACTIVE", "DONE", "BLOCKED", "DEFERRED"}
TASK_STATES = {"ACTIVE", "DONE", "BLOCKED", "FAILED"}


class CheckpointLedgerV2Failure(RuntimeError):
    pass
```

`validate_checkpoint_ledger()` must enforce unique non-empty checkpoint IDs, exact counts, exactly one ACTIVE checkpoint for ACTIVE tasks, correct `current_checkpoint`, at most one active blocker, terminal invariants, and uniqueness/existence of `transition_history[*].authorized_event_id`.

- [ ] **Step 4: Implement transitions**

`transition_checkpoint()` must:

1. deep-copy input;
2. find the target checkpoint;
3. find the action event by `event_id`;
4. reject if that event ID appears in transition history;
5. require action event receipt payload task ID and checkpoint ID to match target;
6. for DONE->non-DONE require non-empty `contradictory_evidence`;
7. for new state DONE require non-empty closing evidence;
8. when closing an ACTIVE checkpoint, activate only the next PENDING checkpoint in list order;
9. when the last checkpoint closes, set status DONE/current null/blocker null;
10. append a transition record containing event ID, from-state, to-state, closing evidence, and contradictory evidence;
11. recount totals and call `validate_checkpoint_ledger()` before return.

- [ ] **Step 5: Prove GREEN and commit**

```bash
python -m pytest -q tests/test_devsystem_checkpoint_ledger_v2.py
git add devsystem/checkpoint_ledger_v2.py tests/test_devsystem_checkpoint_ledger_v2.py
git commit -m "feat: enforce monotonic V2 checkpoints"
```

---

## Task 4: Forward-motion V2 — semantic root-cause fingerprints and retry decisions

**Files:**
- Create: `devsystem/forward_motion_v2.py`
- Modify: `tests/test_devsystem_forward_motion_v2.py`

**Interfaces:**

```python
load_policy() -> dict
fingerprint_action(action: dict) -> str
fingerprint_root_cause(action: dict) -> str
fingerprint_evidence(action: dict) -> str
fingerprint_relevant_inputs(action: dict) -> str
denial_fingerprint(decision: str, action_fingerprint: str, checkpoint_id: str) -> str
decide(task_ledger: dict, action: dict, history: list[dict], policy: dict | None = None, override_event: dict | None = None) -> dict
```

- [ ] **Step 1: Add complete test helpers**

Append to `tests/test_devsystem_forward_motion_v2.py`:

```python
from devsystem.action_ledger_v2 import GENESIS_CHAIN_HASH
from devsystem.forward_motion_v2 import (
    decide,
    denial_fingerprint,
    fingerprint_root_cause,
)


def active_ledger() -> dict:
    return {
        "version": 2,
        "task_id": "forward-motion-test",
        "status": "ACTIVE",
        "current_checkpoint": "2",
        "active_blocker": None,
        "resolved_root_causes": [],
        "action_log": {"head_chain_hash": GENESIS_CHAIN_HASH, "events": [], "consumed_receipts": []},
        "checkpoints": [
            {"id": "1", "state": "DONE", "evidence": {"proof": "green"}},
            {"id": "2", "state": "ACTIVE", "evidence": {}},
        ],
    }


def action(**overrides) -> dict:
    payload = {
        "task_id": "forward-motion-test",
        "checkpoint_id": "2",
        "action_type": "production_proof",
        "target": "render:/health",
        "scope_relation": "in_scope",
        "retry": False,
        "failure_class": None,
        "new_hypothesis": False,
        "inspected_evidence": False,
        "contradictory_evidence": False,
        "failure": {
            "job": "browser-qa",
            "layer": "ui-browser",
            "evidence_signal": "browser-selector-race",
            "error_family": "TimeoutError",
            "message": "locator combobox timed out",
        },
        "command_args": ["--foo", "--bar"],
        "evidence_inputs": {"log_excerpt": "locator combobox timed out"},
        "relevant_inputs": {"commit": "abc123", "deployment": "dep-1"},
    }
    payload.update(overrides)
    return payload


def history_event(*, root: str, evidence: str, inputs: str, decision: str = "AUTHORIZED", progress: str = "no_progress") -> dict:
    return {
        "event_id": "ACT-HISTORY-" + str(abs(hash((root, evidence, inputs, decision, progress)))),
        "receipt": {"payload": {
            "root_cause_fingerprint": root,
            "evidence_fingerprint": evidence,
            "relevant_input_fingerprint": inputs,
            "decision": decision,
        }},
        "outcome": "failure",
        "progress_class": progress,
    }
```

- [ ] **Step 2: Add RED semantic-fingerprint and retry tests**

```python
def test_root_cause_ignores_run_metadata_and_command_order():
    first = action(
        run_id="100",
        timestamp="2026-09-15T10:00:00Z",
        command_args=["--foo", "--bar"],
    )
    second = action(
        run_id="999",
        timestamp="2026-09-15T11:00:00Z",
        command_args=["--bar", "--foo"],
    )
    assert fingerprint_root_cause(first) == fingerprint_root_cause(second)


def test_deterministic_unchanged_retry_is_denied_without_receipt():
    first = decide(active_ledger(), action(), [])
    event = {
        "event_id": "ACT-ONE",
        "receipt": first["receipt"],
        "outcome": "failure",
        "progress_class": "no_progress",
    }
    retried = action(retry=True, failure_class="deterministic-regression")
    result = decide(active_ledger(), retried, [event])
    assert result["decision"] == "DENIED_STALE_FAILURE"
    assert "receipt" not in result


def test_done_task_is_terminal():
    done = active_ledger()
    done["status"] = "DONE"
    done["current_checkpoint"] = None
    done["checkpoints"][1]["state"] = "DONE"
    result = decide(done, action(), [])
    assert result["decision"] == "TASK_COMPLETE"
    assert "receipt" not in result
```

Also add concrete tests for first inspected transient retry authorized / second denied, unknown failure one evidence action / second broad evidence action denied, unrelated side quest deferred, and second blocker deferred.

- [ ] **Step 3: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: V2 engine import/function failures.

- [ ] **Step 4: Implement stable fingerprints**

Create `devsystem/forward_motion_v2.py`. The root-cause fingerprint must use only semantic failure fields, so command ordering and run metadata cannot disguise recurrence:

```python
_VOLATILE_ACTION_KEYS = {
    "run_id", "workflow_run_id", "timestamp", "created_at", "updated_at",
    "retry_counter", "display_branch", "command_args",
}


def _normalize_text(value: str) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"\b[0-9a-f]{7,64}\b", "<hex>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}t\S+z\b", "<timestamp>", text)
    text = re.sub(r"\brun\s+\d+\b", "run <n>", text)
    text = re.sub(r"line\s+\d+", "line <n>", text)
    return re.sub(r"\s+", " ", text).strip()[:500]


def fingerprint_root_cause(action: dict[str, Any]) -> str:
    failure = action.get("failure") or {}
    semantic = {
        "job": str(failure.get("job") or "unknown"),
        "layer": str(failure.get("layer") or "unknown"),
        "evidence_signal": str(failure.get("evidence_signal") or "none"),
        "error_family": str(failure.get("error_family") or "unknown"),
        "message": _normalize_text(str(failure.get("message") or "")),
        "target": str(action.get("target") or ""),
    }
    return sha256_hex(canonical_json(semantic))
```

`fingerprint_evidence()` hashes `evidence_inputs`; `fingerprint_relevant_inputs()` hashes `relevant_inputs`; `fingerprint_action()` hashes task/checkpoint/action type/target plus stable action fields after removing `_VOLATILE_ACTION_KEYS`.

- [ ] **Step 5: Implement base decision order**

`decide()` must compute fingerprints once and evaluate in this exact order:

1. task ID and checkpoint ID validation;
2. terminal task => `TASK_COMPLETE`;
3. unrelated scope => `DEFER_SIDE_QUEST`;
4. second blocker => `DEFER_SIDE_QUEST`;
5. closed/backward checkpoint without contradiction => `DENIED_BACKTRACK` or `DENIED_CLOSED_CHECKPOINT`;
6. deterministic unchanged retry => `DENIED_STALE_FAILURE`;
7. transient retry => first inspected controlled retry allowed, second matching controlled retry denied;
8. unknown evidence gathering => one matching evidence action allowed, second unchanged one denied;
9. same root cause + same evidence fingerprint + same relevant-input fingerprint => `DENIED_STALE_FAILURE`;
10. exact action fingerprint already represented in history => `DENIED_LOOP`;
11. genuinely new hypothesis => `AUTHORIZED_NEW_HYPOTHESIS`;
12. otherwise => `AUTHORIZED`.

Positive decisions call `build_receipt()` with the current `action_log.head_chain_hash`; denied decisions never include a receipt.

- [ ] **Step 6: Prove GREEN and commit**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
git add devsystem/forward_motion_v2.py tests/test_devsystem_forward_motion_v2.py
git commit -m "feat: add semantic V2 forward-motion controller"
```

---

## Task 5: Stagnation, resolved root causes, and exact user-only override consumption

**Files:**
- Modify: `devsystem/forward_motion_v2.py`
- Modify: `tests/test_devsystem_forward_motion_v2.py`

- [ ] **Step 1: Add RED stagnation and resolved-root tests**

Use real fingerprints from `action()` rather than symbolic helper strings:

```python
def test_three_no_progress_events_lock_same_path():
    probe = action()
    initial = decide(active_ledger(), probe, [])
    payload = initial["receipt"]["payload"]
    history = [
        history_event(
            root=payload["root_cause_fingerprint"],
            evidence=payload["evidence_fingerprint"],
            inputs=payload["relevant_input_fingerprint"],
        )
        for _ in range(3)
    ]
    result = decide(active_ledger(), probe, history)
    assert result["decision"] == "DENIED_STAGNATION"


def test_changed_relevant_input_breaks_stagnant_path():
    probe = action()
    initial = decide(active_ledger(), probe, [])
    payload = initial["receipt"]["payload"]
    history = [
        history_event(
            root=payload["root_cause_fingerprint"],
            evidence=payload["evidence_fingerprint"],
            inputs=payload["relevant_input_fingerprint"],
        )
        for _ in range(3)
    ]
    changed = action(relevant_inputs={"commit": "def456", "deployment": "dep-2"})
    assert decide(active_ledger(), changed, history)["decision"] == "AUTHORIZED"
```

For resolved root causes, put this exact record on the ledger:

```python
{
    "root_cause_fingerprint": payload["root_cause_fingerprint"],
    "closing_evidence_fingerprint": payload["evidence_fingerprint"],
    "closed_by_event_id": "ACT-CLOSED-ROOT"
}
```

Assert the same root/evidence/input is denied, while `contradictory_evidence=True` plus new `evidence_inputs` permits `AUTHORIZED_NEW_HYPOTHESIS`.

- [ ] **Step 2: Add RED override tests using denial fingerprints**

Use this exact flow:

```python
def test_valid_override_is_exact_and_single_use():
    probe = action(retry=True, failure_class="deterministic-regression")
    first = decide(active_ledger(), action(), [])
    prior = [{
        "event_id": "ACT-FAILED",
        "receipt": first["receipt"],
        "outcome": "failure",
        "progress_class": "no_progress",
    }]
    denied = decide(active_ledger(), probe, prior)
    blocked_fp = denied["action_fingerprint"]
    denial_fp = denied["denial_fingerprint"]
    override = {
        "event_id": "OVR-USER-0001",
        "source": "user_explicit",
        "task_id": "forward-motion-test",
        "checkpoint_id": "2",
        "blocked_action_fingerprint": blocked_fp,
        "denial_fingerprint": denial_fp,
        "reason": "User explicitly authorizes this exact blocked action once.",
        "consumed": False,
    }
    allowed = decide(active_ledger(), probe, prior, override_event=override)
    assert allowed["decision"] == "AUTHORIZED_USER_OVERRIDE"
    assert allowed["receipt"]["payload"]["override_event_id"] == "OVR-USER-0001"

    consumed = dict(override)
    consumed["consumed"] = True
    reused = decide(active_ledger(), probe, prior, override_event=consumed)
    assert reused["decision"] == "DENIED_UNAUTHORIZED_OVERRIDE"
```

Add separate tests changing source, task ID, checkpoint ID, blocked action fingerprint, and denial fingerprint; each must return `DENIED_UNAUTHORIZED_OVERRIDE` without a receipt.

- [ ] **Step 3: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
```

Expected: new stagnation/root/override tests fail.

- [ ] **Step 4: Implement stagnation and override evaluation**

Before final authorization, inspect the last same-root events. If three consecutive events have `progress_class == "no_progress"` and unchanged evidence/input fingerprints, return `DENIED_STAGNATION`.

For a resolved root cause, deny unless both `contradictory_evidence is True` and evidence fingerprint differs from `closing_evidence_fingerprint`.

For any normal denial, include:

```python
{
    "action_fingerprint": action_fp,
    "denial_fingerprint": denial_fingerprint(decision, action_fp, checkpoint_id)
}
```

If an `override_event` is supplied, validate it only after the ordinary denial is known. It must match that exact denial, have source `user_explicit`, `consumed is False`, the same task/checkpoint/action fingerprint, and a non-empty reason. If valid, issue exactly `AUTHORIZED_USER_OVERRIDE`; do not mutate policy budgets and do not create an override event inside the controller.

- [ ] **Step 5: Prove GREEN and commit**

```bash
python -m pytest -q tests/test_devsystem_forward_motion_v2.py
git add devsystem/forward_motion_v2.py tests/test_devsystem_forward_motion_v2.py
git commit -m "feat: harden V2 stagnation and override controls"
```

---

## Task 6: V2 adversarial replay — reproduce historical loops and bypass attempts deterministically

**Files:**
- Create: `devsystem/anti_loop_replay_v2.py`
- Create: `tests/test_devsystem_anti_loop_replay_v2.py`

- [ ] **Step 1: Write RED replay contract test**

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

- [ ] **Step 2: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_anti_loop_replay_v2.py
```

Expected: import failure.

- [ ] **Step 3: Implement replay scaffolding using real V2 components**

Start the replay with these helpers:

```python
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from devsystem.action_ledger_v2 import ActionLedgerFailure, record_authorized_action, validate_action_ledger
from devsystem.checkpoint_ledger_v2 import CheckpointLedgerV2Failure, transition_checkpoint, validate_checkpoint_ledger
from devsystem.forward_motion_v2 import decide

SCENARIO = "MONSTER_ANTI_LOOP_V2_ADVERSARIAL_REPLAY"


def require_decision(result: dict[str, Any], expected: str, label: str) -> None:
    if result.get("decision") != expected:
        raise AssertionError(f"{label}: expected {expected}, got {result}")


def record_allowed(ledger: dict, action: dict, history: list[dict], *, outcome: str, progress: str, evidence: dict) -> tuple[dict, dict]:
    decision = decide(ledger, action, history)
    if not str(decision.get("decision", "")).startswith("AUTHORIZED"):
        raise AssertionError(f"expected authorization, got {decision}")
    updated = record_authorized_action(
        ledger, decision["receipt"], outcome=outcome, progress_class=progress, evidence=evidence,
    )
    event = updated["action_log"]["events"][-1]
    history.append(deepcopy(event))
    return updated, event
```

Build one task ledger with five checkpoints mirroring the historical A9 pattern. Use the real controller and real ledgers for all allowed paths.

- [ ] **Step 4: Add the exact adversarial sequence**

The sequence is fixed:

1. authorize and record an initial failing production proof;
2. repeat exact proof => `DENIED_LOOP` or `DENIED_STALE_FAILURE`;
3. change only run ID => same semantic root, denied;
4. reverse command args only => same semantic root, denied;
5. deterministic retry without repair => denied;
6. transient failure with inspected evidence => first `AUTHORIZED_CONTROLLED_RETRY`; record it; second => denied;
7. unknown failure evidence-gathering action => first allowed; unchanged second => denied;
8. create three same-root `no_progress` recorded events on a fresh test path => next proposal `DENIED_STAGNATION`;
9. materially change relevant commit/deployment => new authorization allowed;
10. propose a genuinely new discriminating hypothesis => `AUTHORIZED_NEW_HYPOTHESIS`;
11. open one blocker; second blocker => `DEFER_SIDE_QUEST`;
12. unrelated finding => `DEFER_SIDE_QUEST`;
13. attempt DONE checkpoint reopen without contradictory evidence => denied by controller/checkpoint layer;
14. add new contradictory evidence and authorize controlled reopen;
15. record one allowed action, then reuse its receipt => `ActionLedgerFailure`;
16. edit an earlier recorded event, then validate => `ActionLedgerFailure`;
17. supply override with source `agent_self_declared` => `DENIED_UNAUTHORIZED_OVERRIDE`;
18. obtain exact denial, supply matching `user_explicit` override => `AUTHORIZED_USER_OVERRIDE`; record once; mark override consumed; reuse => denied;
19. close remaining checkpoints with authorized action events until task status is DONE;
20. propose one more proof => `TASK_COMPLETE`; compare checkpoint count before/after and require zero invented checkpoints.

Return a result dict with all counters asserted by the test and print `MONSTER_ANTI_LOOP_V2_REPLAY_GREEN` plus formatted JSON.

- [ ] **Step 5: Run both historical and V2 replay proofs**

```bash
python devsystem/a9_anti_loop_replay_v1.py
python devsystem/anti_loop_replay_v2.py
python -m pytest -q tests/test_devsystem_anti_loop_replay_v2.py
```

Expected: both GREEN markers and pytest PASS.

- [ ] **Step 6: Commit**

```bash
git add devsystem/anti_loop_replay_v2.py tests/test_devsystem_anti_loop_replay_v2.py
git commit -m "test: add V2 adversarial anti-loop replay"
```

---

## Task 7: Permanent V2 contract — dependency-light proof of every hard invariant

**Files:**
- Create: `devsystem/forward_motion_contract_v2.py`
- Modify: `tests/test_devsystem_permanent_gate_v1.py`

- [ ] **Step 1: Write RED permanent-contract assertion**

Append:

```python
def test_forward_motion_v2_contract_is_permanently_enforced():
    contract = _load("forward_motion_contract_v2", "devsystem/forward_motion_contract_v2.py")
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

- [ ] **Step 2: Prove RED**

```bash
python -m pytest -q tests/test_devsystem_permanent_gate_v1.py::test_forward_motion_v2_contract_is_permanently_enforced
```

Expected: V2 contract file missing.

- [ ] **Step 3: Implement validator skeleton and explicit invariant probes**

Create `devsystem/forward_motion_contract_v2.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devsystem.a9_anti_loop_replay_v1 import run_replay as run_v1_replay
from devsystem.action_ledger_v2 import (
    ActionLedgerFailure,
    build_receipt,
    record_authorized_action,
    validate_action_ledger,
    validate_bootstrap_ledger,
)
from devsystem.anti_loop_replay_v2 import run_replay as run_v2_replay
from devsystem.checkpoint_ledger_v2 import transition_checkpoint, validate_checkpoint_ledger
from devsystem.forward_motion_v2 import decide, load_policy


class ForwardMotionV2ContractFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardMotionV2ContractFailure(message)
```

Inside `validate()` perform explicit probes, not source-text-only checks:

- exact policy mode and 0/1/1 budgets;
- deterministic retry denied;
- transient first retry authorized, second denied;
- unknown evidence budget capped;
- same semantic root with changed run metadata denied;
- 3-action stagnation denied;
- changed relevant input authorized;
- DONE checkpoint reopen without contradiction rejected;
- single-use receipt replay rejected;
- edited event chain rejected;
- invalid override rejected, exact user override authorized once;
- pure bootstrap validation GREEN when `base_has_v2_policy=False` and rejected when true;
- V1 replay GREEN;
- V2 replay GREEN.

Return exactly:

```python
result = {
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
print("DEVSYSTEM_FORWARD_MOTION_V2_CONTRACT_GREEN")
print(json.dumps(result, indent=2, sort_keys=True))
return result
```

- [ ] **Step 4: Prove GREEN and commit**

```bash
python devsystem/forward_motion_contract_v2.py
python -m pytest -q tests/test_devsystem_permanent_gate_v1.py::test_forward_motion_v2_contract_is_permanently_enforced
git add devsystem/forward_motion_contract_v2.py tests/test_devsystem_permanent_gate_v1.py
git commit -m "feat: certify permanent Anti-Loop V2 contract"
```

---

## Task 8: Permanent CI enforcement — wire V2 into the existing gate and activate once

**Files:**
- Modify: `devsystem/permanent_gate_v1.py`
- Modify: `tests/test_devsystem_permanent_gate_v1.py`
- Modify: `.github/workflows/devsystem-targeted-ci.yml`
- Modify: `devsystem/README.md`
- Create: `devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json`

- [ ] **Step 1: Extend permanent file and workflow invariants**

Add these paths to `REQUIRED_DEVSYSTEM_FILES` in `devsystem/permanent_gate_v1.py`:

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

Add workflow markers:

```python
"python devsystem/forward_motion_contract_v2.py",
"python devsystem/action_ledger_v2.py verify-pr",
```

Add result flags:

```python
"forward_motion_v2_permanent": True,
"forward_motion_v2_pr_enforcement": True,
```

Update `tests/test_devsystem_permanent_gate_v1.py` to assert both flags.

- [ ] **Step 2: Prove RED before workflow wiring**

```bash
python -m pytest -q tests/test_devsystem_permanent_gate_v1.py
```

Expected: required workflow-marker assertions fail.

- [ ] **Step 3: Make the existing permanent-contract checkout full-depth**

Change only the checkout step inside `permanent-contract` from:

```yaml
      - uses: actions/checkout@v4
```

to:

```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
```

This is required because `verify-pr` compares the PR base SHA to the PR head SHA.

- [ ] **Step 4: Add the V2 hard-gate step inside `permanent-contract`**

Insert after `Validate permanent DevSystem contract` and before its pytest self-test:

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

No new workflow/job is created.

- [ ] **Step 5: Create the one-time activation ledger**

Create `devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json`:

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
    ".github/workflows/devsystem-targeted-ci.yml",
    "devsystem/README.md",
    "devsystem/action_ledger_v2.py",
    "devsystem/anti_loop_replay_v2.py",
    "devsystem/checkpoint_ledger_v2.py",
    "devsystem/forward_motion_contract_v2.py",
    "devsystem/forward_motion_policy_v2.json",
    "devsystem/forward_motion_v2.py",
    "devsystem/permanent_gate_v1.py",
    "devsystem/task_ledgers/monster-anti-loop-v2-bootstrap.json",
    "docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md",
    "docs/superpowers/plans/2026-09-15-monster-anti-loop-v2-hard-gate-implementation.md",
    "tests/test_devsystem_action_ledger_v2.py",
    "tests/test_devsystem_anti_loop_replay_v2.py",
    "tests/test_devsystem_checkpoint_ledger_v2.py",
    "tests/test_devsystem_forward_motion_v2.py",
    "tests/test_devsystem_permanent_gate_v1.py"
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
    {"id": "2", "state": "DONE", "evidence": {"receipt_chain": "GREEN"}},
    {"id": "3", "state": "DONE", "evidence": {"checkpoint_monotonicity": "GREEN"}},
    {"id": "4", "state": "DONE", "evidence": {"semantic_loop_controller": "GREEN"}},
    {"id": "5", "state": "DONE", "evidence": {"adversarial_replay": "GREEN"}},
    {"id": "6", "state": "DONE", "evidence": {"permanent_contract": "GREEN"}}
  ]
}
```

- [ ] **Step 6: Update README with exact operational rules**

Append a `Monster Anti-Loop V2 hard gate` section containing these points verbatim in substance:

```text
After V2 activation, V2 is the authoritative forward-motion contract and V1 remains the historical compatibility replay.
A non-documentation PR must change exactly one valid DONE task ledger under devsystem/task_ledgers/.
Every authoritative action in a normal V2 ledger requires one single-use authorization receipt and the append-only action chain must validate.
Checkpoint transitions reference authorized action-event IDs; they do not consume receipts again.
Same-root failures with unchanged evidence/relevant inputs are denied even when run IDs, timestamps, branch labels, or command ordering change.
Three same-path no-progress actions lock that path until relevant inputs/evidence change or a genuinely new hypothesis is tested.
User overrides are exact-action and single-use. Repository hashes provide integrity/auditability, not cryptographic proof of human authorship.
The v2-bootstrap activation mode is valid only when the PR base lacks forward_motion_policy_v2.json and is permanently invalid after activation.
The stable required aggregate check remains devsystem-final-gate.
```

- [ ] **Step 7: Prove permanent integration GREEN**

```bash
python devsystem/permanent_gate_v1.py
python devsystem/forward_motion_contract_v1.py
python devsystem/forward_motion_contract_v2.py
python devsystem/a9_anti_loop_replay_v1.py
python devsystem/anti_loop_replay_v2.py
python -m pytest -q \
  tests/test_devsystem_action_ledger_v2.py \
  tests/test_devsystem_checkpoint_ledger_v2.py \
  tests/test_devsystem_forward_motion_v2.py \
  tests/test_devsystem_anti_loop_replay_v2.py \
  tests/test_devsystem_permanent_gate_v1.py
```

Expected: zero failures and all four GREEN markers.

- [ ] **Step 8: Commit**

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

## Task 9: Final certification, protected merge, and permanent bootstrap-death proof

**Files:** Verification only unless a deterministic in-scope V2 defect is proven.

**Exit Condition:** The exact final PR head passes the permanent V2 contract, existing required DevSystem lanes, exact diff/freeze check, and `devsystem-final-gate`; protected `main` then points to the merge result and bootstrap is proven invalid against the new base.

- [ ] **Step 1: Run the complete dependency-light suite**

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

- [ ] **Step 2: Compile control-plane files**

```bash
python -m py_compile \
  devsystem/action_ledger_v2.py \
  devsystem/checkpoint_ledger_v2.py \
  devsystem/forward_motion_v2.py \
  devsystem/anti_loop_replay_v2.py \
  devsystem/forward_motion_contract_v2.py \
  devsystem/permanent_gate_v1.py
```

Expected: exit 0.

- [ ] **Step 3: Exact freeze-scope diff**

The final PR may contain only these paths:

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
docs/superpowers/specs/2026-09-15-monster-anti-loop-v2-design.md
docs/superpowers/plans/2026-09-15-monster-anti-loop-v2-hard-gate-implementation.md
tests/test_devsystem_action_ledger_v2.py
tests/test_devsystem_anti_loop_replay_v2.py
tests/test_devsystem_checkpoint_ledger_v2.py
tests/test_devsystem_forward_motion_v2.py
tests/test_devsystem_permanent_gate_v1.py
```

Any sports/runtime/model/page/provider path is a hard failure.

- [ ] **Step 4: Prove bootstrap expiration in tests before PR merge**

Run the specific bootstrap-after-activation test:

```bash
python -m pytest -q \
  tests/test_devsystem_action_ledger_v2.py::test_bootstrap_rejected_after_v2_exists
```

Expected: PASS because the helper correctly rejects that state.

- [ ] **Step 5: Open the PR with exact scope language**

PR body must explicitly state:

- V2 is DevSystem/control-plane only;
- no sports runtime/model/page/provider file changed;
- V1 remains intact;
- single-use receipts + action-event checkpoint transitions prevent authoritative receipt bypass;
- semantic root-cause and 3-action stagnation rules prevent superficial rerun loops;
- exact single-use user override is auditable but not falsely described as cryptographic human identity proof;
- bootstrap is one-time and self-expiring;
- `devsystem-final-gate` remains unchanged.

- [ ] **Step 6: Required CI evidence on the exact head**

Require:

```text
permanent-contract = success
regression-shield = success
all classifier-required domain/browser lanes = success or intentionally skipped
devsystem-final-gate = success
```

Deterministic failure: inspect once, change the relevant input/code before any rerun. Transient-capable failure: at most one inspected controlled retry. Unknown failure: one evidence action before a new discriminating hypothesis or stop.

- [ ] **Step 7: Re-verify exact final diff and head SHA after any repair**

The SHA whose required gates are GREEN must equal the PR head being merged. Recheck that no forbidden sports path entered the diff and that the branch is not behind protected `main`.

- [ ] **Step 8: Merge through the existing protected path**

Do not weaken branch protection, bypass the required aggregate gate, or rename `devsystem-final-gate`.

- [ ] **Step 9: Freshly verify protected main**

After merge, verify:

```text
main head = merge result
devsystem/forward_motion_policy_v2.json exists
devsystem/forward_motion_contract_v2.py exists
devsystem-final-gate remains the stable required check
frozen sports paths are absent from the merged diff
```

- [ ] **Step 10: Prove the real new base kills bootstrap**

Using the merged main SHA as `base`, create or use a test head that attempts `activation_mode = "v2-bootstrap"` and run:

```bash
python devsystem/action_ledger_v2.py verify-pr --base "$MERGED_MAIN_SHA" --head "$BOOTSTRAP_ATTEMPT_SHA"
```

Expected failure text:

```text
bootstrap is invalid after V2 activation
```

This is the final activation proof.

- [ ] **Step 11: Terminal report**

Only after all exit conditions above are verified:

```text
MONSTER_ANTI_LOOP_V2_TASK_COMPLETE
Steps remaining: 0
```

Do not create V2.1, cleanup checkpoints, extra certification loops, or V1-removal work. Any such work is a new user-scoped task.

---

## Self-Review — completed before execution handoff

- Spec coverage: Tasks 1–9 cover policy, receipts, action chain, checkpoints, semantic root causes, stagnation, overrides, replay, permanent contract, CI wiring, bootstrap migration, freeze scope, and terminal merge proof.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or undefined test-helper references remain.
- Type/interface consistency: receipt -> action event -> checkpoint transition is single-consumption throughout; all later tasks use the same function names defined earlier.
- Root-cause consistency: root fingerprint excludes command ordering/run metadata and uses only semantic failure identity plus target.
- CI consistency: `permanent-contract` explicitly uses full checkout depth before base/head diff verification.
- Migration consistency: V1 is authoritative during bootstrap; V2 becomes authoritative only after the protected merge; bootstrap then self-expires.
- Security wording: hashes are treated as tamper evidence/auditability, not cryptographic human identity proof.
