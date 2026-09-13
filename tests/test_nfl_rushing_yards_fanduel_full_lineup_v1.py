from pathlib import Path

import nfl_rushing_yards_hub_v11 as frozen_v11
import nfl_rushing_yards_hub_v12 as page
import streamlit_memory_lazy_router_v107 as frozen_router
import streamlit_memory_lazy_router_v108 as router


def _prop(*, athlete_id: str, team_id: str, name: str, line: float, over: int, under: int, position: str = "RB") -> dict:
    return {
        "official_event_id": "401872925",
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "player_name": name,
        "position": position,
        "market_type": "rushing_yards",
        "line": line,
        "over_odds": over,
        "under_odds": under,
        "sportsbook": "FanDuel",
        "line_status": "active",
    }


def test_v12_is_visual_market_context_only_over_frozen_v11():
    assert page.FROZEN_PRIOR == "nfl_rushing_yards_hub_v11"
    assert page.DISPLAY_ONLY is True
    assert page.MARKET_CONTEXT_ONLY is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert frozen_v11.FROZEN_PRIOR == "nfl_rushing_yards_hub_v10"


def test_full_lineup_includes_projected_and_market_only_players(monkeypatch):
    context = {
        "ready": True,
        "teams": [
            {"official_team_id": "4", "team_abbreviation": "CIN"},
            {"official_team_id": "23", "team_abbreviation": "PIT"},
        ],
    }
    event_market = {
        "ready": True,
        "market_available": True,
        "age_seconds": 4.0,
        "props": [
            _prop(
                athlete_id="4362238",
                team_id="4",
                name="Chase Brown",
                line=56.5,
                over=-114,
                under=-114,
            ),
            _prop(
                athlete_id="4426468",
                team_id="23",
                name="Kenny Gainwell",
                line=22.5,
                over=-113,
                under=-113,
            ),
        ],
    }
    monkeypatch.setattr(page, "_projected_athlete_ids", lambda _: {"4362238"})

    html = page._lineup_board_html(context, event_market)

    assert 'aria-label="Full FanDuel Rushing Yards lineup"' in html
    assert "2 LIVE PROPS" in html
    assert "Chase Brown" in html
    assert "56.5" in html
    assert "ESPN athlete 4362238" in html
    assert "PROJECTION AVAILABLE" in html
    assert "Kenny Gainwell" in html
    assert "22.5" in html
    assert "ESPN athlete 4426468" in html
    assert "MARKET ONLY • NO PROJECTION" in html
    assert "projection influence <strong>0.0%</strong>" in html


def test_market_only_card_does_not_invent_projection_values(monkeypatch):
    context = {
        "ready": True,
        "teams": [{"official_team_id": "23", "team_abbreviation": "PIT"}],
    }
    event_market = {
        "ready": True,
        "market_available": True,
        "props": [
            _prop(
                athlete_id="4426468",
                team_id="23",
                name="Kenny Gainwell",
                line=22.5,
                over=-113,
                under=-113,
            )
        ],
    }
    monkeypatch.setattr(page, "_projected_athlete_ids", lambda _: set())

    html = page._lineup_board_html(context, event_market)

    assert "Kenny Gainwell" in html
    assert "22.5" in html
    assert "MARKET ONLY • NO PROJECTION" in html
    assert "PROJECTED RUSH YARDS" not in html.upper()
    assert "EXPECTED CARRIES" not in html.upper()
    assert "EXPECTED YPC" not in html.upper()
    assert "PROJ − LINE" not in html.upper()


def test_lineup_fails_closed_without_fresh_available_market():
    assert page._lineup_board_html({}, {}) == ""
    assert page._lineup_board_html({}, {"ready": False, "market_available": True}) == ""
    assert page._lineup_board_html({}, {"ready": True, "market_available": False}) == ""
    assert page._lineup_board_html({}, {"ready": True, "market_available": True, "props": []}) == ""


def test_invalid_identity_rows_are_not_rendered(monkeypatch):
    monkeypatch.setattr(page, "_projected_athlete_ids", lambda _: set())
    event_market = {
        "ready": True,
        "market_available": True,
        "props": [
            _prop(
                athlete_id="not-an-id",
                team_id="4",
                name="Bad Athlete",
                line=10.5,
                over=-110,
                under=-110,
            ),
            _prop(
                athlete_id="4362238",
                team_id="bad-team",
                name="Bad Team",
                line=10.5,
                over=-110,
                under=-110,
            ),
        ],
    }
    assert page._lineup_board_html({"ready": True, "teams": []}, event_market) == ""


def test_v12_patches_only_v4_context_board_and_restores_in_finally():
    source = Path("nfl_rushing_yards_hub_v12.py").read_text()
    assert "compact_page._render_context_board_v4" in source
    assert "prior.render_nfl_rushing_yards_hub()" in source
    assert "finally:" in source
    assert "compact_page._render_context_board_v4 = original_context_board" in source
    assert "market_page._load_rushing_market(event_id)" in source
    assert "build_event_projections(context)" in source
    assert "projection_weight" not in source.lower() or "0.0" in source


def test_v12_introduces_no_identity_shortcuts_or_betting_actions():
    source = Path("nfl_rushing_yards_hub_v12.py").read_text().lower()
    assert "fuzzy" not in source
    assert "synthetic" not in source
    assert "player_name_matching" not in source
    assert "probability_enabled = true" not in source
    assert "fair_odds_enabled = true" not in source
    assert "ev_enabled = true" not in source
    assert "grading_enabled = true" not in source
    assert "stake_sizing_enabled = true" not in source
    assert "wager_actions = true" not in source


def test_router_v108_advances_only_rushing_active_page():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v107"
    assert router.ACTIVE_PAGE == "nfl_rushing_yards_hub_v12"
    assert router.RUSHING_YARDS_MARKET == frozen_router.RUSHING_YARDS_MARKET == "Rushing Yards"


def test_router_v108_restores_v107_active_page(monkeypatch):
    original = frozen_router.ACTIVE_PAGE
    observed = []

    def fake_render():
        observed.append(frozen_router.ACTIVE_PAGE)

    monkeypatch.setattr(frozen_router, "render_app", fake_render)
    router.render_app()
    assert observed == ["nfl_rushing_yards_hub_v12"]
    assert frozen_router.ACTIVE_PAGE == original


def test_app_activates_v108_and_preserves_v107_heartbeat():
    source = Path("app.py").read_text()
    assert "streamlit_memory_lazy_router_v108 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V107_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V107_NFL_RUSHING_YARDS_HTML_RENDER_REPAIR_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V108_NFL_RUSHING_YARDS_FANDUEL_FULL_LINEUP_2026-09-12"' in source
