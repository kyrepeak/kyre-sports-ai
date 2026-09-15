import pytest
from fastapi import HTTPException

from sports_api.api import nfl_game_totals_games_v1 as games_api
from sports_api.collectors.nfl_game_totals_schedule_v1 import NFLGameTotalsScheduleError


DATE = "2026-09-20"


def _slate(venue_available=True):
    venue = {
        "available": venue_available,
        "name": "Highmark Stadium" if venue_available else None,
        "city": "Orchard Park" if venue_available else None,
        "state": "NY" if venue_available else None,
        "indoor": False if venue_available else None,
    }
    return {
        "schema_version": "nfl_game_totals_schedule_v1",
        "service": "Kyre Sports API",
        "sport": "nfl",
        "official_authority": "ESPN",
        "requested_date": DATE,
        "game_count": 1,
        "venue_available_count": int(venue_available),
        "venue_missing_count": int(not venue_available),
        "source": "fixture://espn",
        "games": [
            {
                "official_event_id": "401772714",
                "kickoff_utc": "2026-09-20T17:00:00+00:00",
                "status": {"state": "pre", "completed": False, "detail": "Scheduled", "pregame": True},
                "away": {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
                "home": {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"},
                "venue": venue,
                "neutral_site": False,
                "identity_policy": {
                    "official_authority": "ESPN",
                    "fuzzy_matching": False,
                    "synthetic_event_ids": False,
                    "synthetic_team_ids": False,
                },
            }
        ],
        "identity_policy": {
            "official_event_id_required": True,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_team_ids": False,
        },
    }


def test_games_metadata_contract_excludes_market_and_projection_data():
    contract = games_api.CONTRACT
    assert contract["exact_event_identity"] is True
    assert contract["sportsbook_data_included"] is False
    assert contract["projection_data_included"] is False
    assert contract["missing_venue_drops_game"] is False


def test_games_endpoint_returns_complete_verified_slate(monkeypatch):
    monkeypatch.setattr(games_api, "collect_official_nfl_slate", lambda date: _slate(True))
    payload = games_api.game_totals_games(DATE)
    assert payload["game_count"] == 1
    assert payload["games"][0]["official_event_id"] == "401772714"
    assert payload["games"][0]["venue"]["name"] == "Highmark Stadium"
    assert payload["metadata_contract"]["sportsbook_data_included"] is False


def test_games_endpoint_keeps_game_when_venue_is_missing(monkeypatch):
    monkeypatch.setattr(games_api, "collect_official_nfl_slate", lambda date: _slate(False))
    payload = games_api.game_totals_games(DATE)
    assert payload["game_count"] == 1
    assert payload["venue_missing_count"] == 1
    assert payload["games"][0]["venue"]["available"] is False


def test_games_endpoint_rejects_bad_date_before_network():
    with pytest.raises(HTTPException) as exc:
        games_api.game_totals_games("09-20-2026")
    assert exc.value.status_code == 422


def test_games_endpoint_converts_official_slate_failure_to_503(monkeypatch):
    def fail(date):
        raise NFLGameTotalsScheduleError("official ESPN unavailable")

    monkeypatch.setattr(games_api, "collect_official_nfl_slate", fail)
    with pytest.raises(HTTPException) as exc:
        games_api.game_totals_games(DATE)
    assert exc.value.status_code == 503
