"""MONSTER V3 Step 8 — Monster Self-Benchmarking V1.

Deterministic, read-only execution-quality benchmark for MONSTER itself.

Consumes normalized task/run summaries and reports time-to-root-cause,
time-to-GREEN/repair time, CI time, runs required, reruns, reruns avoided,
stale runs/proofs rejected, false failures, loops/loops prevented,
production mismatches, actions per step, GREEN rate, first-pass GREEN rate,
and first-patch success rate.

It does not fetch telemetry, mutate repositories, influence sports models, or
rank product outcomes.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_SELF_BENCHMARK_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
PROJECTION_WEIGHT = 0.0

_FINAL_STATES = {"GREEN", "FAILURE", "DEFERRED"}


class SelfBenchmarkFailure(RuntimeError):
    pass


def _parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SelfBenchmarkFailure("timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise SelfBenchmarkFailure("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    raw = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()
    return f"BENCH-{raw}"


def _nonnegative_int(value: Any, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SelfBenchmarkFailure(f"{field} must be an integer") from exc
    if parsed < 0:
        raise SelfBenchmarkFailure(f"{field} must be nonnegative")
    return parsed


def _nonnegative_float(value: Any, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SelfBenchmarkFailure(f"{field} must be numeric") from exc
    if parsed < 0:
        raise SelfBenchmarkFailure(f"{field} must be nonnegative")
    return parsed


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise SelfBenchmarkFailure("benchmark record must be an object")

    task_id = str(record.get("task_id") or "").strip()
    if not task_id:
        raise SelfBenchmarkFailure("task_id is required")

    started = _parse_utc(str(record.get("started_at_utc") or ""))
    completed = _parse_utc(str(record.get("completed_at_utc") or ""))
    if completed < started:
        raise SelfBenchmarkFailure("completed_at_utc may not precede started_at_utc")

    attempts = _nonnegative_int(record.get("attempts"), field="attempts")
    if attempts < 1:
        raise SelfBenchmarkFailure("attempts must be at least 1")

    final_state = str(record.get("final_state") or "").strip().upper()
    if final_state not in _FINAL_STATES:
        raise SelfBenchmarkFailure("final_state is invalid")

    repair_seconds = (completed - started).total_seconds()
    root_cause_seconds = _nonnegative_float(
        record.get("root_cause_seconds", repair_seconds),
        field="root_cause_seconds",
    )
    if root_cause_seconds > repair_seconds:
        raise SelfBenchmarkFailure("root_cause_seconds may not exceed repair_seconds")

    actions = _nonnegative_int(record.get("actions", 1), field="actions")
    if actions < 1:
        raise SelfBenchmarkFailure("actions must be at least 1")

    return {
        "task_id": task_id,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "repair_seconds": repair_seconds,
        "time_to_green_seconds": repair_seconds if final_state == "GREEN" else None,
        "root_cause_seconds": root_cause_seconds,
        "attempts": attempts,
        "actions": actions,
        "ci_seconds": _nonnegative_float(record.get("ci_seconds", 0), field="ci_seconds"),
        "reruns_avoided": _nonnegative_int(record.get("reruns_avoided", 0), field="reruns_avoided"),
        "stale_runs": _nonnegative_int(record.get("stale_runs", 0), field="stale_runs"),
        "stale_proofs_rejected": _nonnegative_int(
            record.get("stale_proofs_rejected", 0),
            field="stale_proofs_rejected",
        ),
        "false_failures": _nonnegative_int(record.get("false_failures", 0), field="false_failures"),
        "loops": _nonnegative_int(record.get("loops", 0), field="loops"),
        "loops_prevented": _nonnegative_int(record.get("loops_prevented", 0), field="loops_prevented"),
        "production_mismatches": _nonnegative_int(
            record.get("production_mismatches", 0),
            field="production_mismatches",
        ),
        "first_patch_success": bool(
            record.get(
                "first_patch_success",
                final_state == "GREEN" and attempts == 1,
            )
        ),
        "final_state": final_state,
    }


def build_benchmark(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise SelfBenchmarkFailure("at least one benchmark record is required")

    normalized = [_normalize_record(record) for record in records]
    task_ids = [record["task_id"] for record in normalized]
    if len(task_ids) != len(set(task_ids)):
        raise SelfBenchmarkFailure("task_id values must be unique")

    task_count = len(normalized)
    green_records = [record for record in normalized if record["final_state"] == "GREEN"]
    green_count = len(green_records)
    first_pass_green_count = sum(
        record["final_state"] == "GREEN" and record["attempts"] == 1
        for record in normalized
    )
    first_patch_success_count = sum(record["first_patch_success"] for record in normalized)
    repair_times = [record["repair_seconds"] for record in normalized]
    root_cause_times = [record["root_cause_seconds"] for record in normalized]
    ci_times = [record["ci_seconds"] for record in normalized]
    green_times = [record["time_to_green_seconds"] for record in green_records]

    body: dict[str, Any] = {
        "version": VERSION,
        "status": "GREEN",
        "task_count": task_count,
        "green_count": green_count,
        "failure_count": sum(record["final_state"] == "FAILURE" for record in normalized),
        "deferred_count": sum(record["final_state"] == "DEFERRED" for record in normalized),
        "green_rate": green_count / task_count,
        "first_pass_green_count": first_pass_green_count,
        "first_pass_green_rate": first_pass_green_count / task_count,
        "first_patch_success_count": first_patch_success_count,
        "first_patch_success_rate": first_patch_success_count / task_count,
        "run_count": sum(record["attempts"] for record in normalized),
        "average_runs_per_step": statistics.fmean(record["attempts"] for record in normalized),
        "rerun_count": sum(max(0, record["attempts"] - 1) for record in normalized),
        "reruns_avoided_count": sum(record["reruns_avoided"] for record in normalized),
        "stale_run_count": sum(record["stale_runs"] for record in normalized),
        "stale_proof_rejected_count": sum(record["stale_proofs_rejected"] for record in normalized),
        "false_failure_count": sum(record["false_failures"] for record in normalized),
        "loop_count": sum(record["loops"] for record in normalized),
        "loops_prevented_count": sum(record["loops_prevented"] for record in normalized),
        "production_mismatch_count": sum(record["production_mismatches"] for record in normalized),
        "action_count": sum(record["actions"] for record in normalized),
        "average_actions_per_step": statistics.fmean(record["actions"] for record in normalized),
        "total_root_cause_seconds": sum(root_cause_times),
        "average_root_cause_seconds": statistics.fmean(root_cause_times),
        "median_root_cause_seconds": statistics.median(root_cause_times),
        "total_repair_seconds": sum(repair_times),
        "average_repair_seconds": statistics.fmean(repair_times),
        "median_repair_seconds": statistics.median(repair_times),
        "average_time_to_green_seconds": statistics.fmean(green_times) if green_times else None,
        "total_ci_seconds": sum(ci_times),
        "average_ci_seconds": statistics.fmean(ci_times),
        "records": normalized,
        "protections": {
            "read_only": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "projection_weight": PROJECTION_WEIGHT,
            "no_overall_vanity_score": True,
        },
    }
    body["benchmark_id"] = _fingerprint(body)
    return validate_benchmark(body)


def validate_benchmark(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise SelfBenchmarkFailure("benchmark snapshot must be an object")
    value = deepcopy(dict(payload))
    supplied = str(value.pop("benchmark_id", ""))
    if not supplied:
        raise SelfBenchmarkFailure("benchmark snapshot requires benchmark_id")
    expected = _fingerprint(value)
    if supplied != expected:
        raise SelfBenchmarkFailure("benchmark fingerprint mismatch")
    if value.get("version") != VERSION:
        raise SelfBenchmarkFailure("unsupported benchmark version")
    if value.get("status") != "GREEN":
        raise SelfBenchmarkFailure("benchmark status must be GREEN")
    protections = value.get("protections")
    expected_protections = {
        "read_only": True,
        "network_calls": False,
        "auto_mutate": False,
        "may_modify_product_runtime": False,
        "projection_weight": 0.0,
        "no_overall_vanity_score": True,
    }
    if protections != expected_protections:
        raise SelfBenchmarkFailure("benchmark protections drift")
    value["benchmark_id"] = supplied
    return value


def compare_benchmarks(
    current: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    now = validate_benchmark(current)
    before = validate_benchmark(baseline)
    metrics = {
        "first_pass_green_rate": now["first_pass_green_rate"] - before["first_pass_green_rate"],
        "first_patch_success_rate": now["first_patch_success_rate"] - before["first_patch_success_rate"],
        "green_rate": now["green_rate"] - before["green_rate"],
        "average_root_cause_seconds": now["average_root_cause_seconds"] - before["average_root_cause_seconds"],
        "average_repair_seconds": now["average_repair_seconds"] - before["average_repair_seconds"],
        "average_ci_seconds": now["average_ci_seconds"] - before["average_ci_seconds"],
        "average_runs_per_step": now["average_runs_per_step"] - before["average_runs_per_step"],
        "average_actions_per_step": now["average_actions_per_step"] - before["average_actions_per_step"],
        "rerun_count": now["rerun_count"] - before["rerun_count"],
        "reruns_avoided_count": now["reruns_avoided_count"] - before["reruns_avoided_count"],
        "stale_run_count": now["stale_run_count"] - before["stale_run_count"],
        "stale_proof_rejected_count": now["stale_proof_rejected_count"] - before["stale_proof_rejected_count"],
        "false_failure_count": now["false_failure_count"] - before["false_failure_count"],
        "loop_count": now["loop_count"] - before["loop_count"],
        "loops_prevented_count": now["loops_prevented_count"] - before["loops_prevented_count"],
        "production_mismatch_count": now["production_mismatch_count"] - before["production_mismatch_count"],
    }
    return {
        "version": VERSION,
        "status": "GREEN",
        "current_benchmark_id": now["benchmark_id"],
        "baseline_benchmark_id": before["benchmark_id"],
        "deltas": metrics,
        "interpretation": {
            "higher_is_better": [
                "first_pass_green_rate",
                "first_patch_success_rate",
                "reruns_avoided_count",
                "stale_proof_rejected_count",
                "loops_prevented_count",
            ],
            "lower_is_better": [
                "average_root_cause_seconds",
                "average_repair_seconds",
                "average_ci_seconds",
                "average_runs_per_step",
                "average_actions_per_step",
                "rerun_count",
                "stale_run_count",
                "false_failure_count",
                "loop_count",
                "production_mismatch_count",
            ],
            "context_only": ["green_rate"],
            "overall_score": None,
        },
    }


def contract_self_test() -> dict[str, Any]:
    baseline = build_benchmark([
        {
            "task_id": "a",
            "started_at_utc": "2026-09-30T00:00:00Z",
            "completed_at_utc": "2026-09-30T00:02:00Z",
            "root_cause_seconds": 75,
            "attempts": 2,
            "actions": 5,
            "ci_seconds": 60,
            "reruns_avoided": 0,
            "stale_runs": 1,
            "stale_proofs_rejected": 0,
            "false_failures": 1,
            "loops": 1,
            "loops_prevented": 0,
            "production_mismatches": 1,
            "first_patch_success": False,
            "final_state": "GREEN",
        },
        {
            "task_id": "b",
            "started_at_utc": "2026-09-30T00:10:00Z",
            "completed_at_utc": "2026-09-30T00:12:00Z",
            "root_cause_seconds": 60,
            "attempts": 1,
            "actions": 3,
            "ci_seconds": 50,
            "final_state": "GREEN",
        },
    ])
    current = build_benchmark([
        {
            "task_id": "c",
            "started_at_utc": "2026-09-30T01:00:00Z",
            "completed_at_utc": "2026-09-30T01:01:00Z",
            "root_cause_seconds": 20,
            "attempts": 1,
            "actions": 2,
            "ci_seconds": 30,
            "reruns_avoided": 1,
            "stale_proofs_rejected": 1,
            "loops_prevented": 1,
            "first_patch_success": True,
            "final_state": "GREEN",
        },
        {
            "task_id": "d",
            "started_at_utc": "2026-09-30T01:10:00Z",
            "completed_at_utc": "2026-09-30T01:11:00Z",
            "root_cause_seconds": 15,
            "attempts": 1,
            "actions": 2,
            "ci_seconds": 30,
            "reruns_avoided": 1,
            "stale_proofs_rejected": 1,
            "loops_prevented": 1,
            "first_patch_success": True,
            "final_state": "GREEN",
        },
    ])
    comparison = compare_benchmarks(current, baseline)

    result = {
        "status": "GREEN",
        "version": VERSION,
        "root_cause_time_tracked": current["average_root_cause_seconds"] == 17.5,
        "repair_time_tracked": current["average_repair_seconds"] == 60.0,
        "time_to_green_tracked": current["average_time_to_green_seconds"] == 60.0,
        "ci_time_tracked": current["average_ci_seconds"] == 30.0,
        "runs_required_tracked": current["average_runs_per_step"] == 1.0,
        "actions_per_step_tracked": current["average_actions_per_step"] == 2.0,
        "reruns_tracked": baseline["rerun_count"] == 1,
        "reruns_avoided_tracked": current["reruns_avoided_count"] == 2,
        "stale_runs_tracked": baseline["stale_run_count"] == 1,
        "stale_proofs_rejected_tracked": current["stale_proof_rejected_count"] == 2,
        "false_failures_tracked": baseline["false_failure_count"] == 1,
        "loops_tracked": baseline["loop_count"] == 1,
        "loops_prevented_tracked": current["loops_prevented_count"] == 2,
        "production_mismatches_tracked": baseline["production_mismatch_count"] == 1,
        "first_pass_green_rate_tracked": current["first_pass_green_rate"] == 1.0,
        "first_patch_success_rate_tracked": current["first_patch_success_rate"] == 1.0,
        "trend_deltas_available": comparison["deltas"]["average_repair_seconds"] < 0,
        "no_overall_vanity_score": comparison["interpretation"]["overall_score"] is None,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "projection_weight": PROJECTION_WEIGHT,
    }
    required = (
        "root_cause_time_tracked",
        "repair_time_tracked",
        "time_to_green_tracked",
        "ci_time_tracked",
        "runs_required_tracked",
        "actions_per_step_tracked",
        "reruns_tracked",
        "reruns_avoided_tracked",
        "stale_runs_tracked",
        "stale_proofs_rejected_tracked",
        "false_failures_tracked",
        "loops_tracked",
        "loops_prevented_tracked",
        "production_mismatches_tracked",
        "first_pass_green_rate_tracked",
        "first_patch_success_rate_tracked",
        "trend_deltas_available",
        "no_overall_vanity_score",
    )
    if not all(result[key] is True for key in required):
        raise SelfBenchmarkFailure("self-benchmark contract failed")
    return result


if __name__ == "__main__":
    print("MONSTER_SELF_BENCHMARK_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
