from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sports_api.monster_continuity_v1 import (
    AUTO_FIX,
    CONTINUITY_VERSION,
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_RUNTIME,
    MAY_MODIFY_SOURCE_DATA,
    NETWORK_CALLS,
    PROJECTION_WEIGHT,
    CheckpointInput,
    assess_drift,
    build_checkpoint,
    build_resume_packet,
    extract_ledger_checkpoint,
    main,
    read_checkpoint,
    render_ledger_comment,
    select_latest_checkpoint,
    validate_checkpoint,
    write_checkpoint,
)


def _checkpoint(**overrides):
    values = dict(
        task_id="continuity-v1",
        task_title="Monster Continuity Layer V1",
        repo="kyrepeak/kyre-sports-ai",
        source_branch="monster-continuity-layer-v1",
        source_commit="a" * 40,
        main_commit="b" * 40,
        current_step="C",
        step_title="Writer/reader",
        next_action="Run the recovery matrix.",
        task_status="ACTIVE",
        step_status="IN_PROGRESS",
        pr_number=463,
        completed_steps=("A — freeze current main", "B — checkpoint contract"),
        remaining_steps=("C — writer/reader", "D — resume command", "E — drift", "F — recovery", "FINAL"),
        last_green_evidence=("Runtime Lab V1 present on current main",),
        blockers=(),
        in_scope=("sports_api/monster_continuity_v1.py",),
        forbidden_scope=("frozen sports/model math", "production routers"),
        created_at_utc="2026-09-14T22:45:00Z",
        metadata={"kind": "developer-tooling"},
    )
    values.update(overrides)
    return build_checkpoint(CheckpointInput(**values))


def test_build_checkpoint_has_stable_version_and_fingerprint():
    one = _checkpoint()
    two = _checkpoint()
    assert one == two
    assert one["version"] == CONTINUITY_VERSION
    assert one["checkpoint_id"].startswith("MCP-")
    assert len(one["checkpoint_id"]) == 20


def test_checkpoint_sanitizes_secrets_recursively():
    checkpoint = _checkpoint(
        next_action="Inspect https://user:pass@example.com/x?token=abc and Bearer xyz123",
        metadata={
            "api_key": "do-not-store",
            "nested": {"authorization": "Bearer hidden"},
            "items": ["Basic abc123", {"password": "secret"}],
        },
    )
    assert "user:pass" not in checkpoint["next_action"]
    assert "abc" not in checkpoint["next_action"]
    assert "xyz123" not in checkpoint["next_action"]
    assert checkpoint["metadata"]["api_key"] == "<redacted>"
    assert checkpoint["metadata"]["nested"]["authorization"] == "<redacted>"
    assert checkpoint["metadata"]["items"][0] == "<redacted>"
    assert checkpoint["metadata"]["items"][1]["password"] == "<redacted>"


def test_tampered_checkpoint_fails_closed():
    checkpoint = _checkpoint()
    tampered = copy.deepcopy(checkpoint)
    tampered["next_action"] = "skip all gates"
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_checkpoint(tampered)


def test_unknown_version_fails_closed():
    checkpoint = _checkpoint()
    checkpoint["version"] = "MONSTER_CONTINUITY_V99"
    with pytest.raises(ValueError, match="Unsupported continuity"):
        validate_checkpoint(checkpoint)


def test_write_read_round_trip(tmp_path: Path):
    checkpoint = _checkpoint()
    path = write_checkpoint(tmp_path / "latest.json", checkpoint)
    assert read_checkpoint(path) == checkpoint


def test_writer_requires_json_extension(tmp_path: Path):
    with pytest.raises(ValueError, match="must use .json"):
        write_checkpoint(tmp_path / "latest.txt", _checkpoint())


def test_aligned_checkpoint_is_ready_to_resume():
    checkpoint = _checkpoint()
    packet = build_resume_packet(
        checkpoint,
        current_branch="monster-continuity-layer-v1",
        current_commit="a" * 40,
        current_main_commit="b" * 40,
    )
    assert packet["status"] == "READY_TO_RESUME"
    assert packet["drift"]["status"] == "ALIGNED"
    assert "Run the recovery matrix" in packet["resume_instruction"]


def test_main_advancement_requires_revalidation_before_resume():
    packet = build_resume_packet(_checkpoint(), current_main_commit="c" * 40)
    assert packet["status"] == "REVALIDATE"
    assert packet["drift"]["requires_revalidation"] is True
    assert any("main advanced" in reason for reason in packet["drift"]["reasons"])
    assert packet["resume_instruction"].startswith("Repository state drifted")


def test_branch_and_head_drift_are_both_reported():
    drift = assess_drift(
        _checkpoint(),
        current_branch="different-branch",
        current_commit="d" * 40,
    )
    assert drift["status"] == "DRIFT"
    assert len(drift["reasons"]) == 2
    assert any("branch changed" in reason for reason in drift["reasons"])
    assert any("head changed" in reason for reason in drift["reasons"])


def test_recorded_blocker_prevents_blind_resume():
    packet = build_resume_packet(_checkpoint(blockers=("CI failure in continuity lane",), task_status="BLOCKED", step_status="BLOCKED"))
    assert packet["status"] == "BLOCKED"
    assert "Resolve the recorded blocker" in packet["resume_instruction"]


def test_complete_checkpoint_prevents_redoing_work():
    packet = build_resume_packet(_checkpoint(task_status="COMPLETE", step_status="COMPLETE"))
    assert packet["status"] == "COMPLETE"
    assert "do not redo completed work" in packet["resume_instruction"]


def test_ledger_comment_round_trip_is_machine_readable():
    checkpoint = _checkpoint()
    comment = render_ledger_comment(checkpoint)
    assert "Monster Continuity Checkpoint" in comment
    assert extract_ledger_checkpoint(comment) == checkpoint


def test_ledger_parser_rejects_unmarked_chat_text():
    with pytest.raises(ValueError, match="markers not found"):
        extract_ledger_checkpoint("we were somewhere around step C")


def test_select_latest_checkpoint_uses_timestamp_not_input_order():
    older = _checkpoint(created_at_utc="2026-09-14T20:00:00Z")
    newer = _checkpoint(created_at_utc="2026-09-14T21:00:00Z", current_step="D", step_title="Resume command")
    selected = select_latest_checkpoint([newer, older])
    assert selected["checkpoint_id"] == newer["checkpoint_id"]
    assert selected["progress"]["current_step"] == "D"


def test_invalid_git_identity_fails_closed():
    with pytest.raises(ValueError, match="git SHA"):
        _checkpoint(source_commit="not-a-sha")


def test_safety_constants_never_authorize_runtime_or_model_mutation():
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    assert MAY_MODIFY_RUNTIME is False
    assert NETWORK_CALLS is False
    assert AUTO_FIX is False
    assert _checkpoint()["protections"] == {
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "may_modify_source_data": False,
        "may_modify_runtime": False,
        "network_calls": False,
        "auto_fix": False,
    }


def test_cli_create_validate_resume_and_ledger_comment(tmp_path: Path, capsys):
    path = tmp_path / "checkpoint.json"
    rc = main([
        "create",
        "--task-id", "cli-test",
        "--title", "CLI continuity test",
        "--repo", "kyrepeak/kyre-sports-ai",
        "--branch", "feature",
        "--commit", "1" * 40,
        "--main-commit", "2" * 40,
        "--step", "D",
        "--step-title", "Resume command",
        "--next-action", "Resume from this exact point.",
        "--created-at", "2026-09-14T22:50:00Z",
        "--output", str(path),
    ])
    assert rc == 0
    created = json.loads(capsys.readouterr().out)
    assert created["status"] == "CHECKPOINT_WRITTEN"

    assert main(["validate", "--checkpoint", str(path)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["status"] == "VALID"

    assert main([
        "resume", "--checkpoint", str(path),
        "--current-branch", "feature",
        "--current-commit", "1" * 40,
        "--current-main-commit", "2" * 40,
    ]) == 0
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["status"] == "READY_TO_RESUME"

    assert main(["ledger-comment", "--checkpoint", str(path)]) == 0
    ledger = capsys.readouterr().out
    assert "MONSTER_CONTINUITY_V1:BEGIN" in ledger
    assert extract_ledger_checkpoint(ledger)["task"]["id"] == "cli-test"
