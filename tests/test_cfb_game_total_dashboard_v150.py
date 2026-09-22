from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    path = ROOT / name
    assert path.exists(), f"missing required V150 file: {name}"
    return path.read_text(encoding="utf-8")


def test_game_total_clean_page_is_presentation_only_over_frozen_v3():
    source = _source("cfb_game_total_clean_page_v1.py")

    assert 'FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"' in source
    assert 'MARKET = "Game Total"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "frozen_page.slate.analyze_game" in source
    assert "frozen_page.final_model.rank_slate" in source
    assert "frozen_page.slate.scan_slate" in source


def test_game_total_dashboard_has_real_compact_visual_contract():
    source = _source("cfb_game_total_clean_page_v1.py")

    assert 'ZoneInfo("America/Phoenix")' in source
    assert "logo_v3.resolve_visuals" in source
    assert "GAME TOTAL • MONSTER DASHBOARD" in source
    assert "QUICK READ" in source
    assert "PHOENIX" in source
    assert "st.expander" in source
    assert "Deep evidence" in source
    assert "Run final Game Total Top-5 scan" in source
    assert "STEP 11" in source
    assert "STEP 12" in source


def test_game_total_dashboard_keeps_old_audit_out_of_top_level_render():
    source = _source("cfb_game_total_clean_page_v1.py")

    # The legacy audit remains available only behind an expander; V150 must not
    # call the frozen V3 render entry point, which recreates the giant old page.
    assert "frozen_page.render_game_total_hub(" not in source
    assert 'with st.expander("Deep evidence • certified team audit"' in source
    assert "frozen_page.frozen_v2.frozen_v1.team_ui._team_card" in source


def test_router_v150_targets_only_exact_cfb_game_total_and_freezes_v149():
    source = _source("streamlit_memory_lazy_router_v150.py")

    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v149"' in source
    assert 'CFB_SPORT_LABEL = "College Football"' in source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v1"' in source
    assert 'st.session_state.get("ks_sport_touch")' in source
    assert 'st.session_state.get("ks_cfb_market_touch")' in source
    assert "return prior.render_app()" in source
    assert "finally:" in source
    assert "root.st.selectbox = original_selectbox" in source
    assert "root._render_nfl = original_render_nfl" in source


def test_router_v150_does_not_write_over_under_query_state_for_game_total():
    source = _source("streamlit_memory_lazy_router_v150.py")

    # V77's persist helper always writes ks_cfb_market=Over/Under. Game Total
    # must clear that frozen fast-route query instead of corrupting refresh state.
    assert "cfb_route_base._persist_fast_route_query()" not in source
    assert "cfb_route_base._clear_fast_route_query()" in source


def test_app_bootstraps_router_v150_game_total_release():
    source = _source("app.py")

    assert (
        'FROZEN_V149_DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_COMPACT_DASHBOARD_2026-09-16"'
        in source
    )
    assert (
        'DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V150_CFB_GAME_TOTAL_MONSTER_COMPACT_DASHBOARD_2026-09-16"'
        in source
    )
    assert "from streamlit_memory_lazy_router_v150 import record_bootstrap_import_ms, render_app" in source


def test_router_v150_does_not_change_game_total_math_or_sportsbook_influence():
    source = _source("streamlit_memory_lazy_router_v150.py")

    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "cfb_game_total_model_v1" not in source
    assert "projected_combined_total =" not in source


def test_browser_qa_waits_for_named_cfb_market_selector_before_game_total_click():
    source = _source("devsystem/cfb_game_total_browser_qa_v1.py")

    assert 'CFB_MARKET_LABEL = "🎯 CFB Market"' in source
    assert 'get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True)' in source
    assert "cfb_market_combo.wait_for(" in source
    assert "if frame.get_by_role(\"combobox\").count() >= 2" not in source


def test_v150_handoff_does_not_rewrite_instantiated_cfb_market_widget_state():
    source = _source("streamlit_memory_lazy_router_v149.py")
    handoff = source.split("def _selectbox_v150_handoff", 1)[1].split(
        "def _restore_game_total_v150_from_query", 1
    )[0]

    assert 'st.session_state["ks_cfb_market_touch"] = GAME_TOTAL_MARKET' not in handoff
    assert "_persist_game_total_v150_query()" in handoff
