from __future__ import annotations

from pathlib import Path

import cfb_game_total_clean_page_v25 as step2
import cfb_game_total_clean_page_v26 as step3
import cfb_game_total_clean_page_v27 as step4
import cfb_game_total_clean_page_v28 as step5
import streamlit_memory_lazy_router_v173 as router


def test_step6_final_visual_chain_is_frozen_and_active() -> None:
    assert step2.STEP2_MATCHUP_HERO_MARKER == "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP2_MATCHUP_HERO_ACTIVE"
    assert step3.STEP3_GAME_TOTAL_ANALYSIS_MARKER == "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP3_GAME_TOTAL_ANALYSIS_ACTIVE"
    assert step4.STEP4_TEAM_EVIDENCE_MARKER == "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP4_TEAM_EVIDENCE_ACTIVE"
    assert step5.STEP5_SYSTEM_POLISH_MARKER == "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP5_SYSTEM_POLISH_ACTIVE"

    assert step2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step3.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step5.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    assert step2.MAY_MODIFY_PROJECTION is False
    assert step3.MAY_MODIFY_PROJECTION is False
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step5.MAY_MODIFY_PROJECTION is False

    assert step5.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v27"
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v28"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v172"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_step6_responsive_contract_covers_all_green_surfaces() -> None:
    css = step5.STEP5_SYSTEM_POLISH_CSS

    for selector in (
        ".gt225-hero",
        ".gt226-wrap",
        ".gt227-section",
        ".gt226-card",
        ".gt227-card",
    ):
        assert selector in css

    assert "@media(max-width:760px)" in css
    assert "@media(max-width:560px)" in css
    assert ".gt225-hero{margin-top:0!important}" in css

    forbidden_hides = (
        ".gt225-hero{display:none",
        ".gt226-wrap{display:none",
        ".gt227-section{display:none",
    )
    for forbidden in forbidden_hides:
        assert forbidden not in css.replace(" ", "")


def test_step6_missing_data_remains_explicit_and_non_synthetic() -> None:
    identity = {"away": {"team": "Away"}, "home": {"team": "Home"}}
    html = step4._team_evidence_html_v27(identity, {}, {})

    assert "Pending" in html
    assert 'data-state="PENDING"' in html
    assert "Trending" not in html
    assert "Edge" not in html


def test_step6_app_boots_certified_game_total_router_successor() -> None:
    app_text = Path("app.py").read_text(encoding="utf-8")
    expected = "from streamlit_memory_lazy_router_v176 import record_bootstrap_import_ms, render_app"
    assert expected in app_text
