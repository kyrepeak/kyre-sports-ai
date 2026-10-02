from __future__ import annotations

import ast
import json
from pathlib import Path

import wnba_pra_repair_v1_step3_data as data

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "wnba_pra_repair_v1_step3_data.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
CERT = ROOT / "devsystem/wnba_pra_repair_v1_step3_data_completeness_cert.py"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-repair-v1-step3-data-completeness.json"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-repair-v1-step3-data-completeness.yml"
APP = ROOT / "app.py"


def test_step3_canonical_opponent_is_independent_of_consumer_card():
    game = {
        "away_team_id": 1611661317,
        "away_team": "Phoenix Mercury",
        "away_tricode": "PHX",
        "home_team_id": 1611661328,
        "home_team": "Seattle Storm",
        "home_tricode": "SEA",
    }
    away = data.opponent_identity(game, 1611661317)
    home = data.opponent_identity(game, 1611661328)
    assert away["ready"] is True
    assert away["opponent_team_key"] == "seattle-storm"
    assert home["ready"] is True
    assert home["opponent_team_key"] == "phoenix-mercury"


def test_step3_form_fallback_uses_verified_role_row_aggregates_only():
    result = data.form_fallback(
        {
            "l5_pra": 27.4,
            "l10_pra": 26.1,
            "l5_minutes": 32.2,
            "l5_points": 18.0,
            "l5_rebounds": 5.8,
            "l5_assists": 3.6,
        }
    )
    assert result == {
        "recent5_pra": 27.4,
        "recent10_pra": 26.1,
        "recent5_minutes": 32.2,
        "recent5_points": 18.0,
        "recent5_rebounds": 5.8,
        "recent5_assists": 3.6,
    }


def test_step3_weighted_usage_matches_frozen_role_weights():
    result = data.weighted_usage(20.0, 22.0, 24.0)
    assert result is not None
    assert round(result, 4) == 21.5


def test_step3_helpers_are_pure_and_do_not_import_model_or_network_runtime():
    source = DATA.read_text(encoding="utf-8")
    assert ast.parse(source)
    for forbidden in (
        "import streamlit",
        "import requests",
        "import httpx",
        "wnba_pra_matchup",
        "wnba_role",
        "sportsbook",
        "monte_carlo",
    ):
        assert forbidden not in source.lower()


def test_step3_overlay_preserves_frozen_parent_and_model_math():
    source = OVERLAY.read_text(encoding="utf-8")
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"' in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION_MATH = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_QUALIFICATION = False" in source
    assert "MAY_MODIFY_RANKING = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "matchup.matchup_factors_v36" in source


def test_step3_overlay_retains_usage_and_recent_form_without_modifying_frozen_page():
    source = OVERLAY.read_text(encoding="utf-8")
    for token in (
        '"l10_pra": getter("L10_PRA")',
        '"l5_pra": getter("L5_PRA")',
        '"projected_usage": getter("PROJ_USG")',
        '"season_usage": getter("USG_PCT")',
        '"l10_usage": getter("L10_USG_PCT")',
        '"l5_usage": getter("L5_USG_PCT")',
        "_repair_history_summary",
        'label == "Opponent key"',
        'label == "Exact pace adjustment"',
        'label == "Exact usage projection"',
    ):
        assert token in source


def test_step3_overlay_restores_every_monkeypatch_after_render():
    source = OVERLAY.read_text(encoding="utf-8")
    assert "game_center._record_from_role_row = original_record" in source
    assert "player_intelligence._history_summary = original_history" in source
    assert "player_intelligence._row = original_row" in source
    assert "player_intelligence.render_player_intelligence = original_player_renderer" in source


def test_step3_app_activates_overlay_and_keeps_step9_compatibility():
    app = APP.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP3_DATA_COMPLETENESS_RUNTIME" in app
    assert "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness import record_bootstrap_import_ms, render_app" in app
    assert "Frozen WNBA PRA Speed V3 Step 9 compatibility: from streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard import record_bootstrap_import_ms, render_app" in app


def test_step3_cert_requires_all_page3_context_fields_green():
    source = CERT.read_text(encoding="utf-8")
    for attr in (
        "data-opponent-ready",
        "data-recent5-ready",
        "data-recent10-ready",
        "data-usage-ready",
        "data-pace-ready",
        "data-history-opponent-linked",
        "data-consumer-independent-context",
    ):
        assert attr in source
    for token in (
        "WNBA_PRA_REPAIR_V1_STEP3_OPPONENT_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP3_RECENT_FORM_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP3_USAGE_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP3_PACE_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP3_H2H_LINK_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP3_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP3_FROZEN",
    ):
        assert token in source


def test_step3_ledger_enforces_step2a_and_protects_prior_green_work():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Repair V1"
    assert ledger["step"] == 3
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


def test_step3_workflow_has_exact_scope_and_frozen_blob_guards():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA PRA Repair V1 Step 3 Data Completeness" in workflow
    assert "Enforce exact Step-3 scope" in workflow
    assert "Verify frozen WNBA PRA dependencies" in workflow
    assert "a181c8949991bb139521f7d379046f34147e5306" in workflow
    assert "393c29711962bf1d42b8fc58322938c92e23000a" in workflow
    assert "51eef1fe2526801a467f155d1c0b32d516ef8a35" in workflow
    assert "python -m devsystem.wnba_pra_repair_v1_step3_data_completeness_cert" in workflow
    assert "WNBA_PRA_REPAIR_V1_STEP3_BRANCH_GREEN" in workflow
