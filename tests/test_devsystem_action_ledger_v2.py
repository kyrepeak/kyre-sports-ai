from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.action_ledger_v2 import (
    ActionLedgerFailure,
    GENESIS_CHAIN_HASH,
    build_receipt,
    record_authorized_action,
    validate_action_ledger,
    validate_receipt,
    verify_pr_ledger,
)


def _ledger(task_id: str = "anti-loop-v2-test") -> dict:
    return {
        "version": 2,
        "task_id": task_id,
        "status": "ACTIVE",
        "action_log": {
            "head_chain_hash": GENESIS_CHAIN_HASH,
            "events": [],
            "consumed_receipts": [],
        },
        "transition_history": [],
        "override_events": [],
    }


def _receipt_payload(**overrides) -> dict:
    payload = {
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
    payload.update(overrides)
    return payload


def test_receipt_hash_validates_and_tampering_fails_closed():
    receipt = build_receipt(_receipt_payload())
    assert validate_receipt(receipt)["status"] == "GREEN"
    tampered = deepcopy(receipt)
    tampered["payload"]["checkpoint_id"] = "99"
    with pytest.raises(ActionLedgerFailure, match="receipt hash mismatch"):
        validate_receipt(tampered)


def test_denied_decision_cannot_issue_receipt():
    with pytest.raises(ActionLedgerFailure, match="denied decision"):
        build_receipt(_receipt_payload(decision="DENIED_LOOP"))


def test_receipt_is_consumed_once_and_chain_advances():
    receipt = build_receipt(_receipt_payload())
    first = record_authorized_action(
        _ledger(), receipt, outcome="success", progress_class="new_evidence", evidence={"proof": "green"}
    )
    assert len(first["action_log"]["events"]) == 1
    assert first["action_log"]["head_chain_hash"] != GENESIS_CHAIN_HASH
    assert validate_action_ledger(first)["status"] == "GREEN"
    with pytest.raises(ActionLedgerFailure, match="receipt already consumed"):
        record_authorized_action(
            first, receipt, outcome="success", progress_class="new_evidence", evidence={"proof": "green"}
        )


def test_receipt_task_and_chain_must_match_ledger():
    with pytest.raises(ActionLedgerFailure, match="task mismatch"):
        record_authorized_action(
            _ledger("other-task"), build_receipt(_receipt_payload()), outcome="success",
            progress_class="new_evidence", evidence={}
        )
    bad_chain = build_receipt(_receipt_payload(previous_chain_hash="f" * 64))
    with pytest.raises(ActionLedgerFailure, match="previous chain"):
        record_authorized_action(
            _ledger(), bad_chain, outcome="success", progress_class="new_evidence", evidence={}
        )


def test_unknown_progress_class_is_rejected():
    with pytest.raises(ActionLedgerFailure, match="progress class"):
        record_authorized_action(
            _ledger(), build_receipt(_receipt_payload()), outcome="success",
            progress_class="magic", evidence={}
        )


def test_editing_earlier_event_breaks_hash_chain():
    first = record_authorized_action(
        _ledger(), build_receipt(_receipt_payload()), outcome="success",
        progress_class="new_evidence", evidence={"proof": 1}
    )
    tampered = deepcopy(first)
    tampered["action_log"]["events"][0]["evidence"] = {"proof": 2}
    with pytest.raises(ActionLedgerFailure, match="event chain hash mismatch"):
        validate_action_ledger(tampered)


def _git(root: Path, *args: str) -> str:
    cp = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return cp.stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "monster@example.com")
    _git(root, "config", "user.name", "Monster Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    return root, _git(root, "rev-parse", "HEAD")


def _write_normal_done_ledger(root: Path, task_id: str = "future-task") -> None:
    ledger = _ledger(task_id)
    ledger["status"] = "DONE"
    (root / "devsystem" / "task_ledgers").mkdir(parents=True, exist_ok=True)
    (root / "devsystem" / "task_ledgers" / f"{task_id}.json").write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8"
    )


def test_normal_code_pr_requires_exactly_one_valid_changed_task_ledger(tmp_path):
    root, base = _init_repo(tmp_path)
    (root / "devsystem").mkdir(exist_ok=True)
    (root / "devsystem" / "forward_motion_policy_v2.json").write_text("{}\n", encoding="utf-8")
    (root / "app.py").write_text("print('x')\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "code without ledger")
    head = _git(root, "rev-parse", "HEAD")
    with pytest.raises(ActionLedgerFailure, match="exactly one changed task ledger"):
        verify_pr_ledger(base, head, root=root)


def test_docs_only_pr_is_exempt(tmp_path):
    root, base = _init_repo(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("hello\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "docs")
    head = _git(root, "rev-parse", "HEAD")
    assert verify_pr_ledger(base, head, root=root)["mode"] == "docs-only"


def test_bootstrap_allowed_only_when_base_lacks_v2_policy(tmp_path):
    root, base = _init_repo(tmp_path)
    (root / "devsystem" / "task_ledgers").mkdir(parents=True)
    (root / "devsystem" / "forward_motion_policy_v2.json").write_text("{}\n", encoding="utf-8")
    ledger_path = root / "devsystem" / "task_ledgers" / "bootstrap.json"
    ledger_path.write_text(json.dumps({
        "version": 2,
        "task_id": "monster-anti-loop-v2-activation",
        "activation_mode": "v2-bootstrap",
        "status": "DONE",
        "bootstrap_scope": [
            "devsystem/forward_motion_policy_v2.json",
            "devsystem/task_ledgers/bootstrap.json",
        ],
        "action_log": {"head_chain_hash": "BOOTSTRAP-V2-ACTIVATION", "events": [], "consumed_receipts": []},
        "transition_history": [],
        "override_events": [],
    }, indent=2) + "\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "bootstrap")
    head = _git(root, "rev-parse", "HEAD")
    result = verify_pr_ledger(base, head, root=root)
    assert result["mode"] == "v2-bootstrap"


def test_bootstrap_rejected_after_v2_exists_on_base(tmp_path):
    root, _ = _init_repo(tmp_path)
    (root / "devsystem" / "task_ledgers").mkdir(parents=True)
    (root / "devsystem" / "forward_motion_policy_v2.json").write_text("{}\n", encoding="utf-8")
    _write_normal_done_ledger(root, "activation-base")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "activate v2")
    base = _git(root, "rev-parse", "HEAD")
    path = root / "devsystem" / "task_ledgers" / "future-bootstrap.json"
    path.write_text(json.dumps({
        "version": 2,
        "task_id": "future-bootstrap",
        "activation_mode": "v2-bootstrap",
        "status": "DONE",
        "bootstrap_scope": ["devsystem/task_ledgers/future-bootstrap.json"],
        "action_log": {"head_chain_hash": "BOOTSTRAP-V2-ACTIVATION", "events": [], "consumed_receipts": []},
        "transition_history": [],
        "override_events": [],
    }, indent=2) + "\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "try bootstrap again")
    head = _git(root, "rev-parse", "HEAD")
    with pytest.raises(ActionLedgerFailure, match="bootstrap is invalid after V2 activation"):
        verify_pr_ledger(base, head, root=root)


def test_bootstrap_rejects_unapproved_non_sports_file_even_if_declared_in_scope(tmp_path):
    root, base = _init_repo(tmp_path)
    (root / "devsystem" / "task_ledgers").mkdir(parents=True)
    (root / "devsystem" / "forward_motion_policy_v2.json").write_text("{}\n", encoding="utf-8")
    (root / "app.py").write_text("print('bootstrap escape')\n", encoding="utf-8")
    ledger_path = root / "devsystem" / "task_ledgers" / "bootstrap.json"
    ledger_path.write_text(json.dumps({
        "version": 2,
        "task_id": "monster-anti-loop-v2-activation",
        "activation_mode": "v2-bootstrap",
        "status": "DONE",
        "bootstrap_scope": [
            "devsystem/forward_motion_policy_v2.json",
            "devsystem/task_ledgers/bootstrap.json",
            "app.py",
        ],
        "action_log": {"head_chain_hash": "BOOTSTRAP-V2-ACTIVATION", "events": [], "consumed_receipts": []},
        "transition_history": [],
        "override_events": [],
    }, indent=2) + "\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "attempt unrelated bootstrap change")
    head = _git(root, "rev-parse", "HEAD")
    with pytest.raises(ActionLedgerFailure, match="unapproved paths|approved V2 control-plane paths"):
        verify_pr_ledger(base, head, root=root)
