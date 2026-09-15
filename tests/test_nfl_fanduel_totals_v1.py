from datetime import datetime, timezone

import pytest

from sports_api.collectors.nfl_fanduel_totals_v1 import (
    NFLGameTotalsCollectorError,
    collect_fanduel_nfl_game_total,
    normalize_game_totals_market,
)


EVENT_ID = "401772714"
PROVIDER_EVENT_ID = "fd-9001"
NOW = datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc)


def _official_event():
    return {
        "event_id": EVENT_ID,
        "kickoff_utc": datetime(2026, 9, 20, 17, 0, tzinfo=timezone.utc),
        "away": {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
        "home": {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"},
    }


def _provider_event():
    return {
        "provider_event_id": PROVIDER_EVENT_ID,
        "provider_event_name": "Detroit Lions @ Buffalo Bills",
        "kickoff_utc": datetime(2026, 9, 20, 17, 0, tzinfo=timezone.utc),
        "away_team_id": "8",
        "home_team_id": "2",
        "away_abbr": "DET",
        "home_abbr": "BUF",
        "kickoff_delta_seconds": 0,
    }


def _runner(role, handicap, odds):
    return {
        "runnerStatus": "ACTIVE",
        "handicap": handicap,
        "result": {"type": role},
        "winRunnerOdds": {
            "americanDisplayOdds": {"americanOddsInt": odds}
        },
    }


def _market(total=48.5):
    return {
        "marketId": "m-total-1",
        "eventId": PROVIDER_EVENT_ID,
        "marketName": "Total Points",
        "marketStatus": "OPEN",
        "inPlay": False,
        "runners": [
            _runner("OVER", total, -110),
            _runner("UNDER", total, -110),
        ],
    }


def _summary():
    return {
        "header": {
            "id": EVENT_ID,
            "competitions": [
                {
                    "id": EVENT_ID,
                    "date": "2026-09-20T17:00:00Z",
                    "status": {"type": {"state": "pre", "completed": False}},
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {
                                "id": "8",
                                "abbreviation": "DET",
                                "displayName": "Detroit Lions",
                            },
                        },
                        {
                            "homeAway": "home",
                            "team": {
                                "id": "2",
                                "abbreviation": "BUF",
                                "displayName": "Buffalo Bills",
                            },
                        },
                    ],
                }
            ],
        }
    }


def _landing():
    return {
        "attachments": {
            "events": [
                {
                    "eventId": PROVIDER_EVENT_ID,
                    "name": "Detroit Lions @ Buffalo Bills",
                    "openDate": "2026-09-20T17:00:00Z",
                }
            ]
        }
    }


def _event_page(markets=None):
    return {"attachments": {"markets": list(markets or [_market()])}}


def test_normalize_game_total_freezes_line_prices_identity_and_safety():
    payload = normalize_game_totals_market(
        _market(),
        official_event=_official_event(),
        provider_event=_provider_event(),
        captured_at_utc=NOW,
    )
    assert payload["schema_version"] == "nfl_game_totals_market_v1"
    assert payload["market"] == "game_total"
    assert payload["official_event_id"] == EVENT_ID
    assert payload["ready"] is True
    assert payload["market_available"] is True
    assert payload["identity"]["away_team_id"] == "8"
    assert payload["identity"]["home_team_id"] == "2"
    assert payload["identity"]["fuzzy_matching"] is False
    assert payload["identity"]["synthetic_event_ids"] is False
    book = payload["books"][0]
    assert book["sportsbook"] == "FanDuel"
    assert book["total"] == 48.5
    assert book["over_price"] == -110
    assert book["under_price"] == -110
    assert book["line_status"] == "active"
    semantics = payload["market_semantics"]
    assert semantics["projection_weight"] == 0.0
    assert semantics["market_context_only"] is True
    assert semantics["may_modify_projection"] is False
    assert semantics["model_probability_input"] is False
    assert semantics["stake_sizing_enabled"] is False
    assert semantics["wager_actions"] is False


def test_collect_game_total_uses_exact_event_identity_network_free():
    payload = collect_fanduel_nfl_game_total(
        EVENT_ID,
        now_utc=NOW,
        espn_fetcher=lambda event_id: _summary(),
        landing_fetcher=lambda: _landing(),
        event_page_fetcher=lambda provider_event_id: _event_page(),
    )
    assert payload["official_event_id"] == EVENT_ID
    assert payload["identity"]["provider_event_id"] == PROVIDER_EVENT_ID
    assert payload["identity"]["kickoff_delta_seconds"] == 0
    assert payload["books"][0]["total"] == 48.5


def test_game_total_fails_closed_when_over_under_lines_disagree():
    market = _market()
    market["runners"][1]["handicap"] = 49.5
    with pytest.raises(NFLGameTotalsCollectorError, match="line mismatch"):
        normalize_game_totals_market(
            market,
            official_event=_official_event(),
            provider_event=_provider_event(),
            captured_at_utc=NOW,
        )


def test_game_total_fails_closed_on_duplicate_canonical_markets():
    with pytest.raises(NFLGameTotalsCollectorError, match="exactly one"):
        collect_fanduel_nfl_game_total(
            EVENT_ID,
            now_utc=NOW,
            espn_fetcher=lambda event_id: _summary(),
            landing_fetcher=lambda: _landing(),
            event_page_fetcher=lambda provider_event_id: _event_page([_market(), _market()]),
        )


def test_game_total_fails_closed_on_non_numeric_official_event_id():
    with pytest.raises(NFLGameTotalsCollectorError, match="must be numeric"):
        collect_fanduel_nfl_game_total("fake-event")
