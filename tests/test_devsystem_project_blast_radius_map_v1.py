from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.project_blast_radius_map_v1 import contract_self_test, plan_change

HEAD = "a" * 40
OLD = "b" * 40


def test_shared_leaf_exposes_entrypoint_blast_radius(tmp_path):
    (tmp_path / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("import shared\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("import feature\n", encoding="utf-8")

    plan = plan_change(
        ["shared.py"],
        root=tmp_path,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["blast_radius"] == 2
    assert plan["impacted_entrypoints"] == ["app.py"]
    assert plan["risk"] == "HIGH"
    assert plan["state"] == "READY"
    assert plan["edit_allowed"] is True
    assert plan["direct_dependents"] == ["feature"]
    assert plan["transitive_dependents"] == ["app", "feature"]


def test_protected_reach_is_visible_before_edit(tmp_path):
    (tmp_path / "frozen_projection.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("import frozen_projection\n", encoding="utf-8")

    plan = plan_change(
        ["feature.py"],
        root=tmp_path,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["frozen_impact"] is True
    assert "frozen_projection.py" in plan["protected_reach"]
    assert plan["state"] == "BLOCKED_PROTECTED_REACH"
    assert plan["edit_allowed"] is False
    assert plan["requires_narrowing"] is True
    assert plan["next_legal_action"] == "NARROW_EDIT_SCOPE"
    assert plan["risk"] in {"HIGH", "CRITICAL"}


def test_unknown_surface_fails_safe_to_full_proof(tmp_path):
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    plan = plan_change(
        ["unknown/new_surface.bin"],
        root=tmp_path,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["unknown_targets"] == ["unknown/new_surface.bin"]
    assert plan["state"] == "FAIL_SAFE"
    assert plan["edit_allowed"] is False
    assert plan["next_legal_action"] == "RESOLVE_UNKNOWN_TARGETS"
    assert plan["proof_plan"]["full_release_required"] is True


def test_stale_head_requires_replan(tmp_path):
    (tmp_path / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
    plan = plan_change(
        ["leaf.py"],
        root=tmp_path,
        expected_head_sha=HEAD,
        observed_head_sha=OLD,
    )
    assert plan["state"] == "STALE_HEAD"
    assert plan["certifiable"] is False
    assert plan["edit_allowed"] is False
    assert plan["requires_replan"] is True
    assert plan["reports"] == []
    assert plan["proof_plan"]["certifiable"] is False
    assert plan["proof_plan"]["requires_replan"] is True


def test_multiple_paths_union_dependents_without_double_counting(tmp_path):
    (tmp_path / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("import shared\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("import shared\nimport feature\n", encoding="utf-8")

    plan = plan_change(
        ["shared.py", "feature.py"],
        root=tmp_path,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["transitive_dependents"] == ["app", "feature"]
    assert plan["blast_radius"] == 2


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["direct_transitive_map"] is True
    assert result["protected_reach_guard"] is True
    assert result["blast_radius_risk"] is True
    assert result["adaptive_proof_handoff"] is True
    assert result["unknown_fail_safe"] is True
    assert result["stale_head_blocked"] is True
    assert result["product_runtime_mutation"] is False


def test_engine_runs_directly():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "project_blast_radius_map_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_PROJECT_BLAST_RADIUS_MAP_V1_GREEN" in completed.stdout
