from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sports_api.collectors.nfl_fanduel_game_totals_v1 import (
    _extract_game_total,
    _reconcile_provider_event,
)


def _identity() -> dict:
    return {
        "kickoff": datetime(2026, 9, 20, 20, 25, tzinfo=timezone.utc),
        "away_values": {"arizona cardinals", "ari"},
        "home_values": {"san francisco 49ers", "sf"},
    }


def test_reconciliation_requires_exact_teams_and_kickoff() -> None:
    landing = {
        "attachments": {
            "events": {
                "fd-1": {
                    "eventId": "fd-1",
                    "name": "Arizona Cardinals @ San Francisco 49ers",
                    "openDate": "2026-09-20T20:25:00Z",
                },
                "wrong-teams": {
                    "eventId": "fd-2",
                    "name": "Seattle Seahawks @ San Francisco 49ers",
                    "openDate": "2026-09-20T20:25:00Z",
                },
                "wrong-kickoff": {
                    "eventId": "fd-3",
                    "name": "Arizona Cardinals @ San Francisco 49ers",
                    "openDate": "2026-09-20T22:25:00Z",
                },
            }
        }
    }

    assert _reconcile_provider_event(_identity(), landing) == "fd-1"


def test_reconciliation_fails_closed_on_ambiguity() -> None:
    landing = {
        "attachments": {
            "events": {
                "fd-1": {
                    "eventId": "fd-1",
                    "name": "Arizona Cardinals @ San Francisco 49ers",
                    "openDate": "2026-09-20T20:25:00Z",
                },
                "fd-2": {
                    "eventId": "fd-2",
                    "name": "Arizona Cardinals @ San Francisco 49ers",
                    "openDate": "2026-09-20T20:25:00Z",
                },
            }
        }
    }

    with pytest.raises(ValueError, match="reconciliation failed"):
        _reconcile_provider_event(_identity(), landing)


def test_extracts_one_open_pregame_full_game_total() -> None:
    payload = {
        "attachments": {
            "markets": {
                "m1": {
                    "marketId": "m1",
                    "eventId": "fd-1",
                    "marketName": "Total Points",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "lastUpdated": "2026-09-15T20:00:00Z",
                    "runners": [
                        {
                            "runnerName": "Over 47.5",
                            "handicap": 47.5,
                            "winRunnerOdds": {
                                "americanDisplayOdds": {"americanOdds": -110}
                            },
                        },
                        {
                            "runnerName": "Under 47.5",
                            "handicap": 47.5,
                            "winRunnerOdds": {
                                "americanDisplayOdds": {"americanOdds": -110}
                            },
                        },
                    ],
                }
            }
        }
    }

    market = _extract_game_total(payload, "fd-1")
    assert market == {
        "sportsbook": "fanduel",
        "total": 47.5,
        "over_price": -110,
        "under_price": -110,
        "market_id": "m1",
        "updated_at_utc": "2026-09-15T20:00:00Z",
        "active": True,
    }


def test_closed_total_fails_closed() -> None:
    payload = {
        "attachments": {
            "markets": {
                "m1": {
                    "marketId": "m1",
                    "eventId": "fd-1",
                    "marketName": "Total Points",
                    "marketStatus": "CLOSED",
                    "inPlay": False,
                    "runners": [],
                }
            }
        }
    }

    with pytest.raises(ValueError, match="exactly one open pregame"):
        _extract_game_total(payload, "fd-1")
