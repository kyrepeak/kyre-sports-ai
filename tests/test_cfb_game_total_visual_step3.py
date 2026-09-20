from __future__ import annotations

import cfb_game_total_clean_page_v26 as page
import streamlit_memory_lazy_router_v171 as router


def test_step3_game_total_analysis_contract() -> None:
    raw = {"projected_combined_total": 61.8}
    final = {
        "ready": True,
        "projected_combined_total": 62.6,
        "forecast_strength": 0.772,
        "grade": "A",
    }
    display_game = {"market_total": 52.5}
    html = page._game_total_analysis_html_v26(raw, final, display_game, {}, 6)

    assert 'data-testid="gt226-game-total-analysis"' in html
    assert page.STEP3_GAME_TOTAL_ANALYSIS_MARKER in html
    for expected in (
        "GAME TOTAL ANALYSIS",
        "Projected Total",
        "62.6",
        "Market Total",
        "52.5",
        "Over / Under Lean",
        "Over +10.1",
        "77.2%",
        "Data Check Progress",
        "6/12 ready",
        "5M Certified",
        "0.0% sportsbook projection influence",
    ):
        assert expected in html
    assert html.count("gt226-bar ready") == 6
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_step3_router_activates_v26_only_for_game_total() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v26"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v170"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
