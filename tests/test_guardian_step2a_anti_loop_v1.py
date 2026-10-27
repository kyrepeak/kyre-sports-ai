from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "devsystem" / "guardian_step2a_anti_loop_v1.py"
WORKFLOW = ROOT / ".github" / "workflows" / "guardian-shared-runtime-lifecycle-v1.yml"
VALID_SHA = "a" * 40
NEW_SHA = "b" * 40


def _load_control():
    assert CONTROL.is_file(), "Guardian Step 2A + Anti-Loop implementation is missing"
    spec = importlib.util.spec_from_file_location("guardian_step2a_anti_loop_v1", CONTROL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guardian_control_module_exists():
    assert CONTROL.is_file(), "Guardian Step 2A + Anti-Loop implementation is missing"


def test_step2a_accepts_one_exact_head_guardian_lane():
    control = _load_control()
    control.validate_step2a(
        system="KYRE_GUARDIAN",
        locked_base_sha=VALID_SHA,
        current_main_sha=VALID_SHA,
        active_problem="shared-runtime-lifecycle-v1",
        active_lane_count=1,
        branch="guardian-shared-runtime-lifecycle-v1",
        pr_number=1896,
        proof_complete=True,
        freeze_requested=True,
    )


def test_step2a_rejects_stale_authoritative_head():
    control = _load_control()
    with pytest.raises(RuntimeError, match="authoritative main changed"):
        control.validate_step2a(
            system="KYRE_GUARDIAN",
            locked_base_sha=VALID_SHA,
            current_main_sha=NEW_SHA,
            active_problem="shared-runtime-lifecycle-v1",
            active_lane_count=1,
            branch="guardian-shared-runtime-lifecycle-v1",
            pr_number=1896,
        )


def test_step2a_rejects_duplicate_active_lanes():
    control = _load_control()
    with pytest.raises(RuntimeError, match="exactly one active Guardian lane"):
        control.validate_step2a(
            system="KYRE_GUARDIAN",
            locked_base_sha=VALID_SHA,
            current_main_sha=VALID_SHA,
            active_problem="shared-runtime-lifecycle-v1",
            active_lane_count=2,
            branch="guardian-shared-runtime-lifecycle-v1",
            pr_number=1896,
        )


def test_step2a_rejects_freeze_before_proof():
    control = _load_control()
    with pytest.raises(RuntimeError, match="proof-before-freeze"):
        control.validate_step2a(
            system="KYRE_GUARDIAN",
            locked_base_sha=VALID_SHA,
            current_main_sha=VALID_SHA,
            active_problem="shared-runtime-lifecycle-v1",
            active_lane_count=1,
            branch="guardian-shared-runtime-lifecycle-v1",
            pr_number=1896,
            proof_complete=False,
            freeze_requested=True,
        )


def test_anti_loop_rejects_same_input_rerun():
    control = _load_control()
    with pytest.raises(RuntimeError, match="blind retry blocked"):
        control.validate_anti_loop(
            run_attempt=2,
            previous_input_fingerprint="same-input",
            current_input_fingerprint="same-input",
        )


def test_anti_loop_allows_retry_only_after_material_input_changes():
    control = _load_control()
    control.validate_anti_loop(
        run_attempt=2,
        previous_input_fingerprint="old-input",
        current_input_fingerprint="new-input",
    )


def test_guardian_workflow_enforces_live_step2a_and_anti_loop_gate():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull-requests: read" in source
    assert "Guard Step 2A exact-head and Anti-Loop" in source
    assert "git ls-remote origin refs/heads/main" in source
    assert "guardian_step2a_anti_loop_v1" in source
    assert "github.run_attempt" in source
    assert "guardian-shared-runtime-lifecycle-v1" in source
