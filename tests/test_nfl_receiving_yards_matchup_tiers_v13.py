from __future__ import annotations

from pathlib import Path


def _helper():
    import nfl_receiving_yards_matchup_tiers_v2 as helper

    return helper


def test_exact_player_lookup_uses_espn_athlete_id_only() -> None:
    helper = _helper()
    team = {
        "players": [
            {"official_athlete_id": "4374302", "player_name": "Amon-Ra St. Brown"},
            {"official_athlete_id": "4430027", "player_name": "Sam LaPorta"},
        ]
    }
    assert helper.find_exact_player(team, "4374302")["player_name"] == "Amon-Ra St. Brown"
    assert helper.find_exact_player(team, "9999999") is None
    assert helper.find_exact_player(team, "Amon-Ra St. Brown") is None


def test_projection_yards_reuses_frozen_builder_result() -> None:
    helper = _helper()
    player = {
        "official_athlete_id": "4374302",
        "official_event_id": "401872932",
    }
    team = {"players": [player]}
    context = {"official_event_id": "401872932"}
    calls = []

    def builder(**kwargs):
        calls.append(kwargs)
        return {"ready": True, "projection_yards": 80.4}

    assert helper.projection_yards_for_athlete(
        context, team, "4374302", builder
    ) == 80.4
    assert len(calls) == 1
    assert calls[0]["official_event_id"] == "401872932"
    assert calls[0]["player"] is player
    assert "line" not in calls[0]
    assert "over_odds" not in calls[0]
    assert "under_odds" not in calls[0]


def test_projection_yards_fails_closed_without_certified_projection() -> None:
    helper = _helper()
    team = {"players": [{"official_athlete_id": "4374302"}]}

    assert helper.projection_yards_for_athlete(
        {}, team, "4374302", lambda **_: {"ready": False}
    ) is None
    assert helper.projection_yards_for_athlete(
        {}, team, "9999999", lambda **_: {"ready": True, "projection_yards": 99.0}
    ) is None


def test_exact_espn_visual_urls_are_identity_driven() -> None:
    helper = _helper()
    assert "4374302" in helper.headshot_url("4374302")
    assert "det" in helper.team_logo_url("DET").lower()
    assert helper.headshot_url("not-an-id") == ""


def test_v13_enriches_frozen_v9_matchup_tiers_without_new_projection_math() -> None:
    source = Path("nfl_receiving_yards_hub_v13.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v12"' in source
    assert 'FROZEN_MATCHUP_TIERS = "nfl_receiving_yards_hub_v9"' in source
    assert 'FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"' in source
    assert "projection_yards_for_athlete" in source
    assert "headshot_url" in source
    assert "team_logo_url" in source
    assert "team_name" in source
    assert "Projected Rec Yds" in source
    assert "MARKET ONLY" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "DISPLAY_ONLY = True" in source


def test_router_v144_advances_only_receiving_yards() -> None:
    source = Path("streamlit_memory_lazy_router_v144.py").read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v143"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v13"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_bootstraps_router_v144() -> None:
    source = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v144 import record_bootstrap_import_ms, render_app" in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V144_NFL_RECEIVING_YARDS_MATCHUP_TIERS_V2_2026-09-16"' in source
