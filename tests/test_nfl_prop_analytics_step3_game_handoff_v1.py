from datetime import datetime, timezone
from pathlib import Path

import nfl_prop_analytics_game_select_v1 as step3


def _game(away, home, verified=True, sources=("NFL", "NFLVERSE")):
    return {
        "away": away,
        "home": home,
        "away_name": away,
        "home_name": home,
        "kickoff_utc": datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc),
        "week": 3,
        "network": "CBS",
        "venue": "Test Stadium",
        "game_id": f"{away}-{home}-2026",
        "sources": sources,
        "source_count": len(sources),
        "verified": verified,
    }


def test_step3_contract_is_selection_only():
    source = Path("nfl_prop_analytics_game_select_v1.py").read_text()
    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 3 GAME SELECTION + MATCHUP HANDOFF"',
        "STEP = 3",
        "PAGE = 1",
        "SELECTION_ONLY = True",
        "PLAYER_PROP_LOGIC = False",
        "ROSTER_LOGIC = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        'data-nfl-prop-analytics-step3-selection="v1"',
        'data-prop-handoff-state="ready"',
        'data-prop-handoff-state="not-ready"',
    ):
        assert token in source, token


def test_only_verified_games_are_eligible():
    truth = {
        "games": [
            _game("BAL", "DAL", verified=True),
            _game("KC", "MIA", verified=False, sources=("ESPN",)),
            _game("LAR", "DEN", verified=True),
        ]
    }
    games = step3._eligible_games(truth)
    assert [(g["away"], g["home"]) for g in games] == [
        ("BAL", "DAL"),
        ("LAR", "DEN"),
    ]


def test_requested_game_wins_then_session_then_first():
    games = [_game("BAL", "DAL"), _game("KC", "MIA"), _game("LAR", "DEN")]
    assert step3._resolve_initial_index(games, "KC-MIA", "BAL-DAL") == 1
    assert step3._resolve_initial_index(games, "", "LAR-DEN") == 2
    assert step3._resolve_initial_index(games, "NOPE", "NOPE") == 0


def test_handoff_payload_is_complete_and_verified():
    game = _game("BAL", "DAL")
    handoff = step3.build_matchup_handoff(game, "2026-09-27")
    assert handoff["version"] == "v1"
    assert handoff["state"] == "ready"
    assert handoff["selection_key"] == "BAL-DAL"
    assert handoff["away"] == "BAL"
    assert handoff["home"] == "DAL"
    assert handoff["target_date"] == "2026-09-27"
    assert handoff["kickoff_utc"] == "2026-09-27T17:00:00+00:00"
    assert handoff["week"] == 3
    assert handoff["network"] == "CBS"
    assert handoff["venue"] == "Test Stadium"
    assert handoff["source_count"] == 2
    assert handoff["verified"] is True


def test_game_label_converts_utc_to_eastern():
    label = step3._game_label(_game("BAL", "DAL"))
    assert "1:00 PM ET" in label


def test_step2_module_remains_frozen_api_dependency():
    source = Path("nfl_prop_analytics_game_select_v1.py").read_text()
    schedule = Path("nfl_prop_analytics_schedule_v1.py").read_text()
    assert "from nfl_prop_analytics_schedule_v1 import load_schedule_truth" in source
    assert 'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 2 SCHEDULE TRUTH"' in schedule


def test_step3_does_not_add_roster_prop_or_projection_logic():
    source = Path("nfl_prop_analytics_game_select_v1.py").read_text().lower()
    forbidden = (
        "player_stats",
        "depth_chart",
        "sportsbook_line",
        "projection_model",
        "passing_yards_hub",
    )
    for token in forbidden:
        assert token not in source, token


def test_hub_renders_step2_before_step3():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    assert hub.index("render_schedule_truth_layer()") < hub.index("render_game_selection_handoff()")
    for token in (
        'data-nfl-prop-analytics-route="v1"',
        'data-prop-analytics-owner="nfl_prop_analytics_hub_v1"',
        'data-prop-analytics-step="1"',
    ):
        assert token in hub, token
