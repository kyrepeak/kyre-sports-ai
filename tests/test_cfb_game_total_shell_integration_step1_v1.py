from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _source() -> str:
    return ROUTER.read_text(encoding="utf-8")


def _function(source: str, name: str, next_name: str | None = None) -> str:
    start = source.index(f"def {name}(")
    if next_name is None:
        return source[start:]
    end = source.index(f"def {next_name}(", start)
    return source[start:end]


def test_step1_page1_uses_shared_kyre_shell_and_four_cfb_markets() -> None:
    source = _source()

    assert "import streamlit_memory_lazy_router_v1 as root" in source
    assert 'CFB_SPORT_LABEL = "College Football"' in source
    assert 'CFB_SHELL_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")' in source
    assert "def _make_page1_selectbox_bridge(" in source
    assert '"🎯 CFB Market"' in source
    assert "list(CFB_SHELL_MARKETS)" in source


def test_step1_exact_game_total_renderer_keeps_v43_content_owner() -> None:
    source = _source()

    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v43"' in source
    assert "def _render_page1_game_total(" in source
    renderer = _function(source, "_render_page1_game_total", "_render_page1_in_shared_shell")
    assert "root._import(PAGE1_NATIVE_ROUTE)" in renderer
    assert "page.render_cfb_hub(" in renderer
    assert "root.section_header" in renderer
    assert "root.status_info" in renderer
    assert "root.team_logo" in renderer
    assert "root.h" in renderer


def test_step1_shell_bridge_restores_every_root_seam() -> None:
    source = _source()
    shell = _function(source, "_render_page1_in_shared_shell", "_render_native_page1")

    assert "original_selectbox = root.st.selectbox" in shell
    assert "original_render_nfl = root._render_nfl" in shell
    assert "original_prefixes = root._ROUTE_MODULE_PREFIXES" in shell
    assert "root.st.selectbox = _make_page1_selectbox_bridge(original_selectbox)" in shell
    assert "root._render_nfl = _make_page1_renderer_bridge(original_render_nfl)" in shell
    assert 'if "cfb_" not in root._ROUTE_MODULE_PREFIXES:' in shell
    assert "return root.render_app()" in shell
    assert "finally:" in shell
    assert "root.st.selectbox = original_selectbox" in shell
    assert "root._render_nfl = original_render_nfl" in shell
    assert "root._ROUTE_MODULE_PREFIXES = original_prefixes" in shell


def test_step1_non_game_total_cfb_selection_exits_direct_shell() -> None:
    source = _source()

    assert "def _make_page1_renderer_bridge(" in source
    renderer_bridge = _function(source, "_make_page1_renderer_bridge", "_render_page1_game_total")
    assert "if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:" in renderer_bridge
    assert "live_owner._clear_game_total_route_query()" in renderer_bridge
    assert "st.rerun()" in renderer_bridge
    assert "if sport != CFB_SPORT_LABEL:" in renderer_bridge
    assert "return delegate(market)" in renderer_bridge


def test_step1_only_active_game_total_page1_enters_shared_shell() -> None:
    source = _source()
    page1 = _function(source, "_render_native_page1", "_clear_auto_event_after_page1")

    assert "if not live_owner._game_total_route_active():" in page1
    assert "return frozen_parent.render_app()" in page1
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE1_NATIVE_ROUTE" in page1
    assert "return _render_page1_in_shared_shell()" in page1
    assert "cfb_router.GAME_TOTAL_PAGE = original_page1" in page1


def test_step1_selected_event_page2_ownership_is_unchanged() -> None:
    source = _source()
    render = _function(source, "render_app")

    assert "if not _selected_game_total():" in render
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in render
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in render
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in render
    assert "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in render
    assert "live_owner.ACTIVE_PAGE = original_live_page" in render
    assert "render_owner.ACTIVE_PAGE = original_render_page" in render


def test_step1_preserves_frozen_math_and_provider_boundaries() -> None:
    source = _source()

    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_MARKET_OWNERSHIP = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
