"""MONSTER V7 Step 3 — Monotonic State Ownership Guard V1.

Prevents older/upstream writers from overwriting newer downstream state.

Ownership is represented by a monotonic tuple:
    ownership_epoch -> authority_rank -> generation

A write must observe the exact current generation/owner, point at the exact
current write event, and either:
- continue under the same owner/epoch without lowering authority; or
- perform exactly one forward ownership handoff with non-decreasing authority.

Older epochs, lower authority, stale generations, ambiguous same-epoch owner
changes, skipped epochs, and forged handoffs fail closed before mutation.

This module is a pure decision engine. It performs no network calls and grants
no mutation authority.
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.causal_state_lineage_graph_v1 import VERSION as LINEAGE_VERSION
from devsystem.automatic_root_cause_backtrace_v1 import VERSION as BACKTRACE_VERSION

VERSION = "MONSTER_V7_MONOTONIC_STATE_OWNERSHIP_GUARD_V1"
STEP1_REQUIRED_VERSION = "MONSTER_V7_CAUSAL_STATE_LINEAGE_GRAPH_V1"
STEP2_REQUIRED_VERSION = "MONSTER_V7_AUTOMATIC_ROOT_CAUSE_BACKTRACE_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class MonotonicStateOwnershipFailure(RuntimeError):
    pass


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise MonotonicStateOwnershipFailure(f"{field} is required")
    return out


def _positive_int(value: Any, field: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise MonotonicStateOwnershipFailure(f"{field} must be an integer") from exc
    if out <= 0:
        raise MonotonicStateOwnershipFailure(f"{field} must be positive")
    return out


def _nonnegative_int(value: Any, field: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise MonotonicStateOwnershipFailure(f"{field} must be an integer") from exc
    if out < 0:
        raise MonotonicStateOwnershipFailure(f"{field} cannot be negative")
    return out


def _digest(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _DIGEST.fullmatch(out):
        raise MonotonicStateOwnershipFailure(
            f"{field} must be sha256:<64 lowercase hex>"
        )
    return out


def normalize_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise MonotonicStateOwnershipFailure("state must be an object")
    out = deepcopy(dict(raw))
    out["field"] = _text(out.get("field"), "field")
    out["owner_id"] = _text(out.get("owner_id"), "owner_id")
    out["ownership_epoch"] = _positive_int(
        out.get("ownership_epoch"), "ownership_epoch"
    )
    out["authority_rank"] = _nonnegative_int(
        out.get("authority_rank"), "authority_rank"
    )
    out["generation"] = _positive_int(out.get("generation"), "generation")
    out["last_write_event_id"] = _text(
        out.get("last_write_event_id"), "last_write_event_id"
    )
    out["value_digest"] = _digest(out.get("value_digest"), "value_digest")
    return out


def normalize_request(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise MonotonicStateOwnershipFailure("write request must be an object")
    out = deepcopy(dict(raw))
    out["request_id"] = _text(out.get("request_id"), "request_id")
    out["field"] = _text(out.get("field"), "field")
    out["writer_id"] = _text(out.get("writer_id"), "writer_id")
    out["writer_epoch"] = _positive_int(out.get("writer_epoch"), "writer_epoch")
    out["writer_authority_rank"] = _nonnegative_int(
        out.get("writer_authority_rank"), "writer_authority_rank"
    )
    out["expected_generation"] = _positive_int(
        out.get("expected_generation"), "expected_generation"
    )
    out["observed_owner_id"] = _text(
        out.get("observed_owner_id"), "observed_owner_id"
    )
    out["observed_owner_epoch"] = _positive_int(
        out.get("observed_owner_epoch"), "observed_owner_epoch"
    )
    out["parent_write_event_id"] = _text(
        out.get("parent_write_event_id"), "parent_write_event_id"
    )
    out["write_event_id"] = _text(out.get("write_event_id"), "write_event_id")
    out["proposed_value_digest"] = _digest(
        out.get("proposed_value_digest"), "proposed_value_digest"
    )
    out["handoff_from_owner_id"] = str(
        out.get("handoff_from_owner_id") or ""
    ).strip()
    out["handoff_from_event_id"] = str(
        out.get("handoff_from_event_id") or ""
    ).strip()
    return out


def _blocked(
    *,
    state: Mapping[str, Any],
    request: Mapping[str, Any],
    reason: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "decision": "WRITE_BLOCKED",
        "allowed": False,
        "reason": reason,
        "detail": detail,
        "field": state["field"],
        "current_owner_id": state["owner_id"],
        "current_ownership_epoch": state["ownership_epoch"],
        "current_authority_rank": state["authority_rank"],
        "current_generation": state["generation"],
        "requested_writer_id": request["writer_id"],
        "requested_writer_epoch": request["writer_epoch"],
        "requested_authority_rank": request["writer_authority_rank"],
        "expected_generation": request["expected_generation"],
        "backtrace_trigger": {
            "version": BACKTRACE_VERSION,
            "trigger": "STATE_REGRESSION",
            "field": state["field"],
            "target_event_id": state["last_write_event_id"],
        },
        "next_legal_action": "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE",
        "mutation_authority": False,
    }


def evaluate_write(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    current = normalize_state(state)
    candidate = normalize_request(request)

    if LINEAGE_VERSION != STEP1_REQUIRED_VERSION:
        raise MonotonicStateOwnershipFailure("Step-1 lineage version mismatch")
    if BACKTRACE_VERSION != STEP2_REQUIRED_VERSION:
        raise MonotonicStateOwnershipFailure("Step-2 backtrace version mismatch")

    if candidate["field"] != current["field"]:
        raise MonotonicStateOwnershipFailure("request field/state field mismatch")

    if candidate["expected_generation"] != current["generation"]:
        return _blocked(
            state=current,
            request=candidate,
            reason="STALE_GENERATION",
            detail="writer did not observe the current generation",
        )

    if (
        candidate["observed_owner_id"] != current["owner_id"]
        or candidate["observed_owner_epoch"] != current["ownership_epoch"]
    ):
        return _blocked(
            state=current,
            request=candidate,
            reason="STALE_OWNER_SNAPSHOT",
            detail="writer did not observe the current owner identity and epoch",
        )

    if candidate["parent_write_event_id"] != current["last_write_event_id"]:
        return _blocked(
            state=current,
            request=candidate,
            reason="STALE_PARENT_WRITE",
            detail="writer is not based on the current last-write event",
        )

    if candidate["writer_epoch"] < current["ownership_epoch"]:
        return _blocked(
            state=current,
            request=candidate,
            reason="STALE_OWNERSHIP_EPOCH",
            detail="older ownership epoch may not overwrite newer state",
        )

    if candidate["writer_epoch"] == current["ownership_epoch"]:
        if candidate["writer_id"] != current["owner_id"]:
            return _blocked(
                state=current,
                request=candidate,
                reason="SAME_EPOCH_OWNER_CHANGE",
                detail="ownership may not change identities inside the same epoch",
            )
        if candidate["writer_authority_rank"] < current["authority_rank"]:
            return _blocked(
                state=current,
                request=candidate,
                reason="LOWER_AUTHORITY_RANK",
                detail="authority rank may not move backward",
            )
        transition = "SAME_OWNER_FORWARD_WRITE"
    else:
        if candidate["writer_epoch"] != current["ownership_epoch"] + 1:
            return _blocked(
                state=current,
                request=candidate,
                reason="OWNERSHIP_EPOCH_GAP",
                detail="ownership handoff must advance exactly one epoch",
            )
        if candidate["writer_authority_rank"] < current["authority_rank"]:
            return _blocked(
                state=current,
                request=candidate,
                reason="LOWER_AUTHORITY_RANK",
                detail="new owner may not lower authority rank",
            )
        if (
            candidate["handoff_from_owner_id"] != current["owner_id"]
            or candidate["handoff_from_event_id"] != current["last_write_event_id"]
        ):
            return _blocked(
                state=current,
                request=candidate,
                reason="UNPROVEN_OWNERSHIP_HANDOFF",
                detail="forward ownership requires an exact handoff from current owner/event",
            )
        transition = "FORWARD_OWNERSHIP_HANDOFF"

    next_state = {
        "field": current["field"],
        "owner_id": candidate["writer_id"],
        "ownership_epoch": candidate["writer_epoch"],
        "authority_rank": candidate["writer_authority_rank"],
        "generation": current["generation"] + 1,
        "last_write_event_id": candidate["write_event_id"],
        "value_digest": candidate["proposed_value_digest"],
    }
    return {
        "version": VERSION,
        "decision": "WRITE_ALLOWED",
        "allowed": True,
        "reason": "MONOTONIC_OWNERSHIP_PRESERVED",
        "transition": transition,
        "previous_state": current,
        "next_state": next_state,
        "ownership_tuple_before": [
            current["ownership_epoch"],
            current["authority_rank"],
            current["generation"],
        ],
        "ownership_tuple_after": [
            next_state["ownership_epoch"],
            next_state["authority_rank"],
            next_state["generation"],
        ],
        "next_legal_action": "APPLY_WRITE_UNDER_STEP_2A",
        "mutation_authority": False,
    }


def contract_self_test() -> dict[str, Any]:
    good = "sha256:" + "1" * 64
    newer = "sha256:" + "2" * 64
    state = {
        "field": "market.selection",
        "owner_id": "STEP_9",
        "ownership_epoch": 9,
        "authority_rank": 90,
        "generation": 4,
        "last_write_event_id": "step9-write-v9",
        "value_digest": good,
    }

    same_owner = evaluate_write(
        state,
        {
            "request_id": "same-owner",
            "field": "market.selection",
            "writer_id": "STEP_9",
            "writer_epoch": 9,
            "writer_authority_rank": 90,
            "expected_generation": 4,
            "observed_owner_id": "STEP_9",
            "observed_owner_epoch": 9,
            "parent_write_event_id": "step9-write-v9",
            "write_event_id": "step9-write-v10",
            "proposed_value_digest": newer,
        },
    )

    old_step = evaluate_write(
        state,
        {
            "request_id": "old-step",
            "field": "market.selection",
            "writer_id": "STEP_6",
            "writer_epoch": 6,
            "writer_authority_rank": 60,
            "expected_generation": 4,
            "observed_owner_id": "STEP_9",
            "observed_owner_epoch": 9,
            "parent_write_event_id": "step9-write-v9",
            "write_event_id": "step6-overwrite",
            "proposed_value_digest": newer,
        },
    )

    stale_generation = evaluate_write(
        state,
        {
            "request_id": "stale-gen",
            "field": "market.selection",
            "writer_id": "STEP_9",
            "writer_epoch": 9,
            "writer_authority_rank": 90,
            "expected_generation": 3,
            "observed_owner_id": "STEP_9",
            "observed_owner_epoch": 9,
            "parent_write_event_id": "step9-write-v9",
            "write_event_id": "stale",
            "proposed_value_digest": newer,
        },
    )

    valid_handoff = evaluate_write(
        state,
        {
            "request_id": "handoff",
            "field": "market.selection",
            "writer_id": "FINAL_CERT",
            "writer_epoch": 10,
            "writer_authority_rank": 100,
            "expected_generation": 4,
            "observed_owner_id": "STEP_9",
            "observed_owner_epoch": 9,
            "parent_write_event_id": "step9-write-v9",
            "write_event_id": "final-write",
            "proposed_value_digest": newer,
            "handoff_from_owner_id": "STEP_9",
            "handoff_from_event_id": "step9-write-v9",
        },
    )

    forged_handoff = deepcopy(valid_handoff["previous_state"])
    forged_request = {
        "request_id": "forged",
        "field": "market.selection",
        "writer_id": "FINAL_CERT",
        "writer_epoch": 10,
        "writer_authority_rank": 100,
        "expected_generation": 4,
        "observed_owner_id": "STEP_9",
        "observed_owner_epoch": 9,
        "parent_write_event_id": "step9-write-v9",
        "write_event_id": "forged-write",
        "proposed_value_digest": newer,
        "handoff_from_owner_id": "STEP_7",
        "handoff_from_event_id": "step7-old",
    }
    forged = evaluate_write(forged_handoff, forged_request)

    lower_authority = evaluate_write(
        state,
        {
            "request_id": "lower-authority",
            "field": "market.selection",
            "writer_id": "FINAL_CERT",
            "writer_epoch": 10,
            "writer_authority_rank": 80,
            "expected_generation": 4,
            "observed_owner_id": "STEP_9",
            "observed_owner_epoch": 9,
            "parent_write_event_id": "step9-write-v9",
            "write_event_id": "low-rank",
            "proposed_value_digest": newer,
            "handoff_from_owner_id": "STEP_9",
            "handoff_from_event_id": "step9-write-v9",
        },
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "step1_version_bound": LINEAGE_VERSION == STEP1_REQUIRED_VERSION,
        "step2_version_bound": BACKTRACE_VERSION == STEP2_REQUIRED_VERSION,
        "same_owner_forward_write_allowed": same_owner["allowed"] is True,
        "older_upstream_writer_blocked": (
            old_step["allowed"] is False
            and old_step["reason"] == "STALE_OWNERSHIP_EPOCH"
        ),
        "stale_generation_blocked": (
            stale_generation["allowed"] is False
            and stale_generation["reason"] == "STALE_GENERATION"
        ),
        "valid_forward_handoff_allowed": (
            valid_handoff["allowed"] is True
            and valid_handoff["transition"] == "FORWARD_OWNERSHIP_HANDOFF"
        ),
        "forged_handoff_blocked": (
            forged["allowed"] is False
            and forged["reason"] == "UNPROVEN_OWNERSHIP_HANDOFF"
        ),
        "lower_authority_blocked": (
            lower_authority["allowed"] is False
            and lower_authority["reason"] == "LOWER_AUTHORITY_RANK"
        ),
        "generation_advances_exactly_one": (
            same_owner["next_state"]["generation"] == state["generation"] + 1
        ),
        "blocked_write_routes_to_backtrace": (
            old_step["next_legal_action"] == "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"
            and old_step["backtrace_trigger"]["version"] == BACKTRACE_VERSION
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = (
        "step1_version_bound",
        "step2_version_bound",
        "same_owner_forward_write_allowed",
        "older_upstream_writer_blocked",
        "stale_generation_blocked",
        "valid_forward_handoff_allowed",
        "forged_handoff_blocked",
        "lower_authority_blocked",
        "generation_advances_exactly_one",
        "blocked_write_routes_to_backtrace",
    )
    if not all(result[name] is True for name in required):
        raise MonotonicStateOwnershipFailure(
            "monotonic state ownership self-test failed"
        )
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise MonotonicStateOwnershipFailure("read-only safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP3_MONOTONIC_STATE_OWNERSHIP_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MonotonicStateOwnershipFailure as exc:
        print(f"MONSTER_V7_STEP3_MONOTONIC_STATE_OWNERSHIP_BLOCKED: {exc}")
        raise SystemExit(1)
