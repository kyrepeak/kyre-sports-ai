"""MONSTER V7 Step 7 — Progress Truth + Stuck-State Detector V1.

Progress is derived only from required checkpoint terminal evidence.
No smoothing, guessed percentages, or hidden remainder are allowed.

A wait becomes stuck only after its material-event deadline is breached.
Async waits reuse the frozen V5 heartbeat/dead-man inspector so a long-running
but live authoritative run is never misclassified as dead. Stuck escalation is
single-use per unchanged stuck fingerprint; identical evidence waits for an
event instead of emitting the same recovery action again.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.execution_heartbeat_deadman_recovery_v1 import (
    VERSION as HEARTBEAT_VERSION,
    inspect_dead_man,
    new_state as new_heartbeat_state,
    register_worker,
)
from devsystem.final_mile_autopilot_v1 import (
    VERSION as AUTOPILOT_VERSION,
)

VERSION = "MONSTER_V7_PROGRESS_TRUTH_STUCK_STATE_DETECTOR_V1"
REQUIRED_HEARTBEAT_VERSION = "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_V1"
REQUIRED_AUTOPILOT_VERSION = "MONSTER_V7_FINAL_MILE_AUTOPILOT_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_STATUSES = {"COMPLETE", "PENDING", "WAITING", "BLOCKED", "NOT_REQUIRED"}
_ASYNC_WAIT_KINDS = {
    "EXACT_HEAD_PROOF",
    "MERGED_MAIN_CERTIFICATION",
    "GENERIC_ASYNC_EVENT",
}
_WAIT_ROUTES = {
    "LEASE_HANDOFF": "INSPECT_ATOMIC_WAIT_QUEUE",
    "EXACT_HEAD_PROOF": "INSPECT_AUTHORITATIVE_RUN",
    "MERGE_EVENT": "INSPECT_PR_MERGE_GATE",
    "MERGED_MAIN_CERTIFICATION": "INSPECT_AUTHORITATIVE_RUN",
    "DEPLOYMENT_EVENT": "RUN_DEPLOYMENT_CONVERGENCE",
    "FREEZE_REGISTRY_EVENT": "VERIFY_FROZEN_REGISTRY",
    "GENERIC_ASYNC_EVENT": "INSPECT_EXECUTION_HEARTBEAT",
}


class ProgressTruthFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ProgressTruthFailure(f"{field} is required")
    return out


def _utc(value: Any) -> datetime:
    text = _text(value, "timestamp").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ProgressTruthFailure("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def new_state(workstream_id: str) -> dict[str, Any]:
    state = {
        "schema_version": 1,
        "version": VERSION,
        "workstream_id": _text(workstream_id, "workstream_id"),
        "revision": 0,
        "issued_escalations": {},
    }
    state["state_hash"] = _hash(state)
    return validate_state(state)


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ProgressTruthFailure("detector state must be an object")
    state = deepcopy(dict(payload))
    if int(state.get("schema_version", 0)) != 1 or state.get("version") != VERSION:
        raise ProgressTruthFailure("detector state version/schema mismatch")
    _text(state.get("workstream_id"), "workstream_id")
    if int(state.get("revision", -1)) < 0:
        raise ProgressTruthFailure("revision invalid")
    issued = state.get("issued_escalations")
    if not isinstance(issued, Mapping):
        raise ProgressTruthFailure("issued_escalations must be an object")
    for fingerprint, action in issued.items():
        if not _HASH64.fullmatch(str(fingerprint)):
            raise ProgressTruthFailure("invalid escalation fingerprint")
        _text(action, "issued escalation action")
    supplied = str(state.get("state_hash") or "").lower()
    unsigned = deepcopy(state)
    unsigned.pop("state_hash", None)
    if supplied != _hash(unsigned):
        raise ProgressTruthFailure("detector state hash mismatch")
    return state


def _rehash(state: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(state))
    out.pop("state_hash", None)
    out["state_hash"] = _hash(out)
    return validate_state(out)


def _normalize_checkpoint(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ProgressTruthFailure("checkpoint must be an object")
    required = bool(raw.get("required", True))
    try:
        weight = int(raw.get("weight_bps", 0))
    except (TypeError, ValueError) as exc:
        raise ProgressTruthFailure("weight_bps must be an integer") from exc
    if required and weight <= 0:
        raise ProgressTruthFailure("required checkpoint weight_bps must be positive")
    if not required and weight != 0:
        raise ProgressTruthFailure("optional checkpoint weight_bps must be zero")
    status = _text(raw.get("status"), "checkpoint status").upper()
    if status not in _STATUSES:
        raise ProgressTruthFailure(f"unsupported checkpoint status: {status}")
    if status == "NOT_REQUIRED" and required:
        raise ProgressTruthFailure("required checkpoint cannot be NOT_REQUIRED")
    if not required and status != "NOT_REQUIRED":
        raise ProgressTruthFailure("optional checkpoint must be NOT_REQUIRED")

    out = {
        "checkpoint_id": _text(raw.get("checkpoint_id"), "checkpoint_id"),
        "label": _text(raw.get("label"), "checkpoint label"),
        "required": required,
        "weight_bps": weight,
        "status": status,
        "owner": str(raw.get("owner") or "").strip(),
        "next_action": str(raw.get("next_action") or "").strip(),
        "terminal_evidence": str(raw.get("terminal_evidence") or "").strip(),
        "blocker_reason": str(raw.get("blocker_reason") or "").strip(),
        "wait_kind": str(raw.get("wait_kind") or "").strip().upper(),
        "entered_wait_at_utc": str(raw.get("entered_wait_at_utc") or "").strip(),
        "last_material_event_at_utc": str(
            raw.get("last_material_event_at_utc") or ""
        ).strip(),
        "wait_timeout_seconds": int(raw.get("wait_timeout_seconds") or 0),
    }
    if status == "COMPLETE" and not out["terminal_evidence"]:
        raise ProgressTruthFailure("COMPLETE checkpoint requires terminal_evidence")
    if status == "BLOCKED":
        if not out["blocker_reason"] or not out["owner"]:
            raise ProgressTruthFailure("BLOCKED checkpoint requires blocker_reason and owner")
    if status == "WAITING":
        if out["wait_kind"] not in _WAIT_ROUTES:
            raise ProgressTruthFailure("WAITING checkpoint wait_kind unsupported")
        if out["wait_timeout_seconds"] <= 0:
            raise ProgressTruthFailure("WAITING checkpoint requires positive wait_timeout_seconds")
        entered = _utc(out["entered_wait_at_utc"])
        material = _utc(out["last_material_event_at_utc"])
        if material < entered:
            raise ProgressTruthFailure("last material event cannot predate wait entry")
        if not out["owner"]:
            raise ProgressTruthFailure("WAITING checkpoint requires owner")
    return out


def _normalize_plan(checkpoints: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(checkpoints, Sequence) or isinstance(checkpoints, (str, bytes)):
        raise ProgressTruthFailure("checkpoints must be a sequence")
    rows = [_normalize_checkpoint(row) for row in checkpoints]
    if not rows:
        raise ProgressTruthFailure("checkpoint plan cannot be empty")
    ids = [row["checkpoint_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ProgressTruthFailure("duplicate checkpoint_id")
    required = [row for row in rows if row["required"]]
    if sum(row["weight_bps"] for row in required) != 10000:
        raise ProgressTruthFailure("required checkpoint weights must total exactly 10000 bps")

    incomplete_seen = False
    for row in required:
        if row["status"] != "COMPLETE":
            incomplete_seen = True
        elif incomplete_seen:
            raise ProgressTruthFailure(
                "checkpoint order drift: later required checkpoint complete before earlier checkpoint"
            )
    return rows


def _display_percent(bps: int) -> str:
    whole = bps // 100
    frac = bps % 100
    return f"{whole}%" if frac == 0 else f"{whole}.{frac:02d}".rstrip("0") + "%"


def _base_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = [row for row in rows if row["required"]]
    completed = [row for row in required if row["status"] == "COMPLETE"]
    remaining = [row for row in required if row["status"] != "COMPLETE"]
    progress_bps = sum(row["weight_bps"] for row in completed)
    remaining_bps = 10000 - progress_bps
    next_row = remaining[0] if remaining else None
    complete = not remaining
    if complete != (progress_bps == 10000):
        raise ProgressTruthFailure("100 percent invariant violated")
    return {
        "progress_bps": progress_bps,
        "remaining_bps": remaining_bps,
        "progress_percent": progress_bps / 100.0,
        "progress_display": _display_percent(progress_bps),
        "complete": complete,
        "completed_checkpoint_ids": [row["checkpoint_id"] for row in completed],
        "remaining_checkpoint_ids": [row["checkpoint_id"] for row in remaining],
        "next_checkpoint_id": next_row["checkpoint_id"] if next_row else None,
        "next_checkpoint_label": next_row["label"] if next_row else None,
        "next_checkpoint_weight_bps": next_row["weight_bps"] if next_row else 0,
        "exact_remaining_display": _display_percent(remaining_bps),
        "high_progress_incomplete": bool(progress_bps >= 9900 and not complete),
    }


def _heartbeat_inspection(
    checkpoint: Mapping[str, Any],
    heartbeat_contexts: Mapping[str, Any],
    now_utc: str,
) -> dict[str, Any] | None:
    if checkpoint["wait_kind"] not in _ASYNC_WAIT_KINDS:
        return None
    raw = heartbeat_contexts.get(checkpoint["checkpoint_id"])
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ProgressTruthFailure("heartbeat context must be an object")
    return inspect_dead_man(
        raw["state"],
        workstream_id=_text(raw.get("workstream_id"), "heartbeat workstream_id"),
        continuation_packet_hash=_text(
            raw.get("continuation_packet_hash"),
            "continuation_packet_hash",
        ),
        now_utc=now_utc,
        observed_run_state=_text(
            raw.get("observed_run_state"),
            "observed_run_state",
        ),
    )


def _wait_truth(
    checkpoint: Mapping[str, Any],
    *,
    now_utc: str,
    heartbeat_contexts: Mapping[str, Any],
) -> dict[str, Any]:
    now = _utc(now_utc)
    last_event = _utc(checkpoint["last_material_event_at_utc"])
    if now < last_event:
        raise ProgressTruthFailure("now_utc cannot predate last material event")
    elapsed = int((now - last_event).total_seconds())
    timeout = int(checkpoint["wait_timeout_seconds"])
    overdue = elapsed > timeout
    route = _WAIT_ROUTES[checkpoint["wait_kind"]]

    if not overdue:
        return {
            "stuck": False,
            "classification": "WAIT_HEALTHY",
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout,
            "overdue_seconds": 0,
            "next_legal_action": "WAIT_FOR_MATERIAL_EVENT",
            "recovery_owner": checkpoint["owner"],
        }

    inspection = _heartbeat_inspection(
        checkpoint,
        heartbeat_contexts,
        now_utc,
    )
    if inspection is not None:
        decision = inspection["decision"]
        if decision == "WORKER_HEARTBEAT_LIVE":
            return {
                "stuck": False,
                "classification": "OVERDUE_BUT_HEARTBEAT_LIVE",
                "elapsed_seconds": elapsed,
                "timeout_seconds": timeout,
                "overdue_seconds": elapsed - timeout,
                "next_legal_action": inspection["next_legal_action"],
                "recovery_owner": "EXECUTION_HEARTBEAT_DEADMAN",
                "heartbeat_decision": decision,
            }
        if decision == "AUTHORITATIVE_RUN_STILL_ACTIVE":
            return {
                "stuck": False,
                "classification": "OVERDUE_BUT_AUTHORITATIVE_RUN_ACTIVE",
                "elapsed_seconds": elapsed,
                "timeout_seconds": timeout,
                "overdue_seconds": elapsed - timeout,
                "next_legal_action": inspection["next_legal_action"],
                "recovery_owner": "EXECUTION_HEARTBEAT_DEADMAN",
                "heartbeat_decision": decision,
            }
        if decision == "DEAD_MAN_RECOVERY_ELIGIBLE":
            return {
                "stuck": True,
                "classification": "DEAD_MAN_RECOVERY_ELIGIBLE",
                "elapsed_seconds": elapsed,
                "timeout_seconds": timeout,
                "overdue_seconds": elapsed - timeout,
                "next_legal_action": "ISSUE_DEAD_MAN_RECOVERY_RECEIPT",
                "recovery_owner": "EXECUTION_HEARTBEAT_DEADMAN",
                "heartbeat_decision": decision,
            }
        return {
            "stuck": True,
            "classification": "ASYNC_LIVENESS_UNPROVEN",
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout,
            "overdue_seconds": elapsed - timeout,
            "next_legal_action": inspection.get(
                "next_legal_action", "VERIFY_AUTHORITATIVE_RUN_STATE"
            ),
            "recovery_owner": "EXECUTION_HEARTBEAT_DEADMAN",
            "heartbeat_decision": decision,
        }

    if checkpoint["wait_kind"] in _ASYNC_WAIT_KINDS:
        route = "INSPECT_EXECUTION_HEARTBEAT"

    return {
        "stuck": True,
        "classification": "WAIT_DEADLINE_BREACHED",
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout,
        "overdue_seconds": elapsed - timeout,
        "next_legal_action": route,
        "recovery_owner": checkpoint["owner"],
    }


def evaluate_progress(
    detector_state: Mapping[str, Any],
    *,
    checkpoints: Sequence[Mapping[str, Any]],
    now_utc: str,
    heartbeat_contexts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = validate_state(detector_state)
    if HEARTBEAT_VERSION != REQUIRED_HEARTBEAT_VERSION:
        raise ProgressTruthFailure("heartbeat/dead-man version mismatch")
    if AUTOPILOT_VERSION != REQUIRED_AUTOPILOT_VERSION:
        raise ProgressTruthFailure("final-mile autopilot version mismatch")

    rows = _normalize_plan(checkpoints)
    report = _base_report(rows)
    report["version"] = VERSION
    report["required_checkpoint_count"] = len([r for r in rows if r["required"]])
    report["completed_checkpoint_count"] = len(report["completed_checkpoint_ids"])
    report["remaining_checkpoint_count"] = len(report["remaining_checkpoint_ids"])
    report["stuck"] = False
    report["blocker"] = None
    report["polling_required"] = False
    report["mutation_authority"] = False

    if report["complete"]:
        report.update({
            "decision": "PROGRESS_COMPLETE",
            "health": "GREEN",
            "next_legal_action": "NONE",
            "truth_statement": "ALL_REQUIRED_CHECKPOINTS_HAVE_TERMINAL_EVIDENCE",
        })
        return {"result": report, "state": state}

    next_row = next(
        row for row in rows
        if row["required"] and row["status"] != "COMPLETE"
    )
    report["active_checkpoint"] = {
        "checkpoint_id": next_row["checkpoint_id"],
        "label": next_row["label"],
        "status": next_row["status"],
        "owner": next_row["owner"],
        "weight_bps": next_row["weight_bps"],
    }
    report["truth_statement"] = (
        f"{report['exact_remaining_display']} remains at "
        f"{next_row['checkpoint_id']}: {next_row['label']}"
    )

    if next_row["status"] == "BLOCKED":
        report.update({
            "decision": "PROGRESS_BLOCKED",
            "health": "RED",
            "blocker": {
                "checkpoint_id": next_row["checkpoint_id"],
                "reason": next_row["blocker_reason"],
                "owner": next_row["owner"],
            },
            "next_legal_action": (
                next_row["next_action"]
                or "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"
            ),
        })
        return {"result": report, "state": state}

    if next_row["status"] == "PENDING":
        report.update({
            "decision": "PROGRESS_READY",
            "health": "YELLOW",
            "next_legal_action": next_row["next_action"] or "ADVANCE_CHECKPOINT",
        })
        return {"result": report, "state": state}

    if next_row["status"] != "WAITING":
        raise ProgressTruthFailure("unexpected incomplete checkpoint status")

    wait = _wait_truth(
        next_row,
        now_utc=now_utc,
        heartbeat_contexts=heartbeat_contexts or {},
    )
    report["wait_truth"] = wait

    if not wait["stuck"]:
        report.update({
            "decision": "PROGRESS_WAITING_HEALTHY",
            "health": "YELLOW",
            "next_legal_action": wait["next_legal_action"],
        })
        return {"result": report, "state": state}

    report["stuck"] = True
    fingerprint = _hash({
        "checkpoint_id": next_row["checkpoint_id"],
        "status": next_row["status"],
        "wait_kind": next_row["wait_kind"],
        "last_material_event_at_utc": next_row["last_material_event_at_utc"],
        "timeout_seconds": next_row["wait_timeout_seconds"],
        "classification": wait["classification"],
        "next_legal_action": wait["next_legal_action"],
    })
    report["stuck_fingerprint"] = fingerprint

    if fingerprint in state["issued_escalations"]:
        report.update({
            "decision": "STUCK_ESCALATION_SUPPRESSED_WAIT_FOR_EVENT",
            "health": "RED",
            "next_legal_action": "WAIT_FOR_MATERIAL_EVENT",
            "duplicate_escalation_suppressed": True,
            "previous_escalation_action": state["issued_escalations"][fingerprint],
        })
        return {"result": report, "state": state}

    updated = deepcopy(state)
    updated["revision"] += 1
    updated["issued_escalations"][fingerprint] = wait["next_legal_action"]
    updated = _rehash(updated)
    report.update({
        "decision": "STUCK_STATE_ESCALATION_ISSUED",
        "health": "RED",
        "next_legal_action": wait["next_legal_action"],
        "duplicate_escalation_suppressed": False,
        "escalation_owner": wait["recovery_owner"],
    })
    return {"result": report, "state": updated}


def contract_self_test() -> dict[str, Any]:
    state = new_state("monster-v7-self-test")
    base = [
        {
            "checkpoint_id": "A",
            "label": "Complete foundation",
            "required": True,
            "weight_bps": 9970,
            "status": "COMPLETE",
            "terminal_evidence": "receipt:A",
        },
        {
            "checkpoint_id": "B",
            "label": "Final freeze",
            "required": True,
            "weight_bps": 30,
            "status": "PENDING",
            "owner": "FROZEN_REGISTRY",
            "next_action": "REGISTER_FROZEN_CHECKPOINT",
        },
    ]
    near = evaluate_progress(
        state,
        checkpoints=base,
        now_utc="2026-10-02T02:00:00Z",
    )

    complete = deepcopy(base)
    complete[1] = {
        **complete[1],
        "status": "COMPLETE",
        "terminal_evidence": "receipt:B",
        "owner": "",
        "next_action": "",
    }
    done = evaluate_progress(
        state,
        checkpoints=complete,
        now_utc="2026-10-02T02:00:00Z",
    )

    waiting = deepcopy(base)
    waiting[1] = {
        **waiting[1],
        "status": "WAITING",
        "wait_kind": "FREEZE_REGISTRY_EVENT",
        "entered_wait_at_utc": "2026-10-02T01:58:00Z",
        "last_material_event_at_utc": "2026-10-02T01:59:30Z",
        "wait_timeout_seconds": 120,
        "owner": "FROZEN_REGISTRY",
    }
    healthy = evaluate_progress(
        state,
        checkpoints=waiting,
        now_utc="2026-10-02T02:00:00Z",
    )
    stuck = evaluate_progress(
        state,
        checkpoints=waiting,
        now_utc="2026-10-02T02:02:00Z",
    )
    duplicate = evaluate_progress(
        stuck["state"],
        checkpoints=waiting,
        now_utc="2026-10-02T02:03:00Z",
    )

    hb0 = new_heartbeat_state("owner/repo")
    hb = register_worker(
        hb0,
        workstream_id="proof",
        owner_id="worker-a",
        scope_lease_id="LEASE-A",
        continuation_packet_hash="a" * 64,
        authoritative_run_id=44,
        now_utc="2026-10-02T01:00:00Z",
        expected_revision=hb0["revision"],
        expected_state_hash=hb0["state_hash"],
        heartbeat_ttl_seconds=60,
    )["state"]
    async_wait = deepcopy(base)
    async_wait[1] = {
        **async_wait[1],
        "status": "WAITING",
        "wait_kind": "EXACT_HEAD_PROOF",
        "entered_wait_at_utc": "2026-10-02T01:00:00Z",
        "last_material_event_at_utc": "2026-10-02T01:00:00Z",
        "wait_timeout_seconds": 60,
        "owner": "AUTHORITATIVE_PROOF",
    }
    dead = evaluate_progress(
        state,
        checkpoints=async_wait,
        now_utc="2026-10-02T01:05:00Z",
        heartbeat_contexts={
            "B": {
                "state": hb,
                "workstream_id": "proof",
                "continuation_packet_hash": "a" * 64,
                "observed_run_state": "completed",
            }
        },
    )
    live = evaluate_progress(
        state,
        checkpoints=async_wait,
        now_utc="2026-10-02T01:05:00Z",
        heartbeat_contexts={
            "B": {
                "state": hb,
                "workstream_id": "proof",
                "continuation_packet_hash": "a" * 64,
                "observed_run_state": "in_progress",
            }
        },
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "heartbeat_version_bound": HEARTBEAT_VERSION == REQUIRED_HEARTBEAT_VERSION,
        "autopilot_version_bound": AUTOPILOT_VERSION == REQUIRED_AUTOPILOT_VERSION,
        "near_complete_is_exactly_99_7": near["result"]["progress_bps"] == 9970,
        "near_complete_never_rounds_to_100": near["result"]["progress_display"] == "99.7%",
        "remainder_is_named": (
            near["result"]["exact_remaining_display"] == "0.3%"
            and near["result"]["next_checkpoint_id"] == "B"
            and "Final freeze" in near["result"]["truth_statement"]
        ),
        "hundred_requires_all_terminal_evidence": (
            done["result"]["progress_bps"] == 10000
            and done["result"]["decision"] == "PROGRESS_COMPLETE"
        ),
        "fresh_material_event_resets_wait": (
            healthy["result"]["decision"] == "PROGRESS_WAITING_HEALTHY"
        ),
        "overdue_wait_escalates_once": (
            stuck["result"]["decision"] == "STUCK_STATE_ESCALATION_ISSUED"
            and stuck["result"]["next_legal_action"] == "VERIFY_FROZEN_REGISTRY"
        ),
        "duplicate_escalation_suppressed": (
            duplicate["result"]["decision"]
            == "STUCK_ESCALATION_SUPPRESSED_WAIT_FOR_EVENT"
        ),
        "dead_man_routes_recovery": (
            dead["result"]["wait_truth"]["classification"]
            == "DEAD_MAN_RECOVERY_ELIGIBLE"
            and dead["result"]["next_legal_action"]
            == "ISSUE_DEAD_MAN_RECOVERY_RECEIPT"
        ),
        "active_run_not_misclassified_stuck": (
            live["result"]["decision"] == "PROGRESS_WAITING_HEALTHY"
            and live["result"]["wait_truth"]["classification"]
            == "OVERDUE_BUT_AUTHORITATIVE_RUN_ACTIVE"
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "heartbeat_version_bound",
        "autopilot_version_bound",
        "near_complete_is_exactly_99_7",
        "near_complete_never_rounds_to_100",
        "remainder_is_named",
        "hundred_requires_all_terminal_evidence",
        "fresh_material_event_resets_wait",
        "overdue_wait_escalates_once",
        "duplicate_escalation_suppressed",
        "dead_man_routes_recovery",
        "active_run_not_misclassified_stuck",
    ]
    if not all(result[name] is True for name in required):
        raise ProgressTruthFailure("progress truth self-test failed")
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise ProgressTruthFailure("pure detector safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP7_PROGRESS_TRUTH_STUCK_DETECTOR_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProgressTruthFailure as exc:
        print(
            "MONSTER_V7_STEP7_PROGRESS_TRUTH_STUCK_DETECTOR_BLOCKED: "
            + str(exc)
        )
        raise SystemExit(1)
