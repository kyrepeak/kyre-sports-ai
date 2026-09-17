from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_real_app_boots_v152_router() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v152 import record_bootstrap_import_ms, render_app" in app_source


def test_v152_router_exposes_production_heartbeat() -> None:
    router = ROOT / "streamlit_memory_lazy_router_v152.py"
    assert router.exists(), "V152 router does not exist yet"
    source = router.read_text(encoding="utf-8")
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"' in source
    assert "return prior.render_app()" in source


def test_v152_activation_keeps_sportsbook_and_model_frozen() -> None:
    router = ROOT / "streamlit_memory_lazy_router_v152.py"
    assert router.exists(), "V152 router does not exist yet"
    source = router.read_text(encoding="utf-8")
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v152_game_total_query_repairs_partial_session_state_on_widget_rerun() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
    assert "def _query_requests_game_total() -> bool:" in source
    restore = source.split("def _restore_game_total_route_from_query() -> bool:", 1)[1].split(
        "def _selectbox_v152(", 1
    )[0]
    assert "_query_requests_game_total()" in restore
    assert 'st.session_state["ks_sport_touch"] = CFB_SPORT_LABEL' in restore
    assert 'st.session_state["ks_cfb_market_touch"] = GAME_TOTAL_MARKET' in restore
    assert "current_sport or current_market" not in restore


def test_v152_selector_preserves_game_total_query_during_page_widget_reruns() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
    assert "def _selectbox_v152(" in source
    selector = source.split("def _selectbox_v152(", 1)[1].split(
        "def _render_production_heartbeat()", 1
    )[0]
    assert 'label == "🎯 NFL Market"' in selector
    assert "selected = str(selected)" in selector
    assert "if selected == GAME_TOTAL_MARKET:" in selector
    assert "_latch_game_total_route()" in selector
    assert "_persist_game_total_route_query()" in selector
    assert "elif selected == cfb_route_base.OVER_UNDER_MARKET:" in selector
    assert "_clear_game_total_route_latch()" in selector
    direct = source.split("def _render_direct_cfb_game_total() -> None:", 1)[1].split(
        "def render_app() -> None:", 1
    )[0]
    assert "root.st.selectbox = _selectbox_v152" in direct
    assert "root.st.selectbox = cfb_route_base._selectbox_v77" not in direct


def test_v152_route_latch_survives_page_reruns_but_clears_on_intentional_navigation() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
    assert 'ROUTE_LATCH_KEY = "cfb_game_total_v152_route_active"' in source
    assert "def _latch_game_total_route() -> None:" in source
    assert "def _clear_game_total_route_latch() -> None:" in source

    active = source.split("def _game_total_route_active() -> bool:", 1)[1].split(
        "def _persist_game_total_route_query()", 1
    )[0]
    assert "ROUTE_LATCH_KEY" in active
    assert 'st.session_state["ks_sport_touch"] = CFB_SPORT_LABEL' in active
    assert 'st.session_state["ks_cfb_market_touch"] = GAME_TOTAL_MARKET' in active
    assert "_clear_game_total_route_latch()" in active

    selector = source.split("def _selectbox_v152(", 1)[1].split(
        "def _render_production_heartbeat()", 1
    )[0]
    assert "_latch_game_total_route()" in selector
    assert "_clear_game_total_route_latch()" in selector

    renderer = source.split("def _render_cfb_game_total_v152(market: str) -> None:", 1)[1].split(
        "def _render_direct_cfb_game_total()", 1
    )[0]
    assert "_clear_game_total_route_latch()" in renderer


def test_v152_final_repaired_evidence_steps_are_ready_together() -> None:
    import cfb_game_total_clean_page_v6 as page
    import cfb_game_total_runtime_display_v1 as runtime

    payload = runtime._load_game_total_snapshot()
    game = (payload.get("games") or [])[0]
    display_game, away, home, diag = runtime._apply_deterministic_snapshot(
        {
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "game_date": game["game_date"],
        },
        {},
        {},
        game,
    )
    statuses = page._existing_step_status(
        {"away": {"exact_identity": True}, "home": {"exact_identity": True}},
        away,
        home,
        display_game,
    )

    assert {step: statuses[step] for step in (4, 5, 6, 7, 9, 10)} == {
        4: "READY",
        5: "READY",
        6: "READY",
        7: "READY",
        9: "READY",
        10: "READY",
    }
    assert diag["game_total_deterministic_snapshot_used"] is True
