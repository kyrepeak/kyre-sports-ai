from datetime import date, datetime, timezone
from pathlib import Path

import nfl_prop_analytics_schedule_v1 as schedule


def test_step2_contract_and_sources_are_independent():
    source = Path("nfl_prop_analytics_schedule_v1.py").read_text()

    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 2 SCHEDULE TRUTH"',
        "STEP = 2",
        "PAGE = 1",
        "SCHEDULE_ONLY = True",
        "PLAYER_PROP_LOGIC = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        'NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"',
        'ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"',
        'NFL_SCHEDULE_URL = "https://www.nfl.com/schedules/{season}/by-week/week-{week}"',
        'data-nfl-prop-analytics-step2-schedule="v1"',
        'data-prop-schedule-state="fail-closed"',
        "No unverified or fabricated games are being displayed.",
    ):
        assert token in source, token


def test_target_sunday_is_current_or_next_sunday():
    assert schedule._target_sunday(date(2026, 9, 25)) == date(2026, 9, 27)
    assert schedule._target_sunday(date(2026, 9, 27)) == date(2026, 9, 27)
    assert schedule._target_sunday(date(2026, 9, 28)) == date(2026, 10, 4)


def test_reconcile_requires_independent_evidence_for_verified():
    kickoff = datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc)
    target = date(2026, 9, 27)

    base = {
        "away": "KC",
        "home": "MIA",
        "kickoff_utc": kickoff,
        "season": 2026,
        "week": 3,
        "network": "CBS",
        "status": "scheduled",
        "venue": "",
        "game_id": "",
    }
    nfl = {**base, "source": "NFL"}
    espn = {**base, "source": "ESPN"}
    nflverse = {**base, "source": "NFLVERSE"}

    truth = schedule._reconcile_schedule(
        {"NFL": [nfl], "NFLVERSE": [nflverse], "ESPN": [espn]},
        target,
    )
    assert len(truth) == 1
    game = truth[0]
    assert game["verified"] is True
    assert game["source_count"] == 3
    assert game["sources"] == ("NFL", "NFLVERSE", "ESPN")
    assert game["away_name"] == "Chiefs"
    assert game["home_name"] == "Dolphins"

    single = schedule._reconcile_schedule(
        {"NFL": [], "NFLVERSE": [], "ESPN": [espn]},
        target,
    )
    assert len(single) == 1
    assert single[0]["verified"] is False
    assert single[0]["source_count"] == 1


def test_reconcile_does_not_call_conflicting_kickoff_verified():
    target = date(2026, 9, 27)
    nfl = schedule._game(
        away="Ravens",
        home="Cowboys",
        kickoff_utc=datetime(2026, 9, 27, 20, 25, tzinfo=timezone.utc),
        source="NFL",
        season=2026,
        week=3,
    )
    espn = schedule._game(
        away="BAL",
        home="DAL",
        kickoff_utc=datetime(2026, 9, 27, 21, 25, tzinfo=timezone.utc),
        source="ESPN",
        season=2026,
        week=3,
    )
    truth = schedule._reconcile_schedule(
        {"NFL": [nfl], "NFLVERSE": [], "ESPN": [espn]},
        target,
    )
    assert truth[0]["source_count"] == 2
    assert truth[0]["kickoff_consensus"] is False
    assert truth[0]["verified"] is False


def test_step1_route_owner_remains_intact_and_step2_is_additive():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    router = Path("streamlit_memory_lazy_router_v240.py").read_text()

    for token in (
        'data-nfl-prop-analytics-route="v1"',
        'data-prop-analytics-owner="nfl_prop_analytics_hub_v1"',
        'data-prop-analytics-step="1"',
        "ROUTE_ONLY = True",
        "render_schedule_truth_layer()",
    ):
        assert token in hub, token

    assert 'PROP_ANALYTICS_HUB = "nfl_prop_analytics_hub_v1"' in router
    assert "import streamlit_memory_lazy_router_v239 as prior" in router


def test_step2_does_not_add_prop_projection_or_passing_yards_logic():
    source = Path("nfl_prop_analytics_schedule_v1.py").read_text().lower()
    forbidden = (
        "evaluate_market(",
        "build_baseline_projection(",
        "collect_fanduel",
        "passing_yards_hub",
    )
    for token in forbidden:
        assert token not in source, token
