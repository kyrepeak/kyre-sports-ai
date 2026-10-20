from datetime import datetime, timedelta, timezone

import nfl_daily_picks_command_center_v3 as page


NOW = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)


def test_spread_observation_builder_fails_closed_without_quote_age() -> None:
    unknown = {
        "sportsbook": "FanDuel",
        "away_spread": -3.0,
        "away_price": -110,
        "home_spread": 3.0,
        "home_price": -110,
        "age_seconds": None,
    }
    assert page._spread_observation_rows("g1", unknown, NOW) == ()


def test_spread_observation_builder_preserves_verified_age() -> None:
    fresh = {
        "sportsbook": "DraftKings",
        "away_spread": -2.5,
        "away_price": -105,
        "home_spread": 2.5,
        "home_price": -115,
        "age_seconds": 45.0,
    }
    rows = page._spread_observation_rows("g1", fresh, NOW)
    assert len(rows) == 2
    assert {row["side"] for row in rows} == {"AWAY", "HOME"}
    assert all(row["verified"] is True for row in rows)
    assert all(row["updated_at"] == NOW - timedelta(seconds=45) for row in rows)
    assert all(row["provider"] == "Kyre Sports API" for row in rows)
