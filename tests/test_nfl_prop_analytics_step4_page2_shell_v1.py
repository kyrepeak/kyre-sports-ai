from datetime import datetime, timezone
from pathlib import Path

import nfl_prop_analytics_matchup_shell_v1 as step4


def _handoff(key="CAR-CLE"):
    away, home = key.split("-")
    return {
        "version": "v1",
        "state": "ready",
        "selection_key": key,
        "away": away,
        "home": home,
        "away_name": away,
        "home_name": home,
        "target_date": "2026-09-27",
        "kickoff_utc": "2026-09-27T17:00:00+00:00",
        "week": 3,
        "network": "CBS",
        "venue": "Test Stadium",
        "game_id": key,
        "sources": ("NFL", "NFLVERSE"),
        "source_count": 2,
        "verified": True,
    }


def _game(key="CAR-CLE", verified=True):
    away, home = key.split("-")
    return {
        "away": away,
        "home": home,
        "away_name": away,
        "home_name": home,
        "kickoff_utc": datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc),
        "week": 3,
        "network": "CBS",
        "venue": "Test Stadium",
        "game_id": key,
        "sources": ("NFL", "NFLVERSE"),
        "source_count": 2,
        "verified": verified,
    }


def test_step4_contract_is_page2_shell_only():
    source = Path("nfl_prop_analytics_matchup_shell_v1.py").read_text()
    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 4 PAGE 2 MATCHUP SHELL"',
        "STEP = 4",
        "PAGE = 2",
        "SHELL_ONLY = True",
        "ROSTER_DATA_LOGIC = False",
        "PLAYER_PROP_LOGIC = False",
        "SPORTSBOOK_ODDS_LOGIC = False",
        "PROJECTION_LOGIC = False",
        'data-nfl-prop-analytics-step4-page2="v1"',
        'data-prop-page2-position-count="8"',
        'data-prop-page2-positions="QB,RB,WR,TE"',
    ):
        assert token in source, token


def test_position_shell_has_four_positions_per_team():
    html = step4._team_position_shell("CAR", "Panthers", "away")
    for position in ("QB", "RB", "WR", "TE"):
        assert f'data-prop-page2-position="{position}"' in html
    assert html.count('data-prop-page2-roster-state="pending"') == 4


def test_matchup_view_query_contract(monkeypatch):
    monkeypatch.setattr(step4, "_query_value", lambda key: "matchup")
    assert step4.is_matchup_page() is True

    monkeypatch.setattr(step4, "_query_value", lambda key: "")
    assert step4.is_matchup_page() is False


def test_session_handoff_wins_when_it_matches_query(monkeypatch):
    handoff = _handoff("CAR-CLE")
    monkeypatch.setattr(step4, "get_selected_game_handoff", lambda: handoff)
    monkeypatch.setattr(
        step4,
        "_query_value",
        lambda key: "CAR-CLE" if key == step4.GAME_QUERY_KEY else "matchup",
    )
    assert step4.resolve_matchup_handoff() == handoff


def test_deep_link_rebuilds_verified_handoff_without_session(monkeypatch):
    monkeypatch.setattr(step4, "get_selected_game_handoff", lambda: None)
    monkeypatch.setattr(
        step4,
        "_query_value",
        lambda key: "CIN-PIT" if key == step4.GAME_QUERY_KEY else "matchup",
    )
    monkeypatch.setattr(
        step4,
        "load_schedule_truth",
        lambda: {
            "target_date": "2026-09-27",
            "games": [
                _game("CAR-CLE", verified=True),
                _game("CIN-PIT", verified=True),
            ],
        },
    )
    handoff = step4.resolve_matchup_handoff()
    assert handoff is not None
    assert handoff["selection_key"] == "CIN-PIT"
    assert handoff["verified"] is True
    assert handoff["source_count"] == 2


def test_deep_link_fails_closed_for_unverified_game(monkeypatch):
    monkeypatch.setattr(step4, "get_selected_game_handoff", lambda: None)
    monkeypatch.setattr(
        step4,
        "_query_value",
        lambda key: "CIN-PIT" if key == step4.GAME_QUERY_KEY else "matchup",
    )
    monkeypatch.setattr(
        step4,
        "load_schedule_truth",
        lambda: {
            "target_date": "2026-09-27",
            "games": [_game("CIN-PIT", verified=False)],
        },
    )
    assert step4.resolve_matchup_handoff() is None


def test_step2_and_step3_product_modules_remain_dependencies_not_targets():
    source = Path("nfl_prop_analytics_matchup_shell_v1.py").read_text()
    assert "from nfl_prop_analytics_game_select_v1 import" in source
    assert "from nfl_prop_analytics_schedule_v1 import load_schedule_truth" in source

    step2 = Path("nfl_prop_analytics_schedule_v1.py").read_text()
    step3 = Path("nfl_prop_analytics_game_select_v1.py").read_text()
    assert 'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 2 SCHEDULE TRUTH"' in step2
    assert 'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 3 GAME SELECTION + MATCHUP HANDOFF"' in step3


def test_hub_routes_page2_before_rendering_page1():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    assert "if is_matchup_page():" in hub
    assert "render_matchup_shell()" in hub
    assert "handoff = render_game_selection_handoff()" in hub
    assert "render_matchup_open_control(handoff)" in hub
    assert hub.index("if is_matchup_page():") < hub.index("render_schedule_truth_layer()")


def test_step4_does_not_add_roster_prop_or_projection_data_logic():
    source = Path("nfl_prop_analytics_matchup_shell_v1.py").read_text().lower()
    forbidden = (
        "depth_chart",
        "player_stats",
        "sportsbook_line",
        "projection_model",
        "passing_yards_hub",
    )
    for token in forbidden:
        assert token not in source, token
