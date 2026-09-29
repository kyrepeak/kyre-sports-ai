from __future__ import annotations

from pathlib import Path


PAGE = Path("cfb_top_picks_page_v1.py").read_text(encoding="utf-8")
ROUTER = Path("streamlit_memory_lazy_router_v241.py").read_text(encoding="utf-8")
APP = Path("app.py").read_text(encoding="utf-8")


def test_step1_page_shell_matches_locked_top_picks_foundation():
    assert 'Top <span>Picks</span>' in PAGE
    assert "10 Best Daily College Football Picks" in PAGE
    assert ">Moneyline<" in PAGE
    assert ">Spread<" in PAGE
    assert ">Over/Under<" in PAGE
    assert 'data-testid="cfb-top-picks-step1-root"' in PAGE
    assert 'data-testid="cfb-top-picks-board-frame"' in PAGE


def test_step1_is_shell_only_no_pick_engine_or_probability_logic():
    forbidden = (
        "calculate_probability(",
        "rank_top_picks(",
        "matchup_history(",
        "toughness_score(",
        "sportsbook_probability",
    )
    assert all(token not in PAGE for token in forbidden)


def test_v241_is_additive_over_frozen_v240():
    assert "import streamlit_memory_lazy_router_v240 as prior" in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v240"' in ROUTER
    assert 'TOP_PICKS_MARKET = "Top Picks"' in ROUTER
    assert "MAY_MODIFY_EXISTING_CFB_PRODUCTS = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_v241_extends_cfb_market_options_without_replacing_existing_routes():
    assert "options = list(cfb_route_base.CFB_MARKETS)" in ROUTER
    assert "options.append(TOP_PICKS_MARKET)" in ROUTER
    assert "return prior.render_app()" in ROUTER
    assert "root._render_nfl = _render_cfb_top_picks_v241" in ROUTER


def test_app_boots_v241_and_keeps_v240_as_frozen_parent():
    assert "from streamlit_memory_lazy_router_v241 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V240" in APP


def test_top_picks_deep_link_contract_is_cfb_scoped():
    assert 'CFB_SPORT_LABEL = "College Football"' in ROUTER
    assert "ROUTE_QUERY_SPORT = cfb_route_base.ROUTE_QUERY_SPORT" in ROUTER
    assert "ROUTE_QUERY_MARKET = cfb_route_base.ROUTE_QUERY_MARKET" in ROUTER
    assert "_cold_top_picks_query_requested" in ROUTER
