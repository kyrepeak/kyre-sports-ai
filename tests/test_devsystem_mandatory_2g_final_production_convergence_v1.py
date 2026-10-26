from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem/mandatory_2g_final_production_convergence_v1.py"
    assert path.is_file(), "MONSTER Step 2G production convergence module is required"
    spec = importlib.util.spec_from_file_location("mandatory_2g_final_production_convergence_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _green_evidence():
    certified_sha = "1" * 40
    final_sha = "2" * 40
    artifact_digest = "a" * 64
    deployment_id = "monster-prod-200"
    return {
        "authority": "MONSTER_ONLY",
        "certified": {
            "sha": certified_sha,
            "artifact_digest": artifact_digest,
        },
        "final": {
            "branch": "monster-main",
            "sha": final_sha,
            "contains_certified_sha": True,
            "artifact_digest": artifact_digest,
        },
        "deployment": {
            "id": deployment_id,
            "sha": final_sha,
            "project": "kyre-sports-ai",
            "environment": "production",
            "healthy": True,
            "stale": False,
        },
        "stable_alias": {
            "url": "https://pickvault.streamlit.app",
            "target_deployment_id": deployment_id,
            "target_sha": final_sha,
            "healthy": True,
        },
        "runtime": {
            "entrypoint": "app.py",
            "expected_entrypoint": "app.py",
            "sha": final_sha,
            "deployment_id": deployment_id,
            "artifact_digest": artifact_digest,
            "process_fresh": True,
            "module_cache_fresh": True,
            "application_state_fresh": True,
        },
        "router": {
            "owner": "MONSTER_CANONICAL_ROUTER",
            "expected_owner": "MONSTER_CANONICAL_ROUTER",
            "sport": "nfl",
            "expected_sport": "nfl",
            "market": "game-total",
            "expected_market": "game-total",
            "module": "nfl_game_totals_page1_s_tier_v1",
            "expected_module": "nfl_game_totals_page1_s_tier_v1",
            "backend_endpoint": "/api/v1/nfl/game-total",
            "expected_backend_endpoint": "/api/v1/nfl/game-total",
        },
        "backend": {
            "endpoint": "/api/v1/nfl/game-total",
            "expected_endpoint": "/api/v1/nfl/game-total",
            "schema": "nfl-game-total-v1",
            "expected_schema": "nfl-game-total-v1",
            "data_truth_contract": "STEP2D_GREEN",
            "expected_data_truth_contract": "STEP2D_GREEN",
        },
        "ui": {
            "expected_markers": ["GAME TIME", "BEST EDGES"],
            "observed_markers": ["GAME TIME", "BEST EDGES"],
            "forbidden_markers": ["Step 8", "V8"],
            "observed_forbidden_markers": [],
            "behavior_verified": True,
        },
        "rollback_anchor": {"sha": "0" * 40},
        "promotion_lanes": 1,
    }


def test_step2g_requires_full_live_convergence_and_returns_identity_digest():
    gate = _load()
    result = gate.validate_convergence(_green_evidence())
    assert result["status"] == "GREEN"
    assert result["monster_only"] is True
    assert result["step2g_enforced"] is True
    assert result["final_verification_authorized"] is True
    assert result["frozen_checkpoint_authorized"] is True
    assert result["live_runtime_identity"]["sha"] == "2" * 40
    assert len(result["evidence_digest"]) == 64


def test_repository_new_deployment_new_live_website_old_is_false_green_blocked():
    gate = _load()
    evidence = _green_evidence()
    evidence["runtime"]["sha"] = "3" * 40
    result = gate.validate_convergence(evidence)
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] in {"PROCESS_STALE", "PRODUCTION_NOT_UPDATED", "USER_FACING_PARITY_FAILURE"}
    assert result["final_verification_authorized"] is False
    assert result["frozen_checkpoint_authorized"] is False


def test_alias_drift_blocks_even_when_deployment_is_correct():
    gate = _load()
    evidence = _green_evidence()
    evidence["stable_alias"]["target_deployment_id"] = "old-deployment"
    result = gate.validate_convergence(evidence)
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] in {"ALIAS_DRIFT", "ALIAS_STALE"}


def test_router_backend_and_ui_must_match_certified_contract():
    gate = _load()
    evidence = _green_evidence()
    evidence["router"]["market"] = "spread"
    assert gate.validate_convergence(evidence)["failure_kind"] == "ROUTER_DRIFT"

    evidence = _green_evidence()
    evidence["backend"]["schema"] = "legacy-v8"
    assert gate.validate_convergence(evidence)["failure_kind"] == "API_SCHEMA_DRIFT"

    evidence = _green_evidence()
    evidence["ui"]["observed_markers"] = ["GAME TIME"]
    assert gate.validate_convergence(evidence)["failure_kind"] == "USER_FACING_PARITY_FAILURE"


def test_stale_streamlit_module_cache_blocks_step2g():
    gate = _load()
    evidence = _green_evidence()
    evidence["runtime"]["module_cache_fresh"] = False
    result = gate.validate_convergence(evidence)
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "STREAMLIT_STALE_MODULE"


def test_foreign_system_evidence_is_rejected_and_recovery_is_anti_loop_first():
    gate = _load()
    evidence = _green_evidence()
    evidence["foreign_receipt"] = "api2-step2g-proof"
    result = gate.validate_convergence(evidence)
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "FOREIGN_SYSTEM_EVIDENCE"
    assert result["recovery_sequence"][:4] == ["ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A"]
    assert result["blind_redeploy_allowed"] is False
    assert result["blind_cache_clear_allowed"] is False
