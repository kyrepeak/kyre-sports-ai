"""API 2 Finalization Authority V1 — canonical terminal completion resolver.

Step 1 is deliberately read-only.  The frozen registry plus an immutable
Runless receipt/gate and exact merge provenance are the terminal authority.
Task ledgers remain advisory and may be repaired by a later step.
"""
from __future__ import annotations

from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt

AUTHORITY = "FROZEN_REGISTRY_RUNLESS"


def _blocked(reason: str, *, freeze_token: str) -> dict[str, Any]:
    return {
        "complete": False,
        "status": "BLOCKED",
        "decision": "CANONICAL_COMPLETION_BLOCKED",
        "authority": AUTHORITY,
        "reason": reason,
        "frozen_token": freeze_token,
    }


def _ledger_is_stale(
    ledger: Mapping[str, Any], *, task_id: str, freeze_token: str
) -> bool:
    freeze_exit = ledger.get("freeze_exit")
    ledger_token = (
        str(freeze_exit.get("frozen_token") or "")
        if isinstance(freeze_exit, Mapping)
        else ""
    )
    return not (
        str(ledger.get("task_id") or "") == task_id
        and str(ledger.get("status") or "") == "DONE"
        and ledger.get("green_plus_frozen_claimed") is True
        and ledger_token == freeze_token
    )


def resolve_completion(
    *,
    task_id: str,
    freeze_token: str,
    ledger: Mapping[str, Any],
    registry: Mapping[str, Any],
    receipt: Mapping[str, Any],
    gate: Mapping[str, Any],
    merge_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve terminal completion from durable authority, never ledger opinion.

    The function has no side effects and fails closed on malformed or mismatched
    evidence.  A stale ledger is reported for later repair but cannot veto a
    complete canonical proof chain.
    """
    try:
        validate_registry(registry)
    except (TypeError, ValueError, KeyError, RuntimeError, AttributeError):
        return _blocked("FROZEN_REGISTRY_INVALID", freeze_token=freeze_token)

    entries = registry.get("entries")
    entry = entries.get(freeze_token) if isinstance(entries, Mapping) else None
    if not isinstance(entry, Mapping) or entry.get("status") != "FROZEN":
        return _blocked("FREEZE_TOKEN_NOT_FROZEN", freeze_token=freeze_token)

    try:
        validate_runless_receipt(receipt)
    except (TypeError, ValueError, KeyError, RuntimeError, AttributeError):
        return _blocked("RUNLESS_RECEIPT_INVALID", freeze_token=freeze_token)

    if (
        str(receipt.get("task_id") or "") != task_id
        or str(receipt.get("failure_class") or "") != "NONE"
    ):
        return _blocked("RUNLESS_RECEIPT_INVALID", freeze_token=freeze_token)

    if (
        str(gate.get("name") or "") != "runless-final-gate"
        or str(gate.get("conclusion") or "").lower() != "success"
    ):
        return _blocked("RUNLESS_FINAL_GATE_NOT_SUCCESS", freeze_token=freeze_token)

    candidate_sha = str(receipt.get("candidate_sha") or "")
    receipt_digest = str(receipt.get("digest") or "")
    if (
        str(gate.get("head_sha") or "") != candidate_sha
        or str(gate.get("receipt_digest") or "") != receipt_digest
    ):
        return _blocked("RUNLESS_GATE_RECEIPT_MISMATCH", freeze_token=freeze_token)

    merged_main_sha = str(entry.get("source_main_sha") or "")
    if not (
        merge_evidence.get("contains_candidate") is True
        and str(merge_evidence.get("candidate_sha") or "") == candidate_sha
        and str(merge_evidence.get("merged_main_sha") or "") == merged_main_sha
    ):
        return _blocked("MERGE_PROVENANCE_MISSING", freeze_token=freeze_token)

    ledger_stale = _ledger_is_stale(
        ledger if isinstance(ledger, Mapping) else {},
        task_id=task_id,
        freeze_token=freeze_token,
    )
    return {
        "complete": True,
        "status": "GREEN_FROZEN",
        "decision": "CANONICAL_GREEN_FROZEN",
        "authority": AUTHORITY,
        "ledger_stale": ledger_stale,
        "repair_recommended": ledger_stale,
        "task_id": task_id,
        "frozen_token": freeze_token,
        "candidate_sha": candidate_sha,
        "receipt_digest": receipt_digest,
        "merged_main_sha": merged_main_sha,
        "registry_revision": registry.get("revision"),
        "registry_state_hash": registry.get("state_hash"),
    }
