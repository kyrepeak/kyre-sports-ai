from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.monster_self_benchmark_v1 import (
    SelfBenchmarkFailure,
    build_benchmark,
    compare_benchmarks,
    contract_self_test,
    validate_benchmark,
)


def _record(task_id: str, **overrides):
    value = {
        "task_id": task_id,
        "started_at_utc": "2026-09-30T00:00:00Z",
        "completed_at_utc": "2026-09-30T00:01:00Z",
        "root_cause_seconds": 20,
        "attempts": 1,
        "actions": 2,
        "ci_seconds": 30,
        "reruns_avoided": 0,
        "stale_runs": 0,
        "stale_proofs_rejected": 0,
        "false_failures": 0,
        "loops": 0,
        "loops_prevented": 0,
        "production_mismatches": 0,
        "first_patch_success": True,
        "final_state": "GREEN",
    }
    value.update(overrides)
    return value


def test_benchmark_tracks_execution_quality_metrics():
    result = build_benchmark([
        _record("one"),
        _record(
            "two",
            completed_at_utc="2026-09-30T00:02:00Z",
            root_cause_seconds=60,
            attempts=2,
            actions=5,
            ci_seconds=60,
            reruns_avoided=1,
            stale_runs=1,
            stale_proofs_rejected=1,
            false_failures=1,
            loops=1,
            loops_prevented=1,
            production_mismatches=1,
            first_patch_success=False,
        ),
    ])
    assert result["task_count"] == 2
    assert result["green_rate"] == 1.0
    assert result["first_pass_green_rate"] == 0.5
    assert result["run_count"] == 3
    assert result["average_runs_per_step"] == 1.5
    assert result["rerun_count"] == 1
    assert result["reruns_avoided_count"] == 1
    assert result["stale_run_count"] == 1
    assert result["stale_proof_rejected_count"] == 1
    assert result["false_failure_count"] == 1
    assert result["loop_count"] == 1
    assert result["loops_prevented_count"] == 1
    assert result["production_mismatch_count"] == 1
    assert result["average_actions_per_step"] == 3.5
    assert result["average_root_cause_seconds"] == 40.0
    assert result["average_repair_seconds"] == 90.0
    assert result["average_time_to_green_seconds"] == 90.0
    assert result["average_ci_seconds"] == 45.0
    assert result["first_patch_success_rate"] == 0.5


def test_failure_and_deferred_states_are_counted_without_faking_green():
    result = build_benchmark([
        _record("green"),
        _record("failure", final_state="FAILURE"),
        _record("deferred", final_state="DEFERRED"),
    ])
    assert result["task_count"] == 3
    assert result["green_count"] == 1
    assert result["failure_count"] == 1
    assert result["deferred_count"] == 1
    assert result["green_rate"] == pytest.approx(1 / 3)


def test_trend_comparison_reports_deltas_without_overall_score():
    baseline = build_benchmark([
        _record("old", attempts=2, ci_seconds=80, completed_at_utc="2026-09-30T00:02:00Z", first_patch_success=False),
    ])
    current = build_benchmark([
        _record("new", attempts=1, ci_seconds=30),
    ])
    comparison = compare_benchmarks(current, baseline)
    assert comparison["deltas"]["first_pass_green_rate"] > 0
    assert comparison["deltas"]["first_patch_success_rate"] > 0
    assert comparison["deltas"]["average_ci_seconds"] < 0
    assert comparison["deltas"]["average_runs_per_step"] < 0
    assert comparison["deltas"]["rerun_count"] < 0
    assert comparison["interpretation"]["overall_score"] is None


def test_snapshot_fingerprint_detects_tampering():
    result = build_benchmark([_record("one")])
    tampered = copy.deepcopy(result)
    tampered["loop_count"] = 99
    with pytest.raises(SelfBenchmarkFailure, match="fingerprint mismatch"):
        validate_benchmark(tampered)


def test_invalid_records_fail_closed():
    with pytest.raises(SelfBenchmarkFailure):
        build_benchmark([_record("one", attempts=0)])
    with pytest.raises(SelfBenchmarkFailure):
        build_benchmark([
            _record(
                "one",
                started_at_utc="2026-09-30T00:02:00Z",
                completed_at_utc="2026-09-30T00:01:00Z",
            )
        ])
    with pytest.raises(SelfBenchmarkFailure):
        build_benchmark([_record("same"), _record("same")])


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["root_cause_time_tracked"] is True
    assert result["repair_time_tracked"] is True
    assert result["time_to_green_tracked"] is True
    assert result["ci_time_tracked"] is True
    assert result["runs_required_tracked"] is True
    assert result["actions_per_step_tracked"] is True
    assert result["reruns_tracked"] is True
    assert result["reruns_avoided_tracked"] is True
    assert result["stale_runs_tracked"] is True
    assert result["stale_proofs_rejected_tracked"] is True
    assert result["false_failures_tracked"] is True
    assert result["loops_tracked"] is True
    assert result["loops_prevented_tracked"] is True
    assert result["production_mismatches_tracked"] is True
    assert result["first_pass_green_rate_tracked"] is True
    assert result["first_patch_success_rate_tracked"] is True
    assert result["trend_deltas_available"] is True
    assert result["no_overall_vanity_score"] is True
    assert result["product_runtime_mutation"] is False
    assert result["projection_weight"] == 0.0


def test_engine_runs_directly():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "monster_self_benchmark_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_SELF_BENCHMARK_V1_GREEN" in completed.stdout
