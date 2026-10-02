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


def test_step3_opponent_is_selected_game_truth_not_consumer_top5():
    game = {
        "away_team_id": 1611661317,
        "away_team": "Phoenix Mercury",
        "away_tricode": "PHX",
        "home_team_id": 1611661328,
        "home_team": "Seattle Storm",
        "home_tricode": "SEA",
    }
    result = data.opponent_identity(game, 1611661317)
    assert result["ready"] is True
    assert result["opponent_team_key"] == "seattle-storm"


def test_step3_form_fallback_keeps_role_row_l5_l10():
    result = data.form_fallback({"l5_pra": 27.4, "l10_pra": 26.1})
    assert result["recent5_pra"] == 27.4
    assert result["recent10_pra"] == 26.1


def test_step3_weighted_usage_matches_existing_role_weights():
    result = data.weighted_usage(20.0, 22.0, 24.0)
    assert result is not None
    assert round(result, 4) == 21.5


def test_step3_helpers_are_pure():
    source = DATA.read_text(encoding="utf-8")
    assert ast.parse(source)
    for forbidden in ("import streamlit", "import requests", "import httpx"):
        assert forbidden not in source.lower()


def test_step3_composes_on_top_of_step2_not_directly_on_step9():
    source = OVERLAY.read_text(encoding="utf-8")
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity"' in source
    assert "import streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity as frozen_parent" in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION_MATH = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_QUALIFICATION = False" in source
    assert "MAY_MODIFY_RANKING = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step3_retains_context_fields_the_frozen_page_dropped():
    source = OVERLAY.read_text(encoding="utf-8")
    for token in (
        '"l10_pra": getter("L10_PRA")',
        '"l5_pra": getter("L5_PRA")',
        '"projected_usage": getter("PROJ_USG")',
        '"season_usage": getter("USG_PCT")',
        '"l10_usage": getter("L10_USG_PCT")',
        '"l5_usage": getter("L5_USG_PCT")',
        "data.opponent_identity(game, player_team_id)",
        "matchup.matchup_factors_v36",
        "_repair_history_summary",
    ):
        assert token in source


def test_step3_does_not_touch_frozen_app_activation():
    app = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity" in app
    assert "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness" not in app


def test_step3_cert_uses_v8_plan_and_chaos_contract():
    source = CERT.read_text(encoding="utf-8")
    assert "compile_execution_plan" in source
    assert "validate_execution_plan" in source
    assert "chaos_contract_self_test" in source
    assert "WNBA_PRA_REPAIR_V1_STEP3_V8_PLAN_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP3_V8_CHAOS_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP3_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP3_FROZEN" in source


def test_step3_ledger_records_component_freeze_and_step2a():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Repair V1"
    assert ledger["step"] == 3
    assert ledger["total_steps"] == 7
    assert ledger["status"] == "DONE"
    assert ledger["proof_mode"] == "MERGED_MAIN_COMPONENT"
    assert ledger["production_activation_deferred_to_step4"] is True
    assert ledger["protected"]["step1_load_audit"] is True
    assert ledger["protected"]["frozen_app_py"] is True
    assert ledger["two_a"]["one_active_problem"] is True
    assert ledger["two_a"]["one_active_branch"] is True
    assert ledger["two_a"]["one_active_pr_max"] == 1
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["action_log"]["head_chain_hash"] == "0" * 64


def test_step3_workflow_exact_scope_has_no_app_py_and_guards_parents():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA PRA Repair V1 Step 3 Data Completeness" in workflow
    assert "Enforce exact Step-3 component scope" in workflow
    assert "Verify frozen parent dependencies" in workflow
    assert "app.py" not in workflow
    assert "4e51bd0e0c631b71cf9af7a443038edbe1b7061c" in workflow
    assert "9e571c95a8dc5229e39dfa60fbcffa18afb38bc1" in workflow
    assert "a181c8949991bb139521f7d379046f34147e5306" in workflow
    assert "393c29711962bf1d42b8fc58322938c92e23000a" in workflow
    assert "51eef1fe2526801a467f155d1c0b32d516ef8a35" in workflow
    assert "merged-main-component" in workflow


def test_step3_execution_plan_is_bound_to_v8_and_current_main():
    plan = json.loads((ROOT / "devsystem/execution_plans/wnba-pra-repair-v1-step3-data-completeness.json").read_text(encoding="utf-8"))
    assert plan["version"] == "MONSTER_V8_EXECUTION_PLAN_COMPILER_V1"
    assert plan["base_main_sha"] == "5bdbe8548a3cc20db2100d2d6b458b49c6956521"
    assert plan["rollback_checkpoint_id"] == "rollback_anchor"
    assert plan["step_2a_required"] is True
    assert plan["mutation_authority"] is False
    assert plan["freeze_contract"]["exact_pr_head_proof"] is True
    assert plan["freeze_contract"]["merged_main_proof"] is True
    assert plan["freeze_contract"]["green_plus_frozen"] is True
