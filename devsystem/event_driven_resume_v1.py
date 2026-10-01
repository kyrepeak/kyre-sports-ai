"""MONSTER V5 Step 3 - Event-Driven Resume V1.

Turns material external/control-plane events into one-shot resume receipts bound
to an exact MONSTER V5 detached-continuation packet hash.

This module is deliberately side-effect free:
- no network calls;
- no repository mutation;
- no product/runtime mutation;
- no timer/polling loop;
- no mutation authority.

A caller persists state on the dedicated Git ref using revision/hash CAS.
Step 2A plus the V5 scope-aware lease remain the only mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.detached_execution_continuation_v1 import (
    DetachedContinuationFailure,
    build_packet,
    validate_packet,
)

VERSION = "MONSTER_V5_EVENT_DRIVEN_RESUME_V1"
STATE_REF = "refs/heads/monster-event-driven-resume"
STATE_PATH = "devsystem/event_driven_resume_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
POLLING_REQUIRED = False

_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{1,255}$")
_EVENT_KINDS = {
    "WORKFLOW_RUN",
    "LEASE_STATE",
    "PR_STATE",
    "DEPLOYMENT_STATE",
    "REGISTRY_STATE",
    "ARTIFACT_STATE",
    "BLOCKER_STATE",
    "GENERIC_STATE",
}
_TRIGGERS = {
    "TERMINAL",
    "FREE",
    "MERGED",
    "CHANGES",
    "APPEARS",
    "CLEARS",
    "READY",
    "EQUALS",
}
_TERMINAL_VALUES = {"SUCCESS", "FAILURE", "CANCELLED", "COMPLETED"}


class EventDrivenResumeFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(value))
    out.pop("state_hash", None)
    return out


def _hash64(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HASH64.fullmatch(text):
        raise EventDrivenResumeFailure(f"{field} must be sha256")
    return text


def _required(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EventDrivenResumeFailure(f"{field} is required")
    return text


def _identity(value: Any, field: str) -> str:
    text = _required(value, field)
    if not _ID_RE.fullmatch(text):
        raise EventDrivenResumeFailure(f"{field} has invalid characters")
    return text


def _norm_map(value: Mapping[str, Any] | None, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise EventDrivenResumeFailure(f"{field} must be a non-empty object")
    result: dict[str, str] = {}
    for key, raw in sorted(value.items()):
        k = str(key or "").strip().lower()
        v = str(raw or "").strip()
        if not k or not v:
            raise EventDrivenResumeFailure(f"{field} contains empty key/value")
        result[k] = v
    return result


def _cas(state: Mapping[str, Any], revision: int, state_hash: str) -> dict[str, Any] | None:
    if int(state["revision"]) != int(revision) or str(state["state_hash"]) != str(state_hash):
        return {
            "decision": "EVENT_RESUME_STALE_CAS",
            "allowed": False,
            "next_legal_action": "REREAD_EVENT_RESUME_STATE",
        }
    return None


def new_state(repository: str) -> dict[str, Any]:
    repo = str(repository or "").strip().lower()
    if "/" not in repo:
        raise EventDrivenResumeFailure("repository must be owner/name")
    state = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "state_ref": STATE_REF,
        "state_path": STATE_PATH,
        "revision": 0,
        "generation": 0,
        "watches": {},
        "consumed_events": {},
        "ready": {},
        "consumed_ready": {},
    }
    state["state_hash"] = _hash(state)
    return validate_state(state)


def build_watch(
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    event_kind: str,
    selector: Mapping[str, Any],
    trigger: str,
    next_legal_action: str,
    baseline_value: str | None = None,
    target_value: str | None = None,
) -> dict[str, Any]:
    workstream = _identity(workstream_id, "workstream_id")
    packet_hash = _hash64(continuation_packet_hash, "continuation_packet_hash")
    kind = str(event_kind or "").strip().upper()
    trig = str(trigger or "").strip().upper()
    if kind not in _EVENT_KINDS:
        raise EventDrivenResumeFailure("event_kind invalid")
    if trig not in _TRIGGERS:
        raise EventDrivenResumeFailure("trigger invalid")
    selector_norm = _norm_map(selector, "selector")
    baseline = str(baseline_value).strip().upper() if baseline_value is not None else None
    target = str(target_value).strip().upper() if target_value is not None else None
    if trig == "CHANGES" and not baseline:
        raise EventDrivenResumeFailure("CHANGES trigger requires baseline_value")
    if trig == "EQUALS" and not target:
        raise EventDrivenResumeFailure("EQUALS trigger requires target_value")
    seed = {
        "workstream_id": workstream,
        "continuation_packet_hash": packet_hash,
        "event_kind": kind,
        "selector": selector_norm,
        "trigger": trig,
        "baseline_value": baseline,
        "target_value": target,
        "next_legal_action": _required(next_legal_action, "next_legal_action"),
    }
    watch_id = "WATCH-" + _hash(seed)[:24].upper()
    return {
        "watch_id": watch_id,
        **seed,
        "status": "ACTIVE",
    }


def build_watch_from_packet(
    packet: Mapping[str, Any],
    *,
    event_kind: str,
    selector: Mapping[str, Any],
    trigger: str,
    next_legal_action: str,
    baseline_value: str | None = None,
    target_value: str | None = None,
) -> dict[str, Any]:
    validated = validate_packet(packet)
    return build_watch(
        workstream_id=validated["workstream_id"],
        continuation_packet_hash=validated["packet_hash"],
        event_kind=event_kind,
        selector=selector,
        trigger=trigger,
        next_legal_action=next_legal_action,
        baseline_value=baseline_value,
        target_value=target_value,
    )


def build_event(
    *,
    event_kind: str,
    selector: Mapping[str, Any],
    value: str,
    source_id: str,
) -> dict[str, Any]:
    kind = str(event_kind or "").strip().upper()
    if kind not in _EVENT_KINDS:
        raise EventDrivenResumeFailure("event_kind invalid")
    body = {
        "event_kind": kind,
        "selector": _norm_map(selector, "selector"),
        "value": _required(value, "value").upper(),
        "source_id": _identity(source_id, "source_id"),
    }
    body["event_fingerprint"] = _hash(body)
    return body


def _validate_watch(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise EventDrivenResumeFailure("watch must be object")
    watch = build_watch(
        workstream_id=raw.get("workstream_id"),
        continuation_packet_hash=raw.get("continuation_packet_hash"),
        event_kind=raw.get("event_kind"),
        selector=raw.get("selector"),
        trigger=raw.get("trigger"),
        next_legal_action=raw.get("next_legal_action"),
        baseline_value=raw.get("baseline_value"),
        target_value=raw.get("target_value"),
    )
    if watch["watch_id"] != str(raw.get("watch_id") or ""):
        raise EventDrivenResumeFailure("watch id mismatch")
    status = str(raw.get("status") or "").upper()
    if status not in {"ACTIVE", "FIRED"}:
        raise EventDrivenResumeFailure("watch status invalid")
    watch["status"] = status
    return watch


def _validate_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise EventDrivenResumeFailure("event must be object")
    event = build_event(
        event_kind=raw.get("event_kind"),
        selector=raw.get("selector"),
        value=raw.get("value"),
        source_id=raw.get("source_id"),
    )
    if event["event_fingerprint"] != str(raw.get("event_fingerprint") or ""):
        raise EventDrivenResumeFailure("event fingerprint mismatch")
    return event


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise EventDrivenResumeFailure("event resume state must be object")
    state = deepcopy(dict(payload))
    if int(state.get("schema_version", 0)) != 1 or state.get("version") != VERSION:
        raise EventDrivenResumeFailure("event resume state version/schema mismatch")
    if state.get("state_ref") != STATE_REF or state.get("state_path") != STATE_PATH:
        raise EventDrivenResumeFailure("event resume persistence identity mismatch")
    if "/" not in str(state.get("repository") or ""):
        raise EventDrivenResumeFailure("repository invalid")
    if int(state.get("revision", -1)) < 0 or int(state.get("generation", -1)) < 0:
        raise EventDrivenResumeFailure("revision/generation invalid")

    watches = state.get("watches")
    consumed_events = state.get("consumed_events")
    ready = state.get("ready")
    consumed_ready = state.get("consumed_ready")
    if not all(isinstance(v, Mapping) for v in (watches, consumed_events, ready, consumed_ready)):
        raise EventDrivenResumeFailure("event resume maps malformed")

    normalized_watches: dict[str, Any] = {}
    for key, raw in watches.items():
        watch = _validate_watch(raw)
        if str(key) != watch["watch_id"]:
            raise EventDrivenResumeFailure("watch key mismatch")
        normalized_watches[str(key)] = watch
    state["watches"] = dict(sorted(normalized_watches.items()))

    for fingerprint, receipt in consumed_events.items():
        _hash64(fingerprint, "consumed event fingerprint")
        if not isinstance(receipt, Mapping):
            raise EventDrivenResumeFailure("consumed event receipt malformed")
        if str(receipt.get("event_fingerprint") or "") != fingerprint:
            raise EventDrivenResumeFailure("consumed event key mismatch")

    for workstream, receipt in ready.items():
        _identity(workstream, "ready workstream")
        if not isinstance(receipt, Mapping):
            raise EventDrivenResumeFailure("ready receipt malformed")
        if str(receipt.get("workstream_id") or "") != workstream:
            raise EventDrivenResumeFailure("ready workstream mismatch")
        _hash64(receipt.get("event_fingerprint"), "ready event_fingerprint")
        _hash64(receipt.get("continuation_packet_hash"), "ready continuation_packet_hash")
        if receipt.get("mutation_authority_granted") is not False:
            raise EventDrivenResumeFailure("ready receipt may not grant mutation authority")

    for fingerprint, receipt in consumed_ready.items():
        _hash64(fingerprint, "consumed ready fingerprint")
        if not isinstance(receipt, Mapping):
            raise EventDrivenResumeFailure("consumed ready receipt malformed")

    supplied = _hash64(state.get("state_hash"), "state_hash")
    expected = _hash(_without_hash(state))
    if supplied != expected:
        raise EventDrivenResumeFailure("event resume state hash mismatch")
    state["state_hash"] = supplied
    return state


def register_watch(
    state: Mapping[str, Any],
    watch: Mapping[str, Any],
    *,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}
    candidate = _validate_watch(watch)
    existing = current["watches"].get(candidate["watch_id"])
    if existing is not None:
        return {
            "result": {
                "decision": "EVENT_WATCH_ALREADY_REGISTERED",
                "allowed": True,
                "watch_id": candidate["watch_id"],
                "state_hash": current["state_hash"],
            },
            "state": current,
        }
    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    updated["watches"][candidate["watch_id"]] = candidate
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    updated = validate_state(updated)
    return {
        "result": {
            "decision": "EVENT_WATCH_REGISTERED",
            "allowed": True,
            "watch_id": candidate["watch_id"],
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def _satisfies(watch: Mapping[str, Any], value: str) -> bool:
    observed = str(value or "").strip().upper()
    trigger = str(watch["trigger"]).upper()
    if trigger == "TERMINAL":
        return observed in _TERMINAL_VALUES
    if trigger == "FREE":
        return observed == "FREE"
    if trigger == "MERGED":
        return observed == "MERGED"
    if trigger == "CHANGES":
        return observed != str(watch.get("baseline_value") or "").upper()
    if trigger == "APPEARS":
        return observed == "PRESENT"
    if trigger == "CLEARS":
        return observed == "CLEARED"
    if trigger == "READY":
        return observed == "READY"
    if trigger == "EQUALS":
        return observed == str(watch.get("target_value") or "").upper()
    return False


def ingest_event(
    state: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    current_continuation_packet_hashes: Mapping[str, str],
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}
    evt = _validate_event(event)
    fingerprint = evt["event_fingerprint"]
    if fingerprint in current["consumed_events"]:
        return {
            "result": {
                "decision": "EVENT_ALREADY_CONSUMED",
                "allowed": False,
                "event_fingerprint": fingerprint,
                "duplicate_wake_blocked": True,
            },
            "state": current,
        }

    matching = [
        w for w in current["watches"].values()
        if w["status"] == "ACTIVE"
        and w["event_kind"] == evt["event_kind"]
        and w["selector"] == evt["selector"]
    ]
    if not matching:
        return {
            "result": {
                "decision": "EVENT_NOT_MATERIAL",
                "allowed": False,
                "event_fingerprint": fingerprint,
            },
            "state": current,
        }

    drifted: list[str] = []
    triggered: list[dict[str, Any]] = []
    for watch in matching:
        live_hash = str(current_continuation_packet_hashes.get(watch["workstream_id"]) or "").lower()
        if live_hash != watch["continuation_packet_hash"]:
            drifted.append(watch["watch_id"])
            continue
        if _satisfies(watch, evt["value"]):
            triggered.append(watch)

    if not triggered:
        decision = "EVENT_CONTINUATION_DRIFT" if drifted else "EVENT_NOT_MATERIAL"
        return {
            "result": {
                "decision": decision,
                "allowed": False,
                "event_fingerprint": fingerprint,
                "drifted_watch_ids": sorted(drifted),
                "next_legal_action": (
                    "REREGISTER_WATCH_FROM_CURRENT_CONTINUATION"
                    if drifted else "WAIT_FOR_MATERIAL_EVENT"
                ),
            },
            "state": current,
        }

    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    wake_receipts: list[dict[str, Any]] = []
    for watch in triggered:
        wid = watch["watch_id"]
        workstream = watch["workstream_id"]
        updated["watches"][wid]["status"] = "FIRED"
        receipt = {
            "workstream_id": workstream,
            "watch_id": wid,
            "event_fingerprint": fingerprint,
            "event_kind": evt["event_kind"],
            "event_value": evt["value"],
            "source_id": evt["source_id"],
            "continuation_packet_hash": watch["continuation_packet_hash"],
            "next_legal_action": watch["next_legal_action"],
            "mutation_authority_granted": False,
            "step_2a_required": True,
            "scope_lease_required_for_mutation": True,
        }
        if workstream not in updated["ready"]:
            updated["ready"][workstream] = receipt
            wake_receipts.append(receipt)

    updated["consumed_events"][fingerprint] = {
        "event_fingerprint": fingerprint,
        "event_kind": evt["event_kind"],
        "source_id": evt["source_id"],
        "triggered_watch_ids": sorted(w["watch_id"] for w in triggered),
        "wake_count": len(wake_receipts),
    }
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    updated = validate_state(updated)
    return {
        "result": {
            "decision": "EVENT_MATERIAL_RESUME_READY",
            "allowed": True,
            "event_fingerprint": fingerprint,
            "wake_count": len(wake_receipts),
            "ready_workstreams": sorted(r["workstream_id"] for r in wake_receipts),
            "duplicate_wake_blocked": True,
            "polling_required": False,
            "mutation_authority_granted": False,
        },
        "state": updated,
    }


def resume_decision(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    current_continuation_packet_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    workstream = _identity(workstream_id, "workstream_id")
    receipt = current["ready"].get(workstream)
    if receipt is None:
        return {
            "decision": "EVENT_RESUME_NOT_READY",
            "allowed_to_resume": False,
            "polling_required": False,
            "mutation_authority_granted": False,
        }
    live_hash = _hash64(current_continuation_packet_hash, "current_continuation_packet_hash")
    if live_hash != receipt["continuation_packet_hash"]:
        return {
            "decision": "EVENT_RESUME_CONTINUATION_DRIFT",
            "allowed_to_resume": False,
            "next_legal_action": "REREGISTER_WATCH_FROM_CURRENT_CONTINUATION",
            "mutation_authority_granted": False,
        }
    return {
        "decision": "EVENT_READY_TO_RESUME",
        "allowed_to_resume": True,
        "workstream_id": workstream,
        "event_fingerprint": receipt["event_fingerprint"],
        "next_legal_action": receipt["next_legal_action"],
        "polling_required": False,
        "mutation_authority_granted": False,
        "step_2a_required": True,
        "scope_lease_required_for_mutation": True,
    }


def consume_ready(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    event_fingerprint: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}
    workstream = _identity(workstream_id, "workstream_id")
    fingerprint = _hash64(event_fingerprint, "event_fingerprint")
    receipt = current["ready"].get(workstream)
    if receipt is None or receipt["event_fingerprint"] != fingerprint:
        return {
            "result": {
                "decision": "EVENT_READY_RECEIPT_NOT_FOUND",
                "allowed": False,
            },
            "state": current,
        }
    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    consumed = updated["ready"].pop(workstream)
    updated["consumed_ready"][fingerprint] = {
        **consumed,
        "consumed": True,
    }
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    updated = validate_state(updated)
    return {
        "result": {
            "decision": "EVENT_READY_RECEIPT_CONSUMED",
            "allowed": True,
            "workstream_id": workstream,
            "event_fingerprint": fingerprint,
            "next_legal_action": consumed["next_legal_action"],
            "mutation_authority_granted": False,
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def contract_self_test() -> dict[str, Any]:
    lease = {
        "owner_id": "chat:step3",
        "lease_id": "SCOPE-LEASE-STEP3",
        "generation": 1,
        "revision": 1,
        "state_hash": "1" * 64,
    }
    registry = {"revision": 11, "state_hash": "2" * 64, "checkpoint_count": 25}
    packet = build_packet(
        workstream_id="monster-v5-step3",
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        current_step=3,
        total_steps=5,
        step_title="Event-Driven Resume",
        execution_state="READY",
        branch="feature",
        head_sha="a" * 40,
        main_sha="b" * 40,
        pr_number=1300,
        authoritative_run_id=77,
        authoritative_job_id=None,
        async_state="SUCCESS",
        scope_lease=lease,
        frozen_registry=registry,
        blocker=None,
        last_completed_action="registered event watch",
        next_legal_action="MERGE_PR_1300",
        worker_id="worker-a",
    )
    packet = validate_packet(packet)

    state = new_state("owner/repo")
    watch = build_watch_from_packet(
        packet,
        event_kind="WORKFLOW_RUN",
        selector={"run_id": "77"},
        trigger="TERMINAL",
        next_legal_action="CLASSIFY_RUN_77_TERMINAL",
    )
    registered = register_watch(
        state, watch,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    live = registered["state"]
    event = build_event(
        event_kind="WORKFLOW_RUN",
        selector={"run_id": "77"},
        value="SUCCESS",
        source_id="github-run-77",
    )
    fired = ingest_event(
        live, event,
        current_continuation_packet_hashes={"monster-v5-step3": packet["packet_hash"]},
        expected_revision=live["revision"],
        expected_state_hash=live["state_hash"],
    )
    ready_state = fired["state"]
    duplicate = ingest_event(
        ready_state, event,
        current_continuation_packet_hashes={"monster-v5-step3": packet["packet_hash"]},
        expected_revision=ready_state["revision"],
        expected_state_hash=ready_state["state_hash"],
    )
    ready = resume_decision(
        ready_state,
        workstream_id="monster-v5-step3",
        current_continuation_packet_hash=packet["packet_hash"],
    )
    drift = resume_decision(
        ready_state,
        workstream_id="monster-v5-step3",
        current_continuation_packet_hash="3" * 64,
    )
    consumed = consume_ready(
        ready_state,
        workstream_id="monster-v5-step3",
        event_fingerprint=event["event_fingerprint"],
        expected_revision=ready_state["revision"],
        expected_state_hash=ready_state["state_hash"],
    )
    consumed_again = consume_ready(
        consumed["state"],
        workstream_id="monster-v5-step3",
        event_fingerprint=event["event_fingerprint"],
        expected_revision=consumed["state"]["revision"],
        expected_state_hash=consumed["state"]["state_hash"],
    )
    stale = register_watch(
        ready_state,
        build_watch(
            workstream_id="x-stream",
            continuation_packet_hash="4" * 64,
            event_kind="LEASE_STATE",
            selector={"lease": "x"},
            trigger="FREE",
            next_legal_action="CLAIM_SCOPE",
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )

    trigger_matrix = {
        "terminal": _satisfies({"trigger": "TERMINAL"}, "SUCCESS"),
        "free": _satisfies({"trigger": "FREE"}, "FREE"),
        "merged": _satisfies({"trigger": "MERGED"}, "MERGED"),
        "changes": _satisfies({"trigger": "CHANGES", "baseline_value": "A"}, "B"),
        "appears": _satisfies({"trigger": "APPEARS"}, "PRESENT"),
        "clears": _satisfies({"trigger": "CLEARS"}, "CLEARED"),
        "ready": _satisfies({"trigger": "READY"}, "READY"),
        "equals": _satisfies({"trigger": "EQUALS", "target_value": "GREEN"}, "GREEN"),
    }

    irrelevant = ingest_event(
        consumed["state"],
        build_event(
            event_kind="PR_STATE",
            selector={"pr": "99"},
            value="MERGED",
            source_id="github-pr-99",
        ),
        current_continuation_packet_hashes={"monster-v5-step3": packet["packet_hash"]},
        expected_revision=consumed["state"]["revision"],
        expected_state_hash=consumed["state"]["state_hash"],
    )

    tampered = deepcopy(consumed["state"])
    tampered["generation"] += 1
    tamper_rejected = False
    try:
        validate_state(tampered)
    except EventDrivenResumeFailure:
        tamper_rejected = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "repository_backed_event_state": STATE_REF.startswith("refs/heads/"),
        "continuation_packet_bound": watch["continuation_packet_hash"] == packet["packet_hash"],
        "material_event_wakes_once": fired["result"]["decision"] == "EVENT_MATERIAL_RESUME_READY",
        "duplicate_event_blocked": duplicate["result"]["decision"] == "EVENT_ALREADY_CONSUMED",
        "resume_without_polling": ready["decision"] == "EVENT_READY_TO_RESUME" and ready["polling_required"] is False,
        "continuation_drift_fails_closed": drift["decision"] == "EVENT_RESUME_CONTINUATION_DRIFT",
        "ready_receipt_one_shot": (
            consumed["result"]["decision"] == "EVENT_READY_RECEIPT_CONSUMED"
            and consumed_again["result"]["decision"] == "EVENT_READY_RECEIPT_NOT_FOUND"
        ),
        "stale_cas_blocked": stale["result"]["decision"] == "EVENT_RESUME_STALE_CAS",
        "irrelevant_event_does_not_wake": irrelevant["result"]["decision"] == "EVENT_NOT_MATERIAL",
        "trigger_matrix_complete": all(trigger_matrix.values()),
        "tamper_evident_state": tamper_rejected,
        "step_2a_still_required": ready["step_2a_required"] is True,
        "scope_lease_still_required": ready["scope_lease_required_for_mutation"] is True,
        "event_never_grants_mutation": MUTATION_AUTHORITY_GRANTED is False,
        "polling_required": POLLING_REQUIRED,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        k for k, v in result.items()
        if isinstance(v, bool)
        and k not in {"polling_required", "network_calls", "auto_mutate", "product_runtime_mutation"}
    ]
    if not all(result[k] is True for k in required):
        raise EventDrivenResumeFailure("event-driven resume self-test failed")
    if result["polling_required"] or result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise EventDrivenResumeFailure("event-driven resume safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V5_EVENT_DRIVEN_RESUME_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EventDrivenResumeFailure, DetachedContinuationFailure) as exc:
        print(f"MONSTER_V5_EVENT_DRIVEN_RESUME_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
