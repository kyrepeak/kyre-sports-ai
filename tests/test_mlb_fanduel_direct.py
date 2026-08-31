from datetime import datetime, timezone

import pytest

from sports_api.collectors import mlb_fanduel_direct as mlb


def _runner(role, name, odds, handicap=0, selection_id=1):
    return {
        "runnerName": name,
        "runnerStatus": "ACTIVE",
        "selectionId": selection_id,
        "handicap": handicap,
        "result": {"type": role},
        "winRunnerOdds": {
            "americanDisplayOdds": {"americanOdds": odds, "americanOddsInt": odds}
        },
    }


def _market(name, market_id, runners, sort_priority):
    return {
        "marketId": market_id,
        "marketName": name,
        "marketStatus": "OPEN",
        "marketTime": "2026-08-31T23:41:00.000Z",
        "inPlay": False,
        "sortPriority": sort_priority,
        "runners": runners,
    }


def _event_page():
    return {
        "attachments": {
            "markets": {
                "m1": _market(
                    "Moneyline",
                    "734.1",
                    [
                        _runner("AWAY", "Milwaukee Brewers", -104, selection_id=29172),
                        _runner("HOME", "Chicago Cubs", -112, selection_id=29166),
                    ],
                    10,
                ),
                "m2": _market(
                    "Run Line",
                    "734.2",
                    [
                        _runner("AWAY", "Milwaukee Brewers", 152, -1.5, 29172),
                        _runner("HOME", "Chicago Cubs", -184, 1.5, 29166),
                    ],
                    20,
                ),
                "m3": _market(
                    "Total Runs",
                    "734.3",
                    [
                        _runner("OVER", "Over", -102, 9.5, 7017905),
                        _runner("UNDER", "Under", -120, 9.5, 7017906),
                    ],
                    30,
                ),
            }
        }
    }


def _schedule(*, second_game=False):
    games = [
        {
            "gamePk": 800001,
            "gameDate": "2026-08-31T23:41:00Z",
            "status": {"detailedState": "Scheduled"},
            "teams": {
                "away": {"team": {"id": 158, "name": "Milwaukee Brewers"}},
                "home": {"team": {"id": 112, "name": "Chicago Cubs"}},
            },
        }
    ]
    if second_game:
        games.append(
            {
                "gamePk": 800002,
                "gameDate": "2026-08-31T18:00:00Z",
                "status": {"detailedState": "Scheduled"},
                "teams": {
                    "away": {"team": {"id": 158, "name": "Milwaukee Brewers"}},
                    "home": {"team": {"id": 112, "name": "Chicago Cubs"}},
                },
            }
        )
    return {"dates": [{"date": "2026-08-31", "games": games}]}


def test_parse_fanduel_matchup_strips_probable_pitchers():
    away, home = mlb.parse_fanduel_matchup(
        "Milwaukee Brewers (K Harrison) @ Chicago Cubs (C Holmes)"
    )
    assert away == "Milwaukee Brewers"
    assert home == "Chicago Cubs"


def test_normalize_core_markets_uses_current_american_odds_and_lines():
    markets = list(_event_page()["attachments"]["markets"].values())
    normalized = mlb.normalize_core_markets(markets)

    assert normalized["moneyline"]["away_odds"] == -104
    assert normalized["moneyline"]["home_odds"] == -112
    assert normalized["run_line"]["away_line"] == -1.5
    assert normalized["run_line"]["away_odds"] == 152
    assert normalized["run_line"]["home_line"] == 1.5
    assert normalized["run_line"]["home_odds"] == -184
    assert normalized["total"]["line"] == 9.5
    assert normalized["total"]["over_odds"] == -102
    assert normalized["total"]["under_odds"] == -120


def test_reconcile_official_game_uses_start_time_for_doubleheader():
    game, method = mlb.reconcile_official_game(
        _schedule(second_game=True),
        away_team="Milwaukee Brewers",
        home_team="Chicago Cubs",
        sportsbook_start_utc="2026-08-31T23:41:00Z",
    )
    assert game["gamePk"] == 800001
    assert method == "teams_and_nearest_start"


def test_reconcile_official_game_fails_closed_when_teams_do_not_match():
    with pytest.raises(mlb.MLBMarketCollectorError, match="no official MLB schedule match"):
        mlb.reconcile_official_game(
            _schedule(),
            away_team="Detroit Tigers",
            home_team="Minnesota Twins",
            sportsbook_start_utc="2026-08-31T23:41:00Z",
        )


def test_collect_live_mlb_game_odds_normalizes_and_reconciles():
    landing = {
        "attachments": {
            "events": {
                "36004222": {
                    "eventId": 36004222,
                    "name": "Milwaukee Brewers (K Harrison) @ Chicago Cubs (C Holmes)",
                    "openDate": "2026-08-31T23:41:00.000Z",
                },
                "28197722": {
                    "eventId": 28197722,
                    "name": "MLB Player Markets",
                    "openDate": "2026-09-01T00:00:00.000Z",
                },
            }
        }
    }
    requested_dates = []

    report = mlb.collect_live_mlb_game_odds(
        now_utc=datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc),
        landing_fetcher=lambda: landing,
        event_fetcher=lambda event_id: _event_page(),
        schedule_fetcher=lambda slate_date: requested_dates.append(slate_date) or _schedule(),
    )

    assert requested_dates == ["2026-08-31"]
    assert report["provider"] == "FanDuel"
    assert report["transport"] == "anonymous_public_get_only"
    assert report["candidate_pregame_event_count"] == 1
    assert report["matched_game_count"] == 1
    assert report["fully_priced_game_count"] == 1

    game = report["games"][0]
    assert game["official_game_id"] == 800001
    assert game["sportsbook_event_id"] == "36004222"
    assert game["away_team"] == {"id": 158, "name": "Milwaukee Brewers"}
    assert game["home_team"] == {"id": 112, "name": "Chicago Cubs"}
    assert game["fully_priced"] is True
    assert game["markets"]["moneyline"]["away_odds"] == -104
    assert game["markets"]["run_line"]["home_line"] == 1.5
    assert game["markets"]["total"]["line"] == 9.5


def test_collect_rejects_unreconciled_event_instead_of_fabricating_game_id():
    landing = {
        "attachments": {
            "events": {
                "1": {
                    "eventId": 1,
                    "name": "Detroit Tigers @ Minnesota Twins",
                    "openDate": "2026-08-31T23:41:00Z",
                }
            }
        }
    }
    report = mlb.collect_live_mlb_game_odds(
        now_utc=datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc),
        landing_fetcher=lambda: landing,
        event_fetcher=lambda event_id: _event_page(),
        schedule_fetcher=lambda slate_date: _schedule(),
    )

    assert report["matched_game_count"] == 0
    assert report["games"] == []
    assert len(report["rejected_events"]) == 1
    assert "no official MLB schedule match" in report["rejected_events"][0]["reason"]
