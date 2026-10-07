from __future__ import annotations

from typing import Any, Mapping

from devsystem.event_driven_resume_v1 import (
    build_watch_from_packet,
    consume_ready,
    ingest_event,
    register_watch,
    resume_decision,
)

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
POLLING_REQUIRED = False


def _result(decision: str, **extra: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "polling_required": False,
        "mutation_authority_granted": False,
        **extra,
    }


def register_runless_wait(
    state: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
    event_kind: str,
    selector: Mapping[str, Any],
    trigger: str,
    next_legal_action: str,
    expected_revision: int,
    expected_state_hash: str,
    baseline_value: str | None = None,
    target_value: str | None = None,
) -> dict[str, Any]:
    watch = build_watch_from_packet(
        packet,
        event_kind=event_kind,
        selector=selector,
        trigger=trigger,
        next_legal_action=next_legal_action,
        baseline_value=baseline_value,
        target_value=target_value,
    )
    registered = register_watch(
        state,
        watch,
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
    )
    decision = str((registered.get("result") or {}).get("decision") or "")
    if decision == "EVENT_RESUME_STALE_CAS":
        registered["result"] = _result(
            "RUNLESS_EVENT_STATE_STALE",
            retry_allowed_now=False,
            next_legal_action="REREAD_EVENT_RESUME_STATE",
        )
    else:
        registered["result"] = _result(
            "RUNLESS_EVENT_WAIT_ARMED",
            watch_id=watch["watch_id"],
            step_2a_required=True,
        )
    return registered


def ingest_runless_event(
    state: Mapping[str, Any],
    *,
    event: Mapping[str, Any],
    current_continuation_packet_hashes: Mapping[str, str],
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    ingested = ingest_event(
        state,
        event,
        current_continuation_packet_hashes=current_continuation_packet_hashes,
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
    )
    raw = dict(ingested.get("result") or {})
    decision = str(raw.get("decision") or "")

    if decision == "EVENT_MATERIAL_RESUME_READY":
        mapped = _result(
            "RUNLESS_EVENT_RESUME_READY",
            ready_workstreams=list(raw.get("ready_workstreams") or []),
            duplicate_wake_blocked=False,
            step_2a_required=True,
        )
    elif decision == "EVENT_ALREADY_CONSUMED":
        mapped = _result(
            "RUNLESS_EVENT_DUPLICATE_BLOCKED",
            duplicate_wake_blocked=True,
            event_fingerprint=raw.get("event_fingerprint"),
        )
    elif decision == "EVENT_RESUME_STALE_CAS":
        mapped = _result(
            "RUNLESS_EVENT_STATE_STALE",
            retry_allowed_now=False,
            next_legal_action="REREAD_EVENT_RESUME_STATE",
        )
    elif decision == "EVENT_CONTINUATION_DRIFT":
        mapped = _result(
            "RUNLESS_EVENT_CONTINUATION_DRIFT",
            retry_allowed_now=False,
            next_legal_action=raw.get("next_legal_action"),
        )
    else:
        mapped = _result(
            "RUNLESS_EVENT_WAITING",
            retry_allowed_now=False,
            next_legal_action=raw.get("next_legal_action", "WAIT_FOR_MATERIAL_EVENT"),
        )

    return {"result": mapped, "state": ingested["state"]}


def claim_runless_resume(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    current_continuation_packet_hash: str,
    step2a_authorized: bool,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    if not step2a_authorized:
        return {
            "result": _result(
                "RUNLESS_RESUME_STEP2A_REQUIRED",
                retry_allowed_now=False,
                step_2a_required=True,
            ),
            "state": state,
        }

    ready = resume_decision(
        state,
        workstream_id=workstream_id,
        current_continuation_packet_hash=current_continuation_packet_hash,
    )
    decision = str(ready.get("decision") or "")
    if decision == "EVENT_RESUME_CONTINUATION_DRIFT":
        return {
            "result": _result(
                "RUNLESS_RESUME_CONTINUATION_DRIFT",
                retry_allowed_now=False,
                next_legal_action=ready.get("next_legal_action"),
            ),
            "state": state,
        }
    if decision == "EVENT_RESUME_NOT_READY":
        return {
            "result": _result(
                "RUNLESS_RESUME_NOT_READY",
                retry_allowed_now=False,
            ),
            "state": state,
        }
    if decision != "EVENT_READY_TO_RESUME":
        return {
            "result": _result(
                "RUNLESS_RESUME_BLOCKED",
                retry_allowed_now=False,
            ),
            "state": state,
        }

    consumed = consume_ready(
        state,
        workstream_id=workstream_id,
        event_fingerprint=str(ready["event_fingerprint"]),
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
    )
    raw = dict(consumed.get("result") or {})
    consumed_decision = str(raw.get("decision") or "")
    if consumed_decision == "EVENT_RESUME_STALE_CAS":
        mapped = _result(
            "RUNLESS_EVENT_STATE_STALE",
            retry_allowed_now=False,
            next_legal_action="REREAD_EVENT_RESUME_STATE",
        )
    elif consumed_decision == "EVENT_READY_RECEIPT_CONSUMED":
        mapped = _result(
            "RUNLESS_RESUME_CONSUMED",
            next_legal_action=raw.get("next_legal_action"),
            step_2a_required=True,
        )
    else:
        mapped = _result(
            "RUNLESS_RESUME_NOT_READY",
            retry_allowed_now=False,
        )
    return {"result": mapped, "state": consumed["state"]}
