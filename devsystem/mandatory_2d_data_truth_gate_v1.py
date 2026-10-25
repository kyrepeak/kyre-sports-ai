"""MONSTER Step 2D — Data Truth + Zero-False-Blank Gate V1.

Read-only post-execution verifier. Step 2D proves that field truth survives the
MONSTER authoritative path and fails closed when a technical failure is masked
as absence, a missing value is fabricated, a fallback is not field-specific,
a technical failure is negative-cached, or source/authoritative/final truth
diverges.

Step 2D performs no network calls and no product/runtime mutation. A failure
emits deterministic MONSTER-owned evidence and routes back through Anti-Loop
and Step 2C before another Step 2B/Step 2A repair may be authorized.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from devsystem.monster_system_isolation_v1 import (
    MonsterSystemIsolationFailure,
    assert_monster_only,
)

VERSION = "MONSTER_STEP2D_DATA_TRUTH_ZERO_FALSE_BLANK_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

STAGE_ORDER = (
    "source",
    "ingestion",
    "parser",
    "identification_mapping",
    "normalization",
    "monster_authoritative",
    "consumer",
    "final_output",
)

TECHNICAL_FAILURE_STATES = frozenset({
    "PROVIDER_FETCH_FAILURE",
    "PARSER_FAILURE",
    "EVENT_MAPPING_FAILURE",
    "ENTITY_MAPPING_FAILURE",
    "MARKET_MAPPING_FAILURE",
    "STALE_DATA",
    "SOURCE_CONFLICT",
    "ALL_SOURCES_UNAVAILABLE",
})

ABSENCE_STATES = frozenset({
    "NOT_FOUND",
    "NOT_AVAILABLE",
    "MARKET_NOT_POSTED",
    "LINE_PENDING",
    "BLANK",
    "EMPTY",
    "MISSING",
})

SUCCESS_STATES = frozenset({"SUCCESS", "VALUE_PRESENT", "VERIFIED_ABSENT"})
RECOVERY_SEQUENCE = (
    "ANTI_LOOP",
    "STEP_2C",
    "STEP_2B",
    "STEP_2A",
    "EXECUTE",
    "STEP_2D",
)
_MISSING = object()


class Mandatory2DDataTruthFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(dict(value)).encode("utf-8")).hexdigest()


def _truth_token(value: Any) -> tuple[str, str]:
    if isinstance(value, bool):
        return ("bool", "true" if value else "false")
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        try:
            number = Decimal(str(value))
            if number.is_finite():
                if number == 0:
                    number = Decimal(0)
                return ("number", format(number.normalize(), "f"))
        except (InvalidOperation, ValueError):
            pass
    return ("json", _canonical(value))


def _stage_truth(stage: Mapping[str, Any]) -> Any:
    if "truth_value" in stage:
        return stage["truth_value"]
    if "value" in stage:
        return stage["value"]
    return _MISSING


def _classification(failure_kind: str, preserved_state: str | None) -> str:
    if preserved_state == "PARSER_FAILURE":
        return "parser"
    if preserved_state in {"EVENT_MAPPING_FAILURE", "ENTITY_MAPPING_FAILURE", "MARKET_MAPPING_FAILURE"}:
        return "canonical-id"
    if preserved_state == "STALE_DATA":
        return "caching/state"
    if preserved_state in {"PROVIDER_FETCH_FAILURE", "SOURCE_CONFLICT", "ALL_SOURCES_UNAVAILABLE"}:
        return "provider/data"
    if failure_kind == "FALLBACK_POLICY_FAILURE":
        return "architecture"
    return "verification/test"


def _blocked(
    *,
    trace: Mapping[str, Any] | None,
    failure_kind: str,
    reason: str,
    failed_stage: str | None = None,
    preserved_failure_state: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    identity = {
        "task_id": str((trace or {}).get("task_id") or "monster-step2d"),
        "execution_id": str((trace or {}).get("execution_id") or "unknown-execution"),
        "field_id": str((trace or {}).get("field_id") or "global"),
        "failure_kind": failure_kind,
        "failed_stage": failed_stage,
        "preserved_failure_state": preserved_failure_state,
        "reason": reason,
        "detail": detail or "",
    }
    fingerprint = _fingerprint(identity)
    candidate = {
        "fingerprint": fingerprint,
        "source": "monster-step2d-data-truth-v1",
        "summary": f"{identity['field_id']}: {failure_kind}: {reason}",
        "material": True,
    }
    return {
        "status": "BLOCKED",
        "version": VERSION,
        "decision": "STEP_2D_REJECTED",
        "monster_only": True,
        "step2d_enforced": True,
        "failure_kind": failure_kind,
        "reason": reason,
        "failed_stage": failed_stage,
        "preserved_failure_state": preserved_failure_state,
        "detail": detail,
        "failure_fingerprint": fingerprint,
        "step2c_evidence_candidate": candidate,
        "final_verification_authorized": False,
        "negative_cache_allowed": False,
        "requires_user_intervention": False,
        "next_legal_action": "RETURN_TO_MONSTER_STEP_2C",
        "recovery_sequence": list(RECOVERY_SEQUENCE),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _validate_fallback(trace: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw = trace.get("fallback")
    if raw is None:
        return ({"fallback_verified": False, "primary_failure_state": None}, None)
    if not isinstance(raw, Mapping):
        return (None, _blocked(trace=trace, failure_kind="FALLBACK_POLICY_FAILURE", reason="fallback evidence must be an object"))
    if raw.get("used") is not True:
        return ({"fallback_verified": False, "primary_failure_state": None}, None)

    primary = str(raw.get("primary_failure_state") or "").strip()
    selected = str(raw.get("selected_source") or "").strip()
    approved_sources = raw.get("approved_sources")
    reason = str(raw.get("selection_reason") or "").strip()
    approved_list = list(approved_sources) if isinstance(approved_sources, Sequence) and not isinstance(approved_sources, (str, bytes, bytearray)) else []

    valid = (
        primary in TECHNICAL_FAILURE_STATES
        and raw.get("field_specific") is True
        and raw.get("approved") is True
        and raw.get("blind_fanout") is False
        and bool(selected)
        and selected in approved_list
        and bool(reason)
    )
    if not valid:
        return (
            None,
            _blocked(
                trace=trace,
                failure_kind="FALLBACK_POLICY_FAILURE",
                reason="fallback must be field-specific, approved, selected from the approved set, reasoned, and non-blind",
                preserved_failure_state=primary or None,
            ),
        )
    return ({"fallback_verified": True, "primary_failure_state": primary}, None)


def _evaluate_field(trace: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(trace, Mapping):
        return _blocked(trace=None, failure_kind="INVALID_EVIDENCE", reason="field trace must be an object")

    field_id = str(trace.get("field_id") or "").strip()
    if not field_id:
        return _blocked(trace=trace, failure_kind="INVALID_EVIDENCE", reason="field_id is required")

    stages = trace.get("stages")
    if not isinstance(stages, Mapping):
        return _blocked(trace=trace, failure_kind="INVALID_EVIDENCE", reason="stages are required")
    for name in STAGE_ORDER:
        if not isinstance(stages.get(name), Mapping):
            return _blocked(trace=trace, failure_kind="INVALID_EVIDENCE", reason=f"missing stage evidence: {name}", failed_stage=name)

    fallback_info, fallback_failure = _validate_fallback(trace)
    if fallback_failure is not None:
        return fallback_failure
    assert fallback_info is not None

    technical: list[tuple[int, str, str, Mapping[str, Any]]] = []
    for index, name in enumerate(STAGE_ORDER):
        stage = stages[name]
        state = str(stage.get("state") or "").strip()
        if state in TECHNICAL_FAILURE_STATES:
            technical.append((index, name, state, stage))

    primary_failure = fallback_info.get("primary_failure_state")
    technical_failure_present = bool(technical) or primary_failure in TECHNICAL_FAILURE_STATES
    if trace.get("negative_cache_written") is True and technical_failure_present:
        preserved = technical[0][2] if technical else str(primary_failure)
        failed_stage = technical[0][1] if technical else "source"
        return _blocked(
            trace=trace,
            failure_kind="NEGATIVE_CACHE_TECHNICAL_FAILURE",
            reason="technical failure cannot be written as a negative-cache absence",
            failed_stage=failed_stage,
            preserved_failure_state=preserved,
        )

    if technical:
        index, name, state, stage = technical[0]
        downstream_value = False
        for later_name in STAGE_ORDER[index + 1 :]:
            later = stages[later_name]
            if str(later.get("state") or "") == "VALUE_PRESENT" and _stage_truth(later) is not _MISSING:
                downstream_value = True
                break
        return _blocked(
            trace=trace,
            failure_kind="FABRICATED_VALUE" if downstream_value else "TECHNICAL_FAILURE",
            reason="technical failure must remain explicit and cannot become absence or invented downstream truth",
            failed_stage=name,
            preserved_failure_state=state,
            detail=str(stage.get("detail") or "") or None,
        )

    for name in STAGE_ORDER:
        state = str(stages[name].get("state") or "").strip()
        if state and state not in SUCCESS_STATES and state not in ABSENCE_STATES:
            return _blocked(
                trace=trace,
                failure_kind="INVALID_EVIDENCE",
                reason=f"unknown Step 2D state: {state}",
                failed_stage=name,
                preserved_failure_state=state,
            )

    source = stages["source"]
    source_state = str(source.get("state") or "").strip()
    source_truth = _stage_truth(source)

    for name in STAGE_ORDER:
        state = str(stages[name].get("state") or "").strip()
        if state in ABSENCE_STATES:
            if source_state == "VALUE_PRESENT" and source_truth is not _MISSING and name != "source":
                return _blocked(
                    trace=trace,
                    failure_kind="FALSE_BLANK",
                    reason="verified source value was converted into an absence/blank state",
                    failed_stage=name,
                    preserved_failure_state=state,
                )
            return _blocked(
                trace=trace,
                failure_kind="UNVERIFIED_ABSENCE",
                reason="absence state is not proof that the requested information is genuinely absent",
                failed_stage=name,
                preserved_failure_state=state,
            )

    final_state = str(stages["final_output"].get("state") or "").strip()
    if final_state == "VERIFIED_ABSENT":
        proof = trace.get("absence_proof")
        proof_ok = (
            isinstance(proof, Mapping)
            and proof.get("source_path_succeeded") is True
            and proof.get("requested_field_checked") is True
            and proof.get("genuinely_absent") is True
            and bool(str(proof.get("evidence_fingerprint") or "").strip())
        )
        prior_success = all(str(stages[name].get("state") or "") == "SUCCESS" for name in STAGE_ORDER[:-1])
        any_value = any(_stage_truth(stages[name]) is not _MISSING for name in STAGE_ORDER)
        if not proof_ok or not prior_success or any_value:
            return _blocked(
                trace=trace,
                failure_kind="UNVERIFIED_ABSENCE",
                reason="verified absence requires a successful path, explicit requested-field check, genuine-absence assertion, and evidence fingerprint",
                failed_stage="final_output",
                preserved_failure_state="VERIFIED_ABSENT",
            )
        return {
            "status": "GREEN",
            "field_id": field_id,
            "absence_verified": True,
            "verified_truth_value": None,
            "fallback_verified": bool(fallback_info["fallback_verified"]),
            "primary_failure_state": fallback_info["primary_failure_state"],
            "negative_cache_allowed": True,
        }

    downstream_values = [
        name
        for name in STAGE_ORDER[1:]
        if str(stages[name].get("state") or "") == "VALUE_PRESENT" and _stage_truth(stages[name]) is not _MISSING
    ]
    if source_state != "VALUE_PRESENT" or source_truth is _MISSING:
        if downstream_values:
            return _blocked(
                trace=trace,
                failure_kind="FABRICATED_VALUE",
                reason="downstream value exists without a verified source value",
                failed_stage=downstream_values[0],
            )
        return _blocked(
            trace=trace,
            failure_kind="UNPROVEN_DATA_STATE",
            reason="field is neither a verified value nor a verified absence",
            failed_stage="source",
        )

    source_token = _truth_token(source_truth)
    for name in STAGE_ORDER[1:]:
        stage = stages[name]
        truth = _stage_truth(stage)
        if truth is not _MISSING and _truth_token(truth) != source_token:
            return _blocked(
                trace=trace,
                failure_kind="VALUE_MISMATCH",
                reason="field truth changed between source and MONSTER path",
                failed_stage=name,
                detail=f"source={source_token!r} stage={_truth_token(truth)!r}",
            )

    authoritative_truth = _stage_truth(stages["monster_authoritative"])
    final_truth = _stage_truth(stages["final_output"])
    if authoritative_truth is _MISSING:
        return _blocked(
            trace=trace,
            failure_kind="FALSE_BLANK",
            reason="source value did not survive to the MONSTER authoritative value",
            failed_stage="monster_authoritative",
        )
    if final_truth is _MISSING:
        return _blocked(
            trace=trace,
            failure_kind="FALSE_BLANK",
            reason="MONSTER authoritative value did not survive to final output",
            failed_stage="final_output",
        )

    if _truth_token(authoritative_truth) != source_token or _truth_token(final_truth) != source_token:
        return _blocked(
            trace=trace,
            failure_kind="VALUE_MISMATCH",
            reason="source, MONSTER authoritative, and final consumer truth do not match",
            failed_stage="final_output",
        )

    return {
        "status": "GREEN",
        "field_id": field_id,
        "absence_verified": False,
        "verified_truth_value": source_truth,
        "fallback_verified": bool(fallback_info["fallback_verified"]),
        "primary_failure_state": fallback_info["primary_failure_state"],
        "negative_cache_allowed": True,
    }


def verify_post_execution(
    execution_receipt: Mapping[str, Any],
    field_traces: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run Step 2D after execution and before final verification authorization."""
    try:
        assert_monster_only({"execution_receipt": execution_receipt, "field_traces": field_traces})
    except MonsterSystemIsolationFailure:
        return {
            "status": "BLOCKED",
            "version": VERSION,
            "decision": "STEP_2D_REJECTED",
            "monster_only": True,
            "step2d_enforced": True,
            "failure_kind": "FOREIGN_STATE_REJECTED",
            "reason": "MONSTER Step 2D rejected foreign runtime state before consuming it as evidence",
            "preserved_failure_state": None,
            "failure_fingerprint": _fingerprint({"failure_kind": "FOREIGN_STATE_REJECTED", "version": VERSION}),
            "step2c_evidence_candidate": None,
            "final_verification_authorized": False,
            "negative_cache_allowed": False,
            "requires_user_intervention": False,
            "next_legal_action": "DISCARD_FOREIGN_STATE_AND_GATHER_MONSTER_EVIDENCE",
            "recovery_sequence": list(RECOVERY_SEQUENCE),
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        }

    if not isinstance(execution_receipt, Mapping):
        return _blocked(trace=None, failure_kind="INVALID_EVIDENCE", reason="execution receipt must be an object")
    if execution_receipt.get("completed") is not True or str(execution_receipt.get("status") or "") != "SUCCESS":
        return _blocked(trace=execution_receipt, failure_kind="EXECUTION_NOT_COMPLETE", reason="Step 2D runs only after successful execution")
    if execution_receipt.get("monster_only") is not True:
        return _blocked(trace=execution_receipt, failure_kind="EXECUTION_NOT_MONSTER_AUTHORIZED", reason="execution receipt is not MONSTER-owned")
    if not isinstance(field_traces, Sequence) or isinstance(field_traces, (str, bytes, bytearray)) or not field_traces:
        return _blocked(trace=execution_receipt, failure_kind="INVALID_EVIDENCE", reason="at least one field trace is required")

    receipt_task = str(execution_receipt.get("task_id") or "")
    receipt_execution = str(execution_receipt.get("execution_id") or "")
    receipt_path = execution_receipt.get("authoritative_path")
    if not receipt_task or not receipt_execution or not isinstance(receipt_path, Mapping):
        return _blocked(trace=execution_receipt, failure_kind="INVALID_EVIDENCE", reason="execution receipt identity and authoritative path are required")

    verified: list[dict[str, Any]] = []
    for raw_trace in field_traces:
        if not isinstance(raw_trace, Mapping):
            return _blocked(trace=None, failure_kind="INVALID_EVIDENCE", reason="field trace must be an object")
        if (
            str(raw_trace.get("task_id") or "") != receipt_task
            or str(raw_trace.get("execution_id") or "") != receipt_execution
            or dict(raw_trace.get("authoritative_path") or {}) != dict(receipt_path)
        ):
            return _blocked(trace=raw_trace, failure_kind="TRACE_AUTHORITY_MISMATCH", reason="field trace does not belong to the exact MONSTER execution authority")
        field_result = _evaluate_field(raw_trace)
        if field_result.get("status") != "GREEN":
            field_result["fields_verified_before_failure"] = len(verified)
            return field_result
        verified.append(field_result)

    return {
        "status": "GREEN",
        "version": VERSION,
        "decision": "STEP_2D_VERIFIED",
        "monster_only": True,
        "step2d_enforced": True,
        "execution_id": receipt_execution,
        "task_id": receipt_task,
        "fields_verified": len(verified),
        "fields": verified,
        "final_verification_authorized": True,
        "negative_cache_allowed": True,
        "next_legal_action": "FINAL_MONSTER_VERIFICATION",
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    path = {
        "repository": "kyrepeak/kyre-sports-ai",
        "branch": "monster-step2d-self-test",
        "target": "monster:data-truth",
        "proof_path": "monster-step2d-self-test",
    }
    execution = {
        "task_id": "monster-step2d-self-test",
        "execution_id": "exec-self-test",
        "completed": True,
        "status": "SUCCESS",
        "monster_only": True,
        "authoritative_path": path,
    }
    def trace(value: Any) -> dict[str, Any]:
        return {
            "task_id": execution["task_id"],
            "execution_id": execution["execution_id"],
            "field_id": "self-test.field",
            "authoritative_path": path,
            "negative_cache_written": False,
            "stages": {
                "source": {"state": "VALUE_PRESENT", "truth_value": value},
                "ingestion": {"state": "SUCCESS", "truth_value": value},
                "parser": {"state": "SUCCESS", "truth_value": value},
                "identification_mapping": {"state": "SUCCESS", "truth_value": value},
                "normalization": {"state": "SUCCESS", "truth_value": value},
                "monster_authoritative": {"state": "VALUE_PRESENT", "truth_value": value},
                "consumer": {"state": "SUCCESS", "truth_value": value},
                "final_output": {"state": "VALUE_PRESENT", "truth_value": value},
            },
        }

    good = verify_post_execution(execution, [trace(0)])
    broken = trace(22.5)
    broken["stages"]["parser"] = {"state": "PARSER_FAILURE", "detail": "self-test parser failure"}
    broken["stages"]["final_output"] = {"state": "NOT_AVAILABLE"}
    failed = verify_post_execution(execution, [broken])

    result = {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "post_execution_only": good.get("final_verification_authorized") is True,
        "zero_is_data": good.get("fields", [{}])[0].get("verified_truth_value") == 0,
        "technical_failure_preserved": failed.get("preserved_failure_state") == "PARSER_FAILURE",
        "false_absence_blocked": failed.get("final_verification_authorized") is False,
        "autonomous_recovery_route": failed.get("next_legal_action") == "RETURN_TO_MONSTER_STEP_2C",
        "no_negative_cache_on_failure": failed.get("negative_cache_allowed") is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "post_execution_only",
        "zero_is_data",
        "technical_failure_preserved",
        "false_absence_blocked",
        "autonomous_recovery_route",
        "no_negative_cache_on_failure",
    )
    if not all(result[key] is True for key in required):
        raise Mandatory2DDataTruthFailure("Step 2D contract self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_STEP2D_DATA_TRUTH_ZERO_FALSE_BLANK_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
