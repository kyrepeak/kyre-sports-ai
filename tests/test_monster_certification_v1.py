from __future__ import annotations

import json
from pathlib import Path

import pytest

from sports_api.monster_certification_v1 import (
    AUTHORITATIVE_MERGE_GATE,
    CERTIFICATION_VERSION,
    FUZZY_MATCHING,
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_RUNTIME,
    MAY_MODIFY_SOURCE_DATA,
    NETWORK_CALLS,
    PROJECTION_WEIGHT,
    REPLACES_DEVSYSTEM_FINAL_GATE,
    CheckSpec,
    CommandResult,
    certification_manifest,
    run_certification,
)


def _one_check(path: str = "probe.txt") -> tuple[CheckSpec, ...]:
    return (
        CheckSpec(
            check_id="probe",
            label="Probe",
            command=("python", "-c", "pass"),
            required_paths=(path,),
        ),
    )


def test_version_and_safety_contract_are_explicit() -> None:
    assert CERTIFICATION_VERSION == "MONSTER_ONE_COMMAND_CERTIFICATION_V1"
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    assert MAY_MODIFY_RUNTIME is False
    assert NETWORK_CALLS is False
    assert FUZZY_MATCHING is False
    assert REPLACES_DEVSYSTEM_FINAL_GATE is False
    assert AUTHORITATIVE_MERGE_GATE == "devsystem-final-gate"


def test_manifest_certifies_compile_plus_steps_1_through_6() -> None:
    manifest = certification_manifest()
    assert [item.check_id for item in manifest] == [
        "final_form_compile",
        "step1_error_radar",
        "step2_performance_profiler",
        "step3_dependency_map",
        "step4_page_factory",
        "step5_test_matrix",
        "step6_failure_memory",
    ]
    assert len(manifest) == 7


def test_manifest_points_only_at_real_repository_files() -> None:
    root = Path(__file__).resolve().parents[1]
    missing = [
        path
        for spec in certification_manifest()
        for path in spec.required_paths
        if not (root / path).is_file()
    ]
    assert missing == []


def test_manifest_has_no_network_commands_or_shell_wrappers() -> None:
    forbidden = ("curl", "wget", "http://", "https://", "bash", "sh -c")
    for spec in certification_manifest():
        rendered = " ".join(spec.command).lower()
        assert not any(token in rendered for token in forbidden)


def test_pass_receipt_requires_every_check_to_pass(tmp_path: Path) -> None:
    (tmp_path / "probe.txt").write_text("ok", encoding="utf-8")
    seen: list[tuple[str, ...]] = []

    def runner(command, cwd):
        assert cwd == tmp_path.resolve()
        seen.append(tuple(command))
        return CommandResult(0, "1 passed", "")

    receipt = run_certification(tmp_path, runner=runner, checks=_one_check())
    assert receipt["status"] == "PASS"
    assert receipt["passed_check_count"] == 1
    assert receipt["failed_check_count"] == 0
    assert receipt["all_required_executed"] is True
    assert seen == [("python", "-c", "pass")]


def test_nonzero_command_fails_closed_with_evidence(tmp_path: Path) -> None:
    (tmp_path / "probe.txt").write_text("ok", encoding="utf-8")

    def runner(command, cwd):
        return CommandResult(7, "", "assertion exploded")

    receipt = run_certification(tmp_path, runner=runner, checks=_one_check())
    result = receipt["results"][0]
    assert receipt["status"] == "FAIL"
    assert result["status"] == "FAIL"
    assert result["reason"] == "command_failed"
    assert result["returncode"] == 7
    assert result["evidence"] == "assertion exploded"


def test_missing_required_path_fails_before_runner(tmp_path: Path) -> None:
    called = False

    def runner(command, cwd):
        nonlocal called
        called = True
        return CommandResult(0)

    receipt = run_certification(tmp_path, runner=runner, checks=_one_check("missing.py"))
    result = receipt["results"][0]
    assert receipt["status"] == "FAIL"
    assert result["reason"] == "required_path_missing"
    assert result["evidence"] == "missing.py"
    assert called is False


def test_runner_exception_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "probe.txt").write_text("ok", encoding="utf-8")

    def runner(command, cwd):
        raise TimeoutError("too slow")

    receipt = run_certification(tmp_path, runner=runner, checks=_one_check())
    result = receipt["results"][0]
    assert receipt["status"] == "FAIL"
    assert result["reason"] == "runner_exception"
    assert "TimeoutError: too slow" in result["evidence"]


def test_fail_fast_marks_incomplete_certification_as_fail(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    checks = (
        CheckSpec("a", "A", ("python", "a"), ("a.txt",)),
        CheckSpec("b", "B", ("python", "b"), ("b.txt",)),
    )
    calls = 0

    def runner(command, cwd):
        nonlocal calls
        calls += 1
        return CommandResult(1, "", "failed")

    receipt = run_certification(tmp_path, runner=runner, checks=checks, fail_fast=True)
    assert receipt["status"] == "FAIL"
    assert receipt["executed_check_count"] == 1
    assert receipt["required_check_count"] == 2
    assert receipt["all_required_executed"] is False
    assert calls == 1


def test_receipt_is_machine_readable_json(tmp_path: Path) -> None:
    (tmp_path / "probe.txt").write_text("ok", encoding="utf-8")
    receipt = run_certification(
        tmp_path,
        runner=lambda command, cwd: CommandResult(0, "passed", ""),
        checks=_one_check(),
    )
    encoded = json.dumps(receipt)
    decoded = json.loads(encoded)
    assert decoded["certification_version"] == CERTIFICATION_VERSION
    assert decoded["protections"]["authoritative_merge_gate"] == "devsystem-final-gate"
    assert decoded["protections"]["projection_weight"] == 0.0


def test_failure_evidence_is_bounded(tmp_path: Path) -> None:
    (tmp_path / "probe.txt").write_text("ok", encoding="utf-8")
    huge = "x" * 10000
    receipt = run_certification(
        tmp_path,
        runner=lambda command, cwd: CommandResult(1, "", huge),
        checks=_one_check(),
    )
    assert len(receipt["results"][0]["evidence"]) == 3000
