from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE1 = ROOT / "cfb_game_total_page1_daily_slate_v1.py"
PAGE1_CONTEXT = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py"
STEP9 = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1.py"
SAME_PAGE = ROOT / "cfb_game_total_page2_same_page_shell_repair_v1.py"
PAGE2 = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"
LIVE_DATA = ROOT / "cfb_game_total_page2_network_free_v2.py"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing required integration owner: {path.name}"
    return path.read_text(encoding="utf-8")


def test_page1_view_game_handoff_matches_selected_route_identity() -> None:
    page1 = _read(PAGE1)
    step9 = _read(STEP9)
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in page1
    assert 'SELECTOR_SYNC_QUERY_KEY = "ks_cfb_game_total_selector_sync"' in page1
    assert "EVENT_QUERY_KEY: event_id" in page1
    assert "SELECTOR_SYNC_QUERY_KEY: event_id" in page1
    assert "cfb_prior.EVENT_QUERY_KEY" in step9
    assert "cfb_prior.SELECTOR_SYNC_QUERY_KEY" in step9
    assert "if cfb_prior._query_value(cfb_prior.SELECTOR_SYNC_QUERY_KEY) != event_id:" in step9


def test_new_daily_slate_does_not_reopen_or_replace_selected_runtime() -> None:
    context = _read(PAGE1_CONTEXT)
    assert "MAY_MODIFY_SELECTED_GAME_RUNTIME = False" in context
    assert ".SAME_PAGE_RUNTIME =" not in context
    assert "page1_repair.PAGE1_REPAIR_ROUTE = PAGE1_DAILY_SLATE_ROUTE" in context
    assert "page1_repair.PAGE1_REPAIR_ROUTE = original_page1_route" in context


def test_selected_fast_path_still_targets_certified_complete_page2_stack() -> None:
    step9 = _read(STEP9)
    same_page = _read(SAME_PAGE)
    assert 'SAME_PAGE_RUNTIME = "cfb_game_total_page2_same_page_shell_repair_v1"' in step9
    assert "importlib.import_module(SAME_PAGE_RUNTIME)" in step9
    assert "return page.render_selected_in_shared_shell()" in step9
    assert "import cfb_game_total_page2_step8_final_runtime_v1 as page2" in same_page
    assert "import cfb_game_total_page2_network_free_v2 as live_data" in same_page
    assert "with live_data.install_page2_live_data_repair():" in same_page
    assert "page2._render_selected_page(" in same_page


def test_complete_page2_feature_bundle_remains_composed() -> None:
    page2 = _read(PAGE2)
    required_imports = (
        "cfb_game_total_page2_step2_matchup_hero_phx_v1 as step2",
        "cfb_game_total_page2_step3_integrated_flow_v1 as step3",
        "cfb_game_total_page2_step4_outlook_summary_v1 as step4",
        "cfb_game_total_page2_step5_team_snapshot_key_drivers_v1 as step5",
        "cfb_game_total_page2_step6_trends_scoring_breakdown_v1 as step6",
        "cfb_game_total_page2_step7_line_lab_best_bet_v1 as step7",
        "cfb_game_total_page2_stage5_best_bet_v1 as stage5",
        "cfb_game_total_page2_stage6_tough_favorable_v1 as stage6",
        "cfb_game_total_page2_data_quality_step8_v1 as data_quality",
    )
    for marker in required_imports:
        assert marker in page2
    assert "stage5.build_best_bet_html" in page2
    assert "stage6.build_tough_favorable_html" in page2
    assert "step7.build_line_lab_html" in page2
    assert "step5.build_team_snapshot_key_drivers_html" in page2
    assert "step6.build_trends_scoring_breakdown_html" in page2
    assert "data_quality.build_data_quality_strip_html" in page2


def test_selected_flow_keeps_fast_network_free_and_truthful_boundaries() -> None:
    same_page = _read(SAME_PAGE)
    live_data = _read(LIVE_DATA)
    page2 = _read(PAGE2)
    for source in (same_page, live_data, page2):
        assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    for marker in (
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False",
        "MAY_MODIFY_OTHER_SPORTS = False",
        "NETWORK_CALLS_ADDED = 0",
    ):
        assert marker in same_page
    assert "NETWORK_CALLS_ADDED = 0" in live_data
    assert "enrich_preloaded_payload" in live_data
    assert "No missing values estimated" in _read(ROOT / "cfb_game_total_page2_data_quality_step8_v1.py")


def test_full_flow_is_one_way_page1_to_selected_analysis_and_back() -> None:
    page1 = _read(PAGE1)
    page2 = _read(PAGE2)
    assert "View Game" in page1
    assert "← Back to Slate" in page2
    assert "target=\"_self\"" in page2
