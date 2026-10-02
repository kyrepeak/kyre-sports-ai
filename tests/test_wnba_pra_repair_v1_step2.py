from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import wnba_pra_repair_v1_step2_team_identity as identity

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py"
CERT = ROOT / "devsystem/wnba_pra_repair_v1_step2_team_identity_cert.py"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-repair-v1-step2-team-identity.json"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-repair-v1-step2-team-identity.yml"
APP = ROOT / "app.py"


def test_step2_identity_registry_is_lightweight_unique_and_complete():
    source = (ROOT / "wnba_pra_repair_v1_step2_team_identity.py").read_text(encoding="utf-8")
    assert ast.parse(source)
    assert len(identity.TEAM_BY_ID) == 15
    assert len(set(identity.TEAM_BY_ID)) == 15
    assert all(str(team_id).startswith("161166") for team_id in identity.TEAM_BY_ID)
    for forbidden in ("import pandas", "import requests", "import streamlit"):
        assert forbidden not in source


def test_step2_repairs_provider_numeric_alias_from_name_and_tricode():
    game = {
        "game_id": "test",
        "away_team_id": 999999,
        "away_team": "Phoenix Mercury",
        "away_tricode": "PHX",
        "home_team_id": 1611661328,
        "home_team": "Seattle Storm",
        "home_tricode": "SEA",
    }
    out = identity.reconcile_game_identity(game)
    assert out["away_team_id"] == 1611661317
    assert out["away_source_team_id"] == 999999
    assert out["away_identity_repaired"] is True
    assert out["home_team_id"] == 1611661328
    assert out["home_identity_repaired"] is False
    assert out["team_identity_state"] == "CANONICAL"


def test_step2_fails_closed_on_conflicting_identity():
    with pytest.raises(identity.WNBATeamIdentityError):
        identity.resolve_team_identity(
            raw_team_id=1611661330,
            team_name="Phoenix Mercury",
            team_tricode="PHX",
        )


def test_step2_rejects_same_team_on_both_sides():
    with pytest.raises(identity.WNBATeamIdentityError):
        identity.reconcile_game_identity(
            {
                "away_team_id": 1611661317,
                "away_team": "Phoenix Mercury",
                "away_tricode": "PHX",
                "home_team_id": 1611661317,
                "home_team": "Phoenix Mercury",
                "home_tricode": "PHX",
            }
        )


def test_step2_overlay_wraps_parent_and_restores_frozen_modules():
    source = OVERLAY.read_text(encoding="utf-8")
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"' in source
    assert "identity.reconcile_slate_payload(payload)" in source
    assert "slate.load_slate = guarded_slate_loader" in source
    assert "performance._FROZEN_SLATE_LOADER = guarded_slate_loader" in source
    assert "game_center.load_game_center = guarded_game_loader" in source
    assert "game_center.render_game_center = guarded_game_renderer" in source
    assert "slate.load_slate = original_slate_loader" in source
    assert "performance._FROZEN_SLATE_LOADER = original_cached_slate_loader" in source
    assert "game_center.load_game_center = original_game_loader" in source
    assert "game_center.render_game_center = original_game_renderer" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION_MATH = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source



def test_step2_prewarm_preserves_frozen_math_and_parallelizes_only_dependencies():
    source = OVERLAY.read_text(encoding="utf-8")
    assert "ThreadPoolExecutor(max_workers=3" in source
    assert "availability._verified_pool_for_day" in source
    assert "availability.availability_for_game_key" in source
    assert "role.advanced_usage_table" in source
    assert "_prewarm_game_center_dependencies(" in source
    assert "return original_game_loader(" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION_MATH = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step2_app_activates_overlay_and_keeps_step9_compatibility():
    app = APP.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP2_TEAM_ID_RUNTIME" in app
    assert "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity import record_bootstrap_import_ms, render_app" in app
    assert "Frozen WNBA PRA Speed V3 Step 9 compatibility: from streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard import record_bootstrap_import_ms, render_app" in app


def test_step2_cert_requires_real_public_two_team_proof():
    source = CERT.read_text(encoding="utf-8")
    assert "nav._find_game_date()" in source
    assert "speed9._prime_wnba_pra_route" in source
    assert "data-away-team-id" in source
    assert "data-home-team-id" in source
    assert "data-away-player-count" in source
    assert "data-home-player-count" in source
    assert "identity.is_canonical_team_id" in source
    assert 'frame.locator(".wn3-teamhead").count() < 2' in source
    for token in (
        "WNBA_PRA_REPAIR_V1_STEP2_BOTH_TEAM_IDS_CANONICAL_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP2_BOTH_TEAM_PLAYER_GROUPS_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP2_FROZEN_SPEED_V3_STEPS1_9_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP2_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP2_FROZEN",
    ):
        assert token in source


def test_step2_ledger_locks_step2a_and_protects_previous_work():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Repair V1"
    assert ledger["step"] == 2
    assert ledger["total_steps"] == 7
    assert ledger["status"] == "DONE"
    assert ledger["protected"]["step1_load_audit"] is True
    assert ledger["protected"]["wnba_pra_speed_v3_steps_1_9"] is True
    assert ledger["two_a"]["one_active_problem"] is True
    assert ledger["two_a"]["one_active_branch"] is True
    assert ledger["two_a"]["one_active_pr_max"] == 1
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["two_a"]["no_unchanged_failed_reruns"] is True
    assert ledger["action_log"]["head_chain_hash"] == "0" * 64
    assert ledger["action_log"]["events"] == []
    assert ledger["action_log"]["consumed_receipts"] == []


def test_step2_workflow_exact_scope_and_frozen_blob_guards():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA PRA Repair V1 Step 2 Team Identity" in workflow
    assert "Enforce exact Step-2 scope" in workflow
    assert "Verify frozen WNBA PRA dependencies" in workflow
    assert "4636cb4314489e3458b70cb3c17c6a6af4c5ea3d" in workflow
    assert "a181c8949991bb139521f7d379046f34147e5306" in workflow
    assert "393c29711962bf1d42b8fc58322938c92e23000a" in workflow
    assert "51eef1fe2526801a467f155d1c0b32d516ef8a35" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "python -m devsystem.wnba_pra_repair_v1_step2_team_identity_cert" in workflow
    assert "WNBA_PRA_REPAIR_V1_STEP2_BRANCH_GREEN" in workflow
