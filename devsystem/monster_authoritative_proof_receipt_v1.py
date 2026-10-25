"""MONSTER-owned authoritative proof receipt V1.

GitHub Actions can contribute regression evidence, but this receipt is the
MONSTER control-plane authority that binds exact candidate identity, every
required gate, evidence digest, production applicability/identity, rollback
anchor, and freeze target.  Foreign-system evidence is rejected fail-closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

VERSION = "MONSTER_AUTHORITATIVE_PROOF_RECEIPT_V1"
PROOF_AUTHORITY = "MONSTER_ONLY"
GITHUB_ACTIONS_ROLE = "SUPPORTING_EVIDENCE_ONLY"
_REQUIRED_GATES = ("step2a", "anti_loop", "step2c", "step2b", "execution", "step2d", "step2e", "step2f", "final_verify")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_FOREIGN = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.IGNORECASE)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _walk(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, str):
        yield value


def _contains_foreign(value: Any) -> bool:
    return any(_FOREIGN.search(text) for text in _walk(value))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "version": VERSION,
        "proof_authority": PROOF_AUTHORITY,
        "github_actions_role": GITHUB_ACTIONS_ROLE,
        "reason": reason,
        "receipt_digest": None,
        "green_authorized": False,
        "frozen_authorized": False,
    }


def build_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _blocked("proof payload must be an object")
    if _contains_foreign(payload):
        return _blocked("foreign-system evidence is forbidden in MONSTER proof")
    task_id = str(payload.get("task_id") or "").strip()
    candidate_sha = str(payload.get("candidate_sha") or "").strip().lower()
    gates = payload.get("gates")
    regressions = payload.get("regressions")
    production = payload.get("production")
    rollback_anchor = payload.get("rollback_anchor")
    freeze_target = str(payload.get("freeze_target") or "").strip()
    evidence = payload.get("evidence")
    if not task_id or not _SHA_RE.fullmatch(candidate_sha):
        return _blocked("task identity and exact candidate SHA are required")
    if not isinstance(gates, Mapping) or any(gates.get(name) != "GREEN" for name in _REQUIRED_GATES):
        return _blocked("every required MONSTER gate must be explicitly GREEN")
    if not isinstance(regressions, Mapping) or regressions.get("status") != "GREEN":
        return _blocked("regression evidence must be GREEN")
    if not isinstance(production, Mapping) or "deployment_applicable" not in production:
        return _blocked("production applicability must be explicit")
    if production.get("deployment_applicable") is False and production.get("proof") != "NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE":
        return _blocked("deployment N/A requires the read-only control-plane Step 2F proof")
    if production.get("deployment_applicable") is True:
        if not production.get("deployment_id") or not production.get("stable_alias_target"):
            return _blocked("applicable production proof requires deployment and stable alias identity")
    if not isinstance(rollback_anchor, Mapping) or not rollback_anchor:
        return _blocked("rollback anchor is required")
    if not freeze_target.startswith("MONSTER_") or not freeze_target.endswith("_FROZEN"):
        return _blocked("MONSTER freeze target is invalid")
    if not isinstance(evidence, Mapping):
        return _blocked("MONSTER evidence bundle is required")

    core = {
        "version": VERSION,
        "proof_authority": PROOF_AUTHORITY,
        "github_actions_role": GITHUB_ACTIONS_ROLE,
        "task_id": task_id,
        "candidate_sha": candidate_sha,
        "gates": {name: gates[name] for name in _REQUIRED_GATES},
        "regressions": dict(regressions),
        "production": dict(production),
        "rollback_anchor": dict(rollback_anchor),
        "freeze_target": freeze_target,
        "evidence_digest": _digest(evidence),
    }
    receipt_digest = _digest(core)
    return {
        "status": "GREEN",
        **core,
        "receipt_digest": receipt_digest,
        "green_authorized": True,
        "frozen_authorized": False,
    }


def validate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping) or receipt.get("status") != "GREEN":
        return _blocked("receipt is not GREEN")
    if _contains_foreign(receipt):
        return _blocked("foreign-system identity found in receipt")
    supplied = str(receipt.get("receipt_digest") or "")
    core = {key: value for key, value in receipt.items() if key not in {"status", "receipt_digest", "green_authorized", "frozen_authorized"}}
    if supplied != _digest(core):
        return _blocked("receipt digest mismatch")
    if receipt.get("proof_authority") != PROOF_AUTHORITY or receipt.get("github_actions_role") != GITHUB_ACTIONS_ROLE:
        return _blocked("proof authority mismatch")
    return {
        "status": "GREEN",
        "version": VERSION,
        "proof_authority": PROOF_AUTHORITY,
        "github_actions_role": GITHUB_ACTIONS_ROLE,
        "candidate_sha": receipt.get("candidate_sha"),
        "evidence_digest": receipt.get("evidence_digest"),
        "receipt_digest": supplied,
        "green_authorized": True,
        "frozen_authorized": False,
    }


def contract_self_test() -> dict[str, Any]:
    payload = {
        "task_id": "monster-receipt-self-test",
        "candidate_sha": "a" * 40,
        "gates": {name: "GREEN" for name in _REQUIRED_GATES},
        "regressions": {"status": "GREEN", "count": 1},
        "production": {"deployment_applicable": False, "proof": "NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE"},
        "rollback_anchor": {"sha": "b" * 40},
        "freeze_target": "MONSTER_RECEIPT_SELF_TEST_FROZEN",
        "evidence": {"source": "monster-only", "value": "self-test"},
    }
    receipt = build_receipt(payload)
    validation = validate_receipt(receipt)
    if validation.get("status") != "GREEN":
        raise RuntimeError(f"MONSTER receipt self-test failed: {validation}")
    return validation


if __name__ == "__main__":
    print("MONSTER_AUTHORITATIVE_PROOF_RECEIPT_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
