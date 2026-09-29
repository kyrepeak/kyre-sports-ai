from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESP=(ROOT/"wnba_pra_responsive_v2_step6.py").read_text(encoding="utf-8")
ROUTER=(ROOT/"streamlit_memory_lazy_router_wnba_nav_v2_step6.py").read_text(encoding="utf-8")
NAV=(ROOT/"wnba_pra_navigation_v2_step1.py").read_text(encoding="utf-8")
S2=(ROOT/"wnba_pra_slate_v2_step2.py").read_text(encoding="utf-8")
S3=(ROOT/"wnba_pra_game_center_v2_step3.py").read_text(encoding="utf-8")
S4=(ROOT/"wnba_pra_player_intelligence_v2_step4.py").read_text(encoding="utf-8")
S5=(ROOT/"wnba_pra_performance_v2_step5.py").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")


def test_step6_three_viewport_zero_overflow_contract():
    assert "CERTIFIED_VIEWPORTS = (390, 768, 1440)" in RESP
    assert '"zero_horizontal_overflow_required": True' in RESP
    assert '"fresh_browser_session_per_viewport": True' in RESP
    assert 'data-wnba-nav-responsive-targets="390,768,1440"' in RESP
    for token in ("@media (max-width:900px)","@media (max-width:760px)","@media (max-width:430px)"):
        assert token in RESP


def test_step6_touch_focus_and_reduced_motion_contract():
    assert "MIN_TOUCH_TARGET_PX = 44" in RESP
    assert "min-height:{MIN_TOUCH_TARGET_PX}px !important" in RESP
    assert ":focus-visible" in RESP
    assert "@media (prefers-reduced-motion:reduce)" in RESP


def test_step6_state_and_back_contract_remains_frozen():
    for token in ("QUERY_PAGE","QUERY_GAME","QUERY_PLAYER","SESSION_PAGE","SESSION_GAME","SESSION_PLAYER"):
        assert token in NAV
    assert "query-first state, then session state" in NAV
    assert "if safe.page == PAGE_PLAYER:" in NAV
    assert "return NavigationState(page=PAGE_GAME, game_id=safe.game_id)" in NAV
    assert "return NavigationState()" in NAV


def test_step6_css_targets_all_three_frozen_page_surfaces():
    for token in (".wn2-card",".wn3-player",".wn3-metrics",".wn4-hero",".wn4-strip",".wn4-grid",".wn4-games"):
        assert token in RESP
    assert ".wn2-card" in S2
    assert ".wn3-player" in S3 and ".wn3-metrics" in S3
    assert ".wn4-hero" in S4 and ".wn4-strip" in S4 and ".wn4-grid" in S4


def test_step6_preserves_step5_transport_and_frozen_steps():
    assert '"step": "2/7"' in S2
    assert '"step": "3/7"' in S3
    assert '"step": "4/7"' in S4
    assert '"step": "5/7"' in S5
    assert '"native_on_click_single_rerun": True' in S5
    assert '"speculative_prefetch": False' in S5
    assert '"frozen_steps_1_through_5_modified": False' in RESP
    assert '"projection_math_changed": False' in RESP
    assert '"market_math_changed": False' in RESP
    assert '"sportsbook_projection_influence": 0.0' in RESP


def test_step6_router_and_app_activation():
    assert 'FROZEN_PERFORMANCE = "wnba_pra_performance_v2_step5"' in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in ROUTER
    assert "return frozen_renderer(market)" in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step6 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen WNBA Navigation V2 Step 5 compatibility" in APP
