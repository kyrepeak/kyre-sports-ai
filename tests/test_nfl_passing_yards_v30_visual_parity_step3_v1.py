from __future__ import annotations

from pathlib import Path

import pytest

import nfl_passing_yards_hub_v30 as page
import streamlit_memory_lazy_router_v123 as router


def _ctx() -> dict:
    return {
        "team": "Cincinnati Bengals",
        "abbr": "CIN",
        "team_id": "4",
        "qb1": {"name": "Joe Quarterback", "athlete_id": "3050481"},
    }


def _profile() -> dict:
    return {
        "ready": True,
        "athlete_id": "3050481",
        "season_http": 200,
        "gamelog_http": 200,
        "season": {
            "games": 3,
            "yards_per_game": 271.4,
            "attempts_per_game": 34.7,
            "yards_per_attempt": 7.82,
            "completion_pct": 68.3,
            "passing_yards": 814,
            "passing_tds": 6,
            "interceptions": 2,
        },
        "recent3_yards": 279.3,
        "recent5_yards": 263.8,
        "home_yards": 288.0,
        "away_yards": 255.0,
    }


def test_v30_is_additive_display_only_step3_over_frozen_v29():
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v29"
    assert page.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"
    assert page.VISUAL_BUILD_STEP == 3
    assert page.VISUAL_BUILD_TOTAL == 6
    assert page.DISPLAY_ONLY is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_profile_card_surfaces_frozen_profile_values_without_recomputing():
    html = page._profile_card_v30(_ctx(), _profile())

    assert 'class="kpass30-profile"' in html
    assert "Joe Quarterback • Passing Profile" in html
    assert "271.4" in html
    assert "Pass Yards / Game" in html
    assert "34.7" in html
    assert "Attempts / Game" in html
    assert "7.82" in html
    assert "Yards / Attempt" in html
    assert "68.3%" in html
    assert "814" in html
    assert "6" in html
    assert "2" in html
    assert "279.3" in html
    assert "263.8" in html
    assert "288.0" in html
    assert "255.0" in html
    assert "ESPN athlete 3050481" in html
    assert "profile math unchanged" in html
    assert "sportsbook projection influence 0.0%" in html


def test_profile_card_fail_soft_state_is_visible():
    html = page._profile_card_v30(
        {"team": "Team", "qb1": {"name": "QB", "athlete_id": "1"}},
        {"ready": False, "season": {}},
    )
    assert "PROFILE CHECK" in html
    assert "—" in html


def test_visual_build_banner_advances_to_step3_of6():
    html = page._visual_build_banner_v30()
    assert "Visual Parity Build" in html
    assert "VISUAL STEP 3 / 6" in html
    assert "V29 + V28 FROZEN" in html
    assert "SPORTSBOOK 0%" in html
    assert 'style="width:50%"' in html


def test_render_restores_profile_banner_and_css_even_on_failure(monkeypatch):
    original_profile = page.profile_ui._profile_card
    original_banner = page.prior._visual_build_banner
    original_css = page.prior._VISUAL_PARITY_CSS

    def boom():
        assert page.profile_ui._profile_card is page._profile_card_v30
        assert page.prior._visual_build_banner is page._visual_build_banner_v30
        assert page._STEP3_VISUAL_CSS in page.prior._VISUAL_PARITY_CSS
        raise RuntimeError("stop inside frozen V29")

    monkeypatch.setattr(page.prior, "render_nfl_passing_yards_hub", boom)
    with pytest.raises(RuntimeError, match="stop inside frozen V29"):
        page.render_nfl_passing_yards_hub()

    assert page.profile_ui._profile_card is original_profile
    assert page.prior._visual_build_banner is original_banner
    assert page.prior._VISUAL_PARITY_CSS == original_css


def test_router_v123_advances_only_passing(monkeypatch):
    called: list[str] = []

    monkeypatch.setattr(router, "_passing_route_active", lambda: True)
    monkeypatch.setattr(router, "_render_direct_passing", lambda: called.append("passing"))
    monkeypatch.setattr(router.prior, "render_app", lambda: called.append("prior"))
    router.render_app()
    assert called == ["passing"]

    called.clear()
    monkeypatch.setattr(router, "_passing_route_active", lambda: False)
    router.render_app()
    assert called == ["prior"]

    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v122"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v30"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_router_direct_handler_rejects_non_passing_markets():
    with pytest.raises(RuntimeError, match="Passing Yards only"):
        router._render_nfl_v123("Receiving Yards")


def test_app_activates_v123_and_preserves_v122_rollback():
    text = Path("app.py").read_text()
    assert "FROZEN_V122_DEPLOYMENT_HEARTBEAT" in text
    assert "STREAMLIT_MAIN_V122_NFL_PASSING_YARDS_VISUAL_PARITY_STEP2_QB_HEROES_2026-09-13" in text
    assert "STREAMLIT_MAIN_V123_NFL_PASSING_YARDS_VISUAL_PARITY_STEP3_QB_PROFILE_2026-09-13" in text
    assert "from streamlit_memory_lazy_router_v123 import record_bootstrap_import_ms, render_app" in text


def test_v30_does_not_own_projection_distribution_or_market_math():
    source = Path("nfl_passing_yards_hub_v30.py").read_text()
    assert "nfl_passing_yards_projection" not in source
    assert "nfl_passing_yards_distribution" not in source
    assert "nfl_passing_yards_market_edge" not in source
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v29"' in source
