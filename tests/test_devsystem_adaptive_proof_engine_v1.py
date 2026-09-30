from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.adaptive_proof_engine_v1 import (
    FULL_RELEASE_PROOFS,
    plan_proof,
    contract_self_test,
)


HEAD = "a" * 40
OLD = "b" * 40


def test_css_uses_static_plus_targeted_browser_only():
    plan = plan_proof(["ui/theme.css"], expected_head_sha=HEAD, observed_head_sha=HEAD)
    assert plan["state"] == "READY"
    assert plan["change_types"] == ["CSS_UI"]
    assert plan["proofs"] == ["STATIC_CONTRACT", "TARGETED_BROWSER"]
    assert plan["full_release_required"] is False


def test_router_uses_route_contract_plus_fresh_session_navigation():
    plan = plan_proof(
        ["streamlit_memory_lazy_router_v999.py"],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["change_types"] == ["ROUTER_NAVIGATION"]
    assert plan["proofs"] == ["ROUTE_CONTRACT", "FRESH_SESSION_NAVIGATION"]
    assert plan["full_release_required"] is False


def test_provider_uses_field_contract_plus_provenance():
    plan = plan_proof(
        ["sports_api/collectors/nfl_provider_v999.py"],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["change_types"] == ["PROVIDER_DATA"]
    assert plan["proofs"] == ["FIELD_CONTRACT", "PROVENANCE_PROOF"]
    assert plan["full_release_required"] is False


def test_release_uses_full_merged_main_plus_production_certification():
    plan = plan_proof(
        [".github/workflows/production-release-v999.yml"],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["change_types"] == ["RELEASE_DEPLOYMENT"]
    assert plan["proofs"] == list(FULL_RELEASE_PROOFS)
    assert plan["full_release_required"] is True


def test_mixed_changes_compose_every_required_proof_without_duplicates():
    plan = plan_proof(
        [
            "ui/theme.css",
            "streamlit_memory_lazy_router_v999.py",
            "sports_api/collectors/nfl_provider_v999.py",
        ],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["change_types"] == ["CSS_UI", "PROVIDER_DATA", "ROUTER_NAVIGATION"]
    assert plan["proofs"] == [
        "STATIC_CONTRACT",
        "TARGETED_BROWSER",
        "FIELD_CONTRACT",
        "PROVENANCE_PROOF",
        "ROUTE_CONTRACT",
        "FRESH_SESSION_NAVIGATION",
    ]
    assert len(plan["proofs"]) == len(set(plan["proofs"]))


def test_release_mixed_with_other_changes_keeps_other_required_proofs_and_full_release():
    plan = plan_proof(
        [
            "sports_api/collectors/nfl_provider_v999.py",
            ".github/workflows/production-release-v999.yml",
        ],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["full_release_required"] is True
    assert "FIELD_CONTRACT" in plan["proofs"]
    assert "PROVENANCE_PROOF" in plan["proofs"]
    assert "FULL_MERGED_MAIN" in plan["proofs"]
    assert "PRODUCTION_CERTIFICATION" in plan["proofs"]


def test_unknown_change_fails_safe_to_full_release_proof():
    plan = plan_proof(
        ["mystery/new_surface.bin"],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["state"] == "FAIL_SAFE"
    assert plan["change_types"] == ["UNKNOWN"]
    assert plan["proofs"] == list(FULL_RELEASE_PROOFS)
    assert plan["full_release_required"] is True


def test_stale_head_cannot_generate_certifiable_proof_plan():
    plan = plan_proof(
        ["ui/theme.css"],
        expected_head_sha=HEAD,
        observed_head_sha=OLD,
    )
    assert plan["state"] == "STALE_HEAD"
    assert plan["certifiable"] is False
    assert plan["requires_replan"] is True
    assert plan["proofs"] == []


def test_exact_head_plan_is_certifiable():
    plan = plan_proof(
        ["ui/theme.css"],
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    assert plan["certifiable"] is True
    assert plan["requires_replan"] is False
    assert plan["identity"]["expected_head_sha"] == HEAD
    assert plan["identity"]["observed_head_sha"] == HEAD


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["css_targeted_browser"] is True
    assert result["router_fresh_session"] is True
    assert result["provider_provenance"] is True
    assert result["release_full_certification"] is True
    assert result["mixed_union_no_duplicates"] is True
    assert result["stale_head_blocked"] is True
    assert result["unknown_fail_safe"] is True
    assert result["product_runtime_mutation"] is False


def test_engine_runs_directly_as_permanent_self_test():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "adaptive_proof_engine_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_ADAPTIVE_PROOF_ENGINE_V1_GREEN" in completed.stdout
