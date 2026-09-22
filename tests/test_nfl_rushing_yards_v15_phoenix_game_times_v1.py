from pathlib import Path

import nfl_rushing_yards_hub_v1 as frozen_v1
import nfl_rushing_yards_hub_v14 as frozen_v14
import nfl_rushing_yards_hub_v15 as page
import streamlit_memory_lazy_router_v110 as frozen_router
import streamlit_memory_lazy_router_v111 as router


def _row(*, game_date="2026-09-13", tip_et="1:00 PM ET", state="pre", status="9/13 - 1:00 PM EDT"):
    return {
        "game_id": "401872925",
        "game_date": game_date,
        "tip_et": tip_et,
        "state": state,
        "status": status,
        "season_type": "Regular Season",
        "away_team": "Tampa Bay Buccaneers",
        "away_abbr": "TB",
        "away_logo": "",
        "away_record": "0-0",
        "away_score": "",
        "home_team": "Cincinnati Bengals",
        "home_abbr": "CIN",
        "home_logo": "",
        "home_record": "0-0",
        "home_score": "",
        "venue": "Paycor Stadium",
        "broadcast": "FOX",
    }


def test_v15_is_display_only_over_frozen_v14():
    assert page.FROZEN_PRIOR == "nfl_rushing_yards_hub_v14"
    assert page.DISPLAY_ONLY is True
    assert page.TIMEZONE_DISPLAY_ONLY is True
    assert page.PHOENIX_TZ_NAME == "America/Phoenix"
    assert page.PHOENIX_TZ_LABEL == "MST"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert frozen_v14.FROZEN_PRIOR == "nfl_rushing_yards_hub_v13"


def test_september_edth_kickoff_converts_to_phoenix_mst():
    labels = page._phoenix_kickoff(_row())
    assert labels == {
        "clock": "10:00 AM MST",
        "clock_with_location": "10:00 AM MST • Phoenix",
        "status": "9/13 - 10:00 AM MST",
        "date": "2026-09-13",
        "timezone": "America/Phoenix",
    }


def test_january_est_kickoff_uses_two_hour_phoenix_difference():
    labels = page._phoenix_kickoff(
        _row(game_date="2026-01-04", tip_et="1:00 PM ET", status="1/4 - 1:00 PM EST")
    )
    assert labels is not None
    assert labels["clock"] == "11:00 AM MST"
    assert labels["status"] == "1/4 - 11:00 AM MST"


def test_pregame_game_card_replaces_both_visible_et_time_surfaces():
    html = page._phoenix_game_card_v15(_row())
    assert "10:00 AM MST • Phoenix" in html
    assert "9/13 - 10:00 AM MST" in html
    assert "1:00 PM ET" not in html
    assert "1:00 PM EDT" not in html
    assert "Paycor Stadium" in html
    assert "Tampa Bay Buccaneers" in html
    assert "Cincinnati Bengals" in html


def test_live_status_is_preserved_while_clock_remains_phoenix_time():
    html = page._phoenix_game_card_v15(
        _row(state="in", status="2nd 05:21")
    )
    assert "2nd 05:21" in html
    assert "10:00 AM MST • Phoenix" in html
    assert "9/13 - 10:00 AM MST" not in html


def test_tbd_time_fails_closed_to_frozen_card():
    row = _row(tip_et="TBD", status="Scheduled")
    assert page._phoenix_kickoff(row) is None
    assert page._phoenix_game_card_v15(row) == frozen_v1._game_card(row)


def test_v15_patches_only_game_card_and_restores(monkeypatch):
    original = frozen_v1._game_card
    observed = []

    def fake_render():
        observed.append(frozen_v1._game_card is page._phoenix_game_card_v15)

    monkeypatch.setattr(frozen_v14, "render_nfl_rushing_yards_hub", fake_render)
    page.render_nfl_rushing_yards_hub()
    assert observed == [True]
    assert frozen_v1._game_card is original


def test_v15_source_contains_no_model_or_market_rebuild():
    source = Path("nfl_rushing_yards_hub_v15.py").read_text().lower()
    assert "build_event_projections" not in source
    assert "fetch_event_market" not in source
    assert "projection_weight" not in source
    assert "probability" not in source
    assert "fair_odds" not in source
    assert "expected_value" not in source
    assert "recommendation" not in source
    assert "stake" not in source
    assert "wager" not in source


def test_router_v111_advances_only_rushing_active_page():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v110"
    assert router.ACTIVE_PAGE == "nfl_rushing_yards_hub_v15"
    assert router.RUSHING_YARDS_MARKET == frozen_router.RUSHING_YARDS_MARKET == "Rushing Yards"


def test_router_v111_restores_v110_active_page(monkeypatch):
    original = frozen_router.ACTIVE_PAGE
    observed = []

    def fake_render():
        observed.append(frozen_router.ACTIVE_PAGE)

    monkeypatch.setattr(frozen_router, "render_app", fake_render)
    router.render_app()
    assert observed == ["nfl_rushing_yards_hub_v15"]
    assert frozen_router.ACTIVE_PAGE == original


def test_app_activates_v111_and_preserves_v110_heartbeat():
    source = Path("app.py").read_text()
    assert "streamlit_memory_lazy_router_v111 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V110_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V110_NFL_RUSHING_YARDS_DETAILED_MATCHUP_TIERS_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V111_NFL_RUSHING_YARDS_PHOENIX_GAME_TIMES_2026-09-13"' in source
