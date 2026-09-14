from __future__ import annotations

from pathlib import Path

import pytest

import nfl_passing_yards_hub_v29 as page
import streamlit_memory_lazy_router_v122 as router


def _verified_ctx(*, team_id: str = "4", athlete_id: str = "3050481", abbr: str = "CIN", name: str = "Cincinnati Bengals", qb_name: str = "Joe Example") -> dict:
    return {
        "identity_verified": True,
        "team_id": team_id,
        "abbr": abbr,
        "team": name,
        "depth_source": "ESPN depth chart",
        "availability_alert": False,
        "qb1": {
            "athlete_id": athlete_id,
            "name": qb_name,
            "injury_status": "No listed injury",
        },
    }


def test_v29_is_additive_display_only_step2_over_frozen_v28():
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v28"
    assert page.VISUAL_BUILD_STEP == 2
    assert page.VISUAL_BUILD_TOTAL == 6
    assert page.DISPLAY_ONLY is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert "VISUAL PARITY STEP 2" in page.MODEL_VERSION


def test_exact_visual_requires_verified_numeric_team_and_athlete_ids():
    ready = page._exact_visual(_verified_ctx())
    assert ready["ready"] is True
    assert ready["team_id"] == "4"
    assert ready["athlete_id"] == "3050481"

    missing_team = _verified_ctx(team_id="")
    assert page._exact_visual(missing_team)["ready"] is False

    bad_athlete = _verified_ctx(athlete_id="not-an-id")
    assert page._exact_visual(bad_athlete)["ready"] is False

    unverified = _verified_ctx()
    unverified["identity_verified"] = False
    assert page._exact_visual(unverified)["ready"] is False


def test_matchup_map_requires_both_exact_verified_sides():
    away = _verified_ctx(team_id="27", athlete_id="111", abbr="TB", name="Tampa Bay Buccaneers")
    home = _verified_ctx(team_id="4", athlete_id="222", abbr="CIN", name="Cincinnati Bengals")

    mapping = page._matchup_map({"away": away, "home": home})
    assert mapping == {
        "27": {"opponent_abbr": "CIN", "venue_token": "@"},
        "4": {"opponent_abbr": "TB", "venue_token": "vs"},
    }

    home["identity_verified"] = False
    assert page._matchup_map({"away": away, "home": home}) == {}


def test_qb_hero_card_uses_certified_exact_id_visual_helpers(monkeypatch):
    ctx = _verified_ctx(qb_name="Joe Quarterback")
    monkeypatch.setattr(page.step1_ui, "_status_label", lambda *_: ("VERIFIED QB1", "identity verified"))
    monkeypatch.setattr(page.player_visual_ui, "_player_headshot_url", lambda visual: f"https://img.test/{visual['athlete_id']}.png")
    monkeypatch.setattr(page.team_visual_ui, "_team_logo_url", lambda visual: f"https://logo.test/{visual['team_id']}.png")

    html = page._qb_hero_card(ctx, False, {"opponent_abbr": "TB", "venue_token": "vs"})

    assert 'class="kpass29-card"' in html
    assert "Joe Quarterback" in html
    assert "CIN vs TB" in html
    assert "EXACT-ID QB1" in html
    assert "3050481" in html
    assert "ESPN Athlete ID" in html
    assert "ESPN Team ID" in html
    assert "https://img.test/3050481.png" in html
    assert "https://logo.test/4.png" in html
    assert "sportsbook projection influence 0.0%" in html


def test_visual_build_banner_matches_six_step_board():
    html = page._visual_build_banner()
    assert "Visual Parity Build" in html
    assert "VISUAL STEP 2 / 6" in html
    assert "V28 ENGINE FROZEN" in html
    assert "SPORTSBOOK 0%" in html


def test_render_restores_frozen_hooks_even_if_prior_renderer_raises(monkeypatch):
    original_identity = page.step7_ui.identity.resolve_matchup_identity
    original_qb_card = page.step1_ui._qb_card
    monkeypatch.setattr(page.st, "markdown", lambda *args, **kwargs: None)

    def boom():
        raise RuntimeError("stop after hooks are installed")

    monkeypatch.setattr(page.prior, "render_nfl_passing_yards_hub", boom)

    with pytest.raises(RuntimeError, match="stop after hooks"):
        page.render_nfl_passing_yards_hub()

    assert page.step7_ui.identity.resolve_matchup_identity is original_identity
    assert page.step1_ui._qb_card is original_qb_card


def test_router_v122_advances_only_passing(monkeypatch):
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

    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v121"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v29"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_router_direct_handler_rejects_non_passing_markets():
    with pytest.raises(RuntimeError, match="Passing Yards only"):
        router._render_nfl_v122("Receiving Yards")


def test_app_activates_v122_and_preserves_v121_rollback_heartbeat():
    text = Path("app.py").read_text()
    assert "FROZEN_V121_DEPLOYMENT_HEARTBEAT" in text
    assert "STREAMLIT_MAIN_V121_NFL_RECEIVING_YARDS_STEP10_FINAL_POLISH_SPEED_CERT_2026-09-13" in text
    assert "STREAMLIT_MAIN_V122_NFL_PASSING_YARDS_VISUAL_PARITY_STEP2_QB_HEROES_2026-09-13" in text
    assert "from streamlit_memory_lazy_router_v122 import record_bootstrap_import_ms, render_app" in text


def test_v29_does_not_own_passing_projection_or_market_math():
    source = Path("nfl_passing_yards_hub_v29.py").read_text()
    assert "nfl_passing_yards_projection" not in source
    assert "nfl_passing_yards_distribution" not in source
    assert "nfl_passing_yards_market_edge" not in source
    assert "FROZEN_PRIOR = \"nfl_passing_yards_hub_v28\"" in source
