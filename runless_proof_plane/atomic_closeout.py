from __future__ import annotations

from typing import Any, Mapping

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

_REQUIRED_OPERATIONS = [
    "PERSIST_OR_VERIFY_MERGED_RECEIPT",
    "PUBLISH_OR_VERIFY_RUNLESS_GATE",
    "FREEZE_OR_VERIFY_EXACT_ARTIFACTS",
    "CANONICAL_READBACK",
]


def _result(decision: str, *, allowed: bool, **extra: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "allowed": bool(allowed),
        "network_calls": False,
        "auto_mutate": False,
        "mutation_authority_granted": False,
        "github_actions_fallback": 0,
        **extra,
    }


def _exact_freeze_entry(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "FROZEN",
        "checkpoint_id": str(request["freeze_token"]),
        "source_main_sha": str(request["main_sha"]),
        "artifacts": dict(request["freeze_artifacts"]),
    }


def evaluate_atomic_closeout(
    request: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the one legal, idempotent closeout decision for an exact Runless state.

    This module is intentionally pure: it does not make network calls or mutate GitHub,
    the registry, product runtime, or sports models.  The caller may execute the returned
    ordered operations only after its own Step 2A mutation authorization.
    """

    if bool(request.get("github_actions_fallback_authorized")):
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_ACTIONS_FALLBACK_BLOCKED",
            allowed=False,
            retry_allowed_now=False,
        )

    expected_main = str(request.get("main_sha") or "")
    observed_main = str(state.get("main_sha") or "")
    if observed_main != expected_main:
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_MAIN_DRIFT",
            allowed=False,
            retry_allowed_now=False,
            next_legal_action="REREAD_MAIN_AND_STEP2A",
        )

    source_candidate = str(request.get("source_candidate_sha") or "")
    parents = {str(value) for value in (state.get("candidate_parent_shas") or [])}
    if source_candidate not in parents:
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_ANCESTRY_DRIFT",
            allowed=False,
            retry_allowed_now=False,
            next_legal_action="REREAD_MERGE_ANCESTRY_AND_STEP2A",
        )

    lease = dict(state.get("lease") or {})
    identity = dict(lease.get("resource_identity") or {})
    if (
        str(lease.get("lease_id") or "") != str(request.get("lease_id") or "")
        or str(lease.get("owner_id") or "") != str(request.get("lease_owner") or "")
        or str(identity.get("main_sha") or "") != expected_main
        or str(identity.get("registry_state_hash") or "")
        != str(request.get("registry_state_hash") or "")
    ):
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_STEP2A_REQUIRED",
            allowed=False,
            retry_allowed_now=False,
            next_legal_action="REREAD_LEASE_AND_STEP2A",
        )

    registry = dict(state.get("registry") or {})
    if (
        int(registry.get("revision", -1)) != int(request.get("registry_revision", -2))
        or str(registry.get("state_hash") or "")
        != str(request.get("registry_state_hash") or "")
        or str(registry.get("source_main_sha") or "") != expected_main
    ):
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_REGISTRY_STALE",
            allowed=False,
            retry_allowed_now=False,
            next_legal_action="REREAD_REGISTRY_AND_STEP2A",
        )

    freeze_token = str(request.get("freeze_token") or "")
    entries = dict(registry.get("entries") or {})
    expected_entry = _exact_freeze_entry(request)
    existing_entry = entries.get(freeze_token)
    if existing_entry is not None:
        if dict(existing_entry) != expected_entry:
            return _result(
                "RUNLESS_ATOMIC_CLOSEOUT_FREEZE_DRIFT",
                allowed=False,
                retry_allowed_now=False,
                next_legal_action="STOP_AND_RECONCILE_FREEZE_TOKEN",
            )
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_ALREADY_COMPLETE",
            allowed=True,
            duplicate_write_required=False,
            required_operations=[],
            static_evidence_reexecuted=False,
        )

    merged_receipt = state.get("merged_receipt")
    if merged_receipt is not None:
        receipt = dict(merged_receipt)
        if (
            str(receipt.get("prior_digest") or "")
            != str(request.get("premerge_receipt_digest") or "")
            or str(receipt.get("candidate_sha") or "") != expected_main
        ):
            return _result(
                "RUNLESS_ATOMIC_CLOSEOUT_RECEIPT_DRIFT",
                allowed=False,
                retry_allowed_now=False,
                next_legal_action="STOP_AND_RECONCILE_RECEIPT",
            )

    gate_digest = state.get("gate_receipt_digest")
    if gate_digest is not None and merged_receipt is None:
        return _result(
            "RUNLESS_ATOMIC_CLOSEOUT_GATE_WITHOUT_RECEIPT",
            allowed=False,
            retry_allowed_now=False,
            next_legal_action="STOP_AND_RECONCILE_GATE",
        )

    return _result(
        "RUNLESS_ATOMIC_CLOSEOUT_READY",
        allowed=True,
        duplicate_write_required=False,
        required_operations=list(_REQUIRED_OPERATIONS),
        static_evidence_reexecuted=False,
        preserve_unrelated_thaws=True,
        step_2a_required_before_mutation=True,
    )
