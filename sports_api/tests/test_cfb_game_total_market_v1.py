from __future__ import annotations

from datetime import datetime, timezone

from sports_api.collectors.cfb_game_total_market_v1 import (
    match_market_rows_to_ncaa_games,
    normalize_fanduel_game_markets,
)


def _runner(role: str, *, handicap=None, odds=-110):
    row = {
        "runnerStatus": "ACTIVE",
        "result": {"type": role},
        "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": odds}},
    }
    if handicap is not None:
        row["handicap"] = handicap
    return row


def test_fanduel_quote_keeps_total_prices_spread_and_moneyline_together():
    payload = {
        "attachments": {
            "events": {
                "fd-1": {
                    "eventId": "fd-1",
                    "name": "Michigan State @ UCLA",
                    "openDate": "2026-10-24T19:30:00Z",
                }
            },
            "markets": {
                "tot": {
                    "marketId": "tot",
                    "eventId": "fd-1",
                    "marketName": "Total Points",
                    "marketStatus": "OPEN",
                    "runners": [
                        _runner("OVER", handicap=43.5, odds=-112),
                        _runner("UNDER", handicap=43.5, odds=-108),
                    ],
                },
                "sp": {
                    "marketId": "sp",
                    "eventId": "fd-1",
                    "marketName": "Spread",
                    "marketStatus": "OPEN",
                    "runners": [
                        _runner("AWAY", handicap=14.5, odds=-106),
                        _runner("HOME", handicap=-14.5, odds=-114),
                    ],
                },
                "ml": {
                    "marketId": "ml",
                    "eventId": "fd-1",
                    "marketName": "Moneyline",
                    "marketStatus": "OPEN",
                    "runners": [
                        _runner("AWAY", odds=520),
                        _runner("HOME", odds=-750),
                    ],
                },
            },
        }
    }
    rows = normalize_fanduel_game_markets(
        payload, observed_at_utc=datetime(2026, 10, 22, 7, 30, tzinfo=timezone.utc)
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["sportsbook"] == "FanDuel"
    assert row["total_line"] == 43.5
    assert row["over_price"] == -112
    assert row["under_price"] == -108
    assert row["away_spread"] == 14.5
    assert row["home_spread"] == -14.5
    assert row["away_moneyline"] == 520
    assert row["home_moneyline"] == -750


def test_matching_uses_canonical_ncaa_id_and_suppresses_duplicate_quote_rows():
    game = {
        "game_id": "ncaa-1",
        "away_team": "Michigan St.",
        "home_team": "UCLA",
        "kickoff_iso": "2026-10-24T19:30:00+00:00",
    }
    quote = {
        "sportsbook": "FanDuel",
        "provider_event_id": "fd-1",
        "provider_market_id": "tot",
        "away_team": "Michigan State",
        "home_team": "UCLA",
        "start_time_utc": "2026-10-24T19:30:00Z",
        "total_line": 43.5,
    }
    matched = match_market_rows_to_ncaa_games([game], [quote, dict(quote)])
    assert list(matched) == ["ncaa-1"]
    assert len(matched["ncaa-1"]) == 1
