from __future__ import annotations

from pathlib import Path

import cfb_top_picks_page_v5 as page


PAGE = Path("cfb_top_picks_page_v5.py").read_text(encoding="utf-8")
ROUTER = Path("streamlit_memory_lazy_router_v245.py").read_text(encoding="utf-8")
APP = Path("app.py").read_text(encoding="utf-8")


def _row(rank: int = 1) -> dict:
    return {
        "rank": rank,
        "event_id": f"40123456{rank}",
        "away": "Away State",
        "away_abbr": "AWY",
        "home": "Home Tech",
        "home_abbr": "HME",
        "time": "Sat, 12:00 PM",
        "network": "ESPN",
        "market": "MONEYLINE",
        "pick": "Away State",
        "odds": "-145",
        "probability": 68,
        "probability_value": 0.68,
        "toughness": 3,
        "toughness_label": "Medium",
        "reliability": 0.82,
        "source": "Kyre model",
        "sportsbook_projection_weight": 0.0,
    }


def test_step5_is_thin_visual_layer_over_frozen_step4():
    assert "import cfb_top_picks_page_v4 as prior" in PAGE
    assert "prior.engine.build_top_picks(limit=10)" in PAGE
    assert "prior.details.build_pick_detail(selected_row, slate_day)" in PAGE
    assert "MAY_MODIFY_RANKING = False" in PAGE
    assert "MAY_MODIFY_HISTORY = False" in PAGE
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.HISTORY_PROJECTION_INFLUENCE == 0.0


def test_step5_page_html_adds_final_marker_without_removing_step4_contract():
    html = page._page_html([_row()], {"games_analyzed": 1}, "2026-10-03")
    assert 'data-testid="cfb-top-picks-step5-root"' in html
    assert 'data-cfb-top-picks-visual="v5"' in html
    assert "CFB_TOP_PICKS_STEP5_FINAL_VISUAL_ACTIVE" in html
    assert "CFB_TOP_PICKS_STEP4_DETAILS_ACTIVE" in html
    assert "CFB_TOP_PICKS_STEP3_LIVE_RANKING_ACTIVE" in html
    assert "CFB_TOP_PICKS_STEP2_COMPACT_CARDS_ACTIVE" in html
    assert "CFB_TOP_PICKS_STEP1_SHELL_ACTIVE" in html


def test_step5_css_has_phone_tablet_desktop_responsive_guards():
    assert "@media(max-width:1100px)" in PAGE
    assert "@media(max-width:900px)" in PAGE
    assert "@media(max-width:820px)" in PAGE
    assert "@media(max-width:640px)" in PAGE
    assert "overflow-x:clip" in PAGE
    assert "grid-template-columns:38px minmax(0,1fr) 62px 22px" in PAGE
    assert "#119dff" in page.CSS


def test_v245_routes_only_top_picks_and_delegates_everything_else():
    assert "import streamlit_memory_lazy_router_v244 as prior" in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v244"' in ROUTER
    assert 'TOP_PICKS_PAGE = "cfb_top_picks_page_v5"' in ROUTER
    assert "return prior.render_app()" in ROUTER
    assert "MAY_MODIFY_EXISTING_CFB_PRODUCTS = False" in ROUTER
    assert "MAY_MODIFY_RANKING = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER
    assert "HISTORY_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_app_activates_v245_and_retains_v244_compatibility():
    assert "from streamlit_memory_lazy_router_v245 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V244 compatibility" in APP
