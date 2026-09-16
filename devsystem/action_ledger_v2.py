"""Tamper-evident action ledger and authorization receipts for Monster Anti-Loop V2."""
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
BOOTSTRAP_CHAIN_HASH = "BOOTSTRAP-V2-ACTIVATION"
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
REQUIRED_RECEIPT_FIELDS = {
    "policy_version",
    "task_id",
    "checkpoint_id",
    "action_fingerprint",
    "root_cause_fingerprint",
    "evidence_fingerprint",
    "relevant_input_fingerprint",
    "decision",
    "previous_chain_hash",
    "event_nonce",
    "override_event_id",
}


class ActionLedgerFailure(RuntimeError):
    pass


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    body = deepcopy(payload)
    missing = sorted(REQUIRED_RECEIPT_FIELDS - set(body))
    if missing:
        raise ActionLedgerFailure("receipt missing required fields: " + ", ".join(missing))
    if body.get("decision") not in AUTHORIZED_DECISIONS:
        raise ActionLedgerFailure("denied decision cannot issue authorization receipt")
    if int(body.get("policy_version", 0)) != 2:
        raise ActionLedgerFailure("receipt policy version must be 2")
    receipt_hash = sha256_hex(canonical_json(body))
    return {"payload": body, "receipt_hash": receipt_hash}


def validate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ActionLedgerFailure("receipt must be an object")
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        raise ActionLedgerFailure("receipt payload must be an object")
    missing = sorted(REQUIRED_RECEIPT_FIELDS - set(payload))
    if missing:
        raise ActionLedgerFailure("receipt missing required fields: " + ", ".join(missing))
    expected = sha256_hex(canonical_json(payload))
    if receipt.get("receipt_hash") != expected:
        raise ActionLedgerFailure("receipt hash mismatch")
    if payload.get("decision") not in AUTHORIZED_DECISIONS:
        raise ActionLedgerFailure("receipt decision is not authorized")
    if int(payload.get("policy_version", 0)) != 2:
        raise ActionLedgerFailure("receipt policy version must be 2")
    return {"status": "GREEN", "receipt_hash": expected}


def _action_log(task_ledger: dict[str, Any]) -> dict[str, Any]:
    log = task_ledger.get("action_log")
    if not isinstance(log, dict):
        raise ActionLedgerFailure("task ledger requires action_log")
    events = log.get("events")
    consumed = log.get("consumed_receipts")
    if not isinstance(events, list) or not isinstance(consumed, list):
        raise ActionLedgerFailure("action_log events and consumed_receipts must be lists")
    if not isinstance(log.get("head_chain_hash"), str):
        raise ActionLedgerFailure("action_log requires head_chain_hash")
    return log


def record_authorized_action(
    task_ledger: dict[str, Any],
    receipt: dict[str, Any],
    *,
    outcome: str,
    progress_class: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(task_ledger)
    log = _action_log(updated)
    validate_receipt(receipt)
    payload = receipt["payload"]
    receipt_hash = str(receipt["receipt_hash"])
    if str(payload.get("task_id")) != str(updated.get("task_id")):
        raise ActionLedgerFailure("receipt task mismatch")
    if receipt_hash in log["consumed_receipts"]:
        raise ActionLedgerFailure("receipt already consumed")
    if str(payload.get("previous_chain_hash")) != str(log.get("head_chain_hash")):
        raise ActionLedgerFailure("receipt previous chain does not match ledger head")
    if progress_class not in PROGRESS_CLASSES:
        raise ActionLedgerFailure("unrecognized progress class")
    if not str(outcome).strip():
        raise ActionLedgerFailure("outcome is required")
    if not isinstance(evidence, dict):
        raise ActionLedgerFailure("evidence must be an object")

    previous_chain_hash = str(log["head_chain_hash"])
    event_id = "ACT-" + sha256_hex(receipt_hash + canonical_json(evidence))[:16].upper()
    event: dict[str, Any] = {
        "event_id": event_id,
        "receipt": deepcopy(receipt),
        "outcome": str(outcome),
        "progress_class": progress_class,
        "evidence": deepcopy(evidence),
    }
    event_chain_hash = sha256_hex(previous_chain_hash + canonical_json(event))
    event["event_chain_hash"] = event_chain_hash
    log["events"].append(event)
    log["consumed_receipts"].append(receipt_hash)
    log["head_chain_hash"] = event_chain_hash
    return updated


def validate_action_ledger(task_ledger: dict[str, Any]) -> dict[str, Any]:
    log = _action_log(task_ledger)
    events = log["events"]
    consumed = log["consumed_receipts"]
    if len(consumed) != len(set(consumed)):
        raise ActionLedgerFailure("consumed receipt list contains duplicates")
    computed_head = GENESIS_CHAIN_HASH
    seen_receipts: list[str] = []
    seen_events: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            raise ActionLedgerFailure("action event must be an object")
        receipt = event.get("receipt")
        validate_receipt(receipt)
        payload = receipt["payload"]
        receipt_hash = str(receipt["receipt_hash"])
        if str(payload.get("task_id")) != str(task_ledger.get("task_id")):
            raise ActionLedgerFailure("receipt task mismatch")
        if str(payload.get("previous_chain_hash")) != computed_head:
            raise ActionLedgerFailure("receipt previous chain does not match replay head")
        if receipt_hash in seen_receipts:
            raise ActionLedgerFailure("receipt already consumed")
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in seen_events:
            raise ActionLedgerFailure("action event id must be non-empty and unique")
        if event.get("progress_class") not in PROGRESS_CLASSES:
            raise ActionLedgerFailure("unrecognized progress class")
        event_without_hash = {k: deepcopy(v) for k, v in event.items() if k != "event_chain_hash"}
        expected_chain = sha256_hex(computed_head + canonical_json(event_without_hash))
        if event.get("event_chain_hash") != expected_chain:
            raise ActionLedgerFailure("event chain hash mismatch")
        computed_head = expected_chain
        seen_receipts.append(receipt_hash)
        seen_events.add(event_id)
    if log.get("head_chain_hash") != computed_head:
        raise ActionLedgerFailure("action log head chain hash mismatch")
    if consumed != seen_receipts:
        raise ActionLedgerFailure("consumed receipt index does not match event history")
    return {
        "status": "GREEN",
        "event_count": len(events),
        "head_chain_hash": computed_head,
        "consumed_receipt_count": len(consumed),
    }


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
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


def _read_json_at(ref: str, path: str, root: Path) -> dict[str, Any]:
    text = _git(root, "show", f"{ref}:{path}")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ActionLedgerFailure(f"invalid JSON ledger {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ActionLedgerFailure(f"ledger must be an object: {path}")
    return value


def verify_pr_ledger(base: str, head: str, *, root: Path = ROOT) -> dict[str, Any]:
    changed = [line.strip() for line in _git(root, "diff", "--name-only", base, head).splitlines() if line.strip()]
    if not changed:
        return {"status": "GREEN", "mode": "no-changes", "changed_files": 0}
    if all(path.startswith("docs/") for path in changed):
        return {"status": "GREEN", "mode": "docs-only", "changed_files": len(changed)}

    ledger_paths = [
        path for path in changed
        if path.startswith("devsystem/task_ledgers/") and path.endswith(".json")
    ]
    if len(ledger_paths) != 1:
        raise ActionLedgerFailure("non-documentation PR requires exactly one changed task ledger")
    ledger_path = ledger_paths[0]
    ledger = _read_json_at(head, ledger_path, root)
    base_has_v2 = _base_has_v2_policy(base, root)

    if base_has_v2:
        if ledger.get("activation_mode") == "v2-bootstrap":
            raise ActionLedgerFailure("bootstrap is invalid after V2 activation")
        if ledger.get("status") != "DONE":
            raise ActionLedgerFailure("future task ledger must finish in DONE state")
        validate_action_ledger(ledger)
        return {"status": "GREEN", "mode": "v2-enforced", "ledger": ledger_path}

    if ledger.get("activation_mode") != "v2-bootstrap":
        raise ActionLedgerFailure("first V2 activation requires v2-bootstrap ledger")
    added_policy = "devsystem/forward_motion_policy_v2.json" in changed
    if not added_policy:
        raise ActionLedgerFailure("bootstrap requires V2 policy to be added in the same change")
    if ledger.get("status") != "DONE":
        raise ActionLedgerFailure("bootstrap ledger must be DONE")
    log = _action_log(ledger)
    if log.get("head_chain_hash") != BOOTSTRAP_CHAIN_HASH or log.get("events") or log.get("consumed_receipts"):
        raise ActionLedgerFailure("bootstrap action-log sentinel is invalid")
    scope = ledger.get("bootstrap_scope")
    if not isinstance(scope, list) or not scope:
        raise ActionLedgerFailure("bootstrap_scope must be a non-empty list")
    if set(changed) - set(map(str, scope)):
        raise ActionLedgerFailure("bootstrap scope does not cover every changed file")
    forbidden = [
        path for path in changed
        if path.startswith(("sports_api/", "cfb_", "mlb_", "wnba_", "nfl_"))
        and not path.startswith("devsystem/")
    ]
    if forbidden:
        raise ActionLedgerFailure("bootstrap may not change sports runtime files: " + ", ".join(forbidden))
    return {"status": "GREEN", "mode": "v2-bootstrap", "ledger": ledger_path}


def _main() -> int:
    parser = argparse.ArgumentParser(description="Monster Anti-Loop V2 action ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify-pr")
    verify.add_argument("--base", required=True)
    verify.add_argument("--head", required=True)
    args = parser.parse_args()
    if args.command == "verify-pr":
        result = verify_pr_ledger(args.base, args.head)
        print("MONSTER_ANTI_LOOP_V2_LEDGER_GREEN")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    raise ActionLedgerFailure("unsupported command")


if __name__ == "__main__":
    raise SystemExit(_main())
