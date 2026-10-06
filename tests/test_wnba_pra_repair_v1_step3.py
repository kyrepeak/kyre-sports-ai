from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import wnba_pra_repair_v1_step3_data as data
from devsystem.upstream_blocker_short_circuit_v1 import evaluate_upstream_dependency

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "wnba_pra_repair_v1_step3_data.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
CERT = ROOT / "devsystem/wnba_pra_repair_v1_step3_data_completeness_cert.py"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-repair-v1-step3-data-completeness.json"
PLAN = ROOT / "devsystem/execution_plans/wnba-pra-repair-v1-step3-data-completeness.json"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-repair-v1-step3-data-completeness.yml"
APP = ROOT / "app.py"


def test_step3_upstream_step2_green_frozen_releases_downstream_proof():
    gate = evaluate_upstream_dependency("wnba-pra-repair-v1-step3-public")
    assert gate["status"] == "GREEN"
    assert gate["decision"] == "PROCEED_DOWNSTREAM_PROOF"
    assert gate["downstream_proof_allowed"] is True
    assert gate["upstream_owner"] == "wnba-pra-repair-v1-step2-team-identity"


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


def test_step3_runtime_is_activated_above_step2():
    app = APP.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP3_DATA_COMPLETENESS_RUNTIME" in app
    assert "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness import record_bootstrap_import_ms, render_app" in app
    assert "Frozen WNBA PRA Repair V1 Step 2 compatibility: from streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity import record_bootstrap_import_ms, render_app" in app


def test_step3_cert_cannot_freeze_from_source_only_proof():
    source = CERT.read_text(encoding="utf-8")
    assert "validate_execution_plan" in source
    assert "chaos_contract_self_test" in source
    assert "def source_only_result" in source
    assert '"green_plus_frozen_allowed": False' in source
    assert "def run_production" in source
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
    assert "WNBA_PRA_REPAIR_V1_STEP3_GREEN" in source
    assert "WNBA_PRA_REPAIR_V1_STEP3_FROZEN" in source


def test_step3_production_waits_for_canonical_player_ready_game_center():
    source = CERT.read_text(encoding="utf-8")
    assert "GAME_SETUP_TIMEOUT_SECONDS = 90.0" in source
    assert "PLAYER_SETUP_TIMEOUT_SECONDS = 90.0" in source
    assert "MAX_GAME_ATTEMPTS_PER_DATE = 2" in source
    assert "DEPLOYMENT_ATTEMPTS = 2" in source
    assert "DEPLOYMENT_RETRY_SECONDS = 5.0" in source
    assert 'timeout_seconds=GAME_SETUP_TIMEOUT_SECONDS' in source
    assert 'timeout_seconds=PLAYER_SETUP_TIMEOUT_SECONDS' in source
    assert "range(min(game_count, MAX_GAME_ATTEMPTS_PER_DATE))" in source
    assert "target_date = nav._find_game_date()" in source
    assert "for target_date in _candidate_dates()" not in source
    assert "_wait_game_shell(page)" not in source
    assert "canonical Game Center has no tappable player controls" in source


def test_step3_ledger_requires_merged_main_production_before_freeze():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Repair V1"
    assert ledger["step"] == 3
    assert ledger["total_steps"] == 7
    assert ledger["status"] == "DONE"
    assert ledger["proof_mode"] == "MERGED_MAIN_PRODUCTION_REQUIRED"
    assert ledger["v8"]["component_only_freeze_rejected"] is True
    assert ledger["v8"]["app_exact_head_thaw_required"] is True
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["freeze_exit"]["merged_main_production_proof_green_required"] is True
    assert ledger["green_plus_frozen_claimed"] is False


def test_step3_workflow_requires_app_activation_and_real_production_proof():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Enforce exact Step-3 scope" in workflow
    assert "app.py" in workflow
    assert "--source-only" in workflow
    assert "public-production:" in workflow
    assert "python -m playwright install chromium" in workflow
    assert "--production-url https://pickvault.streamlit.app" in workflow
    assert "merged-main-component" not in workflow


def test_step3_execution_plan_is_strong_and_bound_to_v8():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["version"] == "MONSTER_V8_EXECUTION_PLAN_COMPILER_V1"
    assert plan["base_main_sha"] == "5bdbe8548a3cc20db2100d2d6b458b49c6956521"
    assert plan["rollback_checkpoint_id"] == "rollback_anchor"
    assert plan["step_2a_required"] is True
    assert plan["mutation_authority"] is False
    assert "frozen_activation" in plan["topological_order"]
    assert "merged_main_proof" in plan["topological_order"]
    assert "freeze_release" in plan["topological_order"]
    assert "app.py" in plan["resource_plan"]["write_paths"]
    assert plan["freeze_contract"]["exact_pr_head_proof"] is True
    assert plan["freeze_contract"]["merged_main_proof"] is True
    assert plan["freeze_contract"]["green_plus_frozen"] is True


def test_step3_deep_navigation_preserves_universal_wnba_pra_shell_route():
    source = OVERLAY.read_text(encoding="utf-8")
    assert "import wnba_pra_navigation_v2_step1 as navigation" in source
    assert 'SHELL_SPORT_QUERY_KEY = "ks_jump_sport"' in source
    assert 'SHELL_MARKET_QUERY_KEY = "ks_jump_market"' in source
    assert 'SHELL_SPORT_SESSION_KEY = "ks_sport_touch"' in source
    assert 'SHELL_MARKET_SESSION_KEY = "ks_wnba_market_touch"' in source
    assert 'SHELL_SPORT_VALUE = "WNBA"' in source
    assert 'SHELL_MARKET_VALUE = "PRA"' in source
    assert "def _pin_deep_wnba_shell_route" in source
    assert "navigation.PAGE_GAME" in source
    assert "navigation.PAGE_PLAYER" in source
    assert "original_nav_query_writer = navigation._write_query" in source
    assert "navigation._write_query = stable_nav_query_writer" in source
    assert "navigation._write_query = original_nav_query_writer" in source


def test_step3_initial_slate_wait_accepts_off_day_before_real_game_date():
    source = CERT.read_text(encoding="utf-8")
    assert "def _wait_initial_slate_shell" in source
    assert "def _prime_wnba_pra_for_target_date" in source
    assert 'nav._step7_marker(frame, "slate").count() > 0' in source
    assert '"WNBA Slate" in body' in source
    assert '"No player/model prefetch" in body' in source
    assert 'frame.get_by_label("📅 Slate date", exact=True)' in source
    assert "frame, slate_seconds = _prime_wnba_pra_for_target_date(page, route_url)" in source
    assert "frame = nav._set_date_with_game(page, frame, target_date)" in source


def test_step3_ci_bridge_targets_speed9_imported_wait_alias(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    calls: list[tuple[str, str, float]] = []

    def frozen_wait(page, page_name: str, *, timeout_seconds: float):
        calls.append(("frozen", page_name, timeout_seconds))
        return page_name, timeout_seconds

    def offday_wait(page, *, timeout_seconds: float):
        calls.append(("offday", "slate", timeout_seconds))
        return "slate", timeout_seconds

    cert = SimpleNamespace(_wait_initial_slate_shell=offday_wait)
    speed9 = SimpleNamespace(_wait_page=frozen_wait)

    assert data.install_step3_proof_wait_alias(
        cert_module=cert,
        speed9_module=speed9,
    ) is True
    assert speed9._wait_page(object(), "slate", timeout_seconds=12.0) == ("slate", 12.0)
    assert speed9._wait_page(object(), "game", timeout_seconds=9.0) == ("game", 9.0)
    assert calls == [("offday", "slate", 12.0), ("frozen", "game", 9.0)]
    assert speed9._step3_offday_wait_alias_bridge_v1 is True


def test_step3_ci_bridge_resolves_python_m_cert_from_main_module(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    calls: list[tuple[str, str, float]] = []

    def frozen_wait(page, page_name: str, *, timeout_seconds: float):
        calls.append(("frozen", page_name, timeout_seconds))
        return page_name, timeout_seconds

    def offday_wait(page, *, timeout_seconds: float):
        calls.append(("offday", "slate", timeout_seconds))
        return "slate", timeout_seconds

    cert = SimpleNamespace(
        __spec__=SimpleNamespace(name=data.STEP3_CERT_MODULE),
        _wait_initial_slate_shell=offday_wait,
    )
    speed9 = SimpleNamespace(_wait_page=frozen_wait)

    monkeypatch.delitem(sys.modules, data.STEP3_CERT_MODULE, raising=False)
    monkeypatch.setitem(sys.modules, "__main__", cert)
    monkeypatch.setitem(
        sys.modules,
        "devsystem.wnba_pra_speed_v3_step9_final_cert",
        speed9,
    )

    assert data.install_step3_proof_wait_alias() is True
    assert speed9._wait_page(object(), "slate", timeout_seconds=12.0) == ("slate", 12.0)
    assert speed9._wait_page(object(), "game", timeout_seconds=9.0) == ("game", 9.0)
    assert calls == [("offday", "slate", 12.0), ("frozen", "game", 9.0)]
    assert speed9._step3_offday_wait_alias_bridge_v1 is True


def test_step3_ci_bridge_rejects_unrelated_main_module(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delitem(sys.modules, data.STEP3_CERT_MODULE, raising=False)
    monkeypatch.setitem(
        sys.modules,
        "__main__",
        SimpleNamespace(
            __spec__=SimpleNamespace(name="unrelated.module"),
            _wait_initial_slate_shell=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "devsystem.wnba_pra_speed_v3_step9_final_cert",
        SimpleNamespace(_wait_page=lambda *args, **kwargs: None),
    )

    assert data.install_step3_proof_wait_alias() is False


def test_step3_ci_bridge_is_disabled_in_public_runtime(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def frozen_wait(page, page_name: str, *, timeout_seconds: float):
        return page_name, timeout_seconds

    speed9 = SimpleNamespace(_wait_page=frozen_wait)
    cert = SimpleNamespace(_wait_initial_slate_shell=lambda *args, **kwargs: None)
    original = speed9._wait_page

    assert data.install_step3_proof_wait_alias(
        cert_module=cert,
        speed9_module=speed9,
    ) is False
    assert speed9._wait_page is original
