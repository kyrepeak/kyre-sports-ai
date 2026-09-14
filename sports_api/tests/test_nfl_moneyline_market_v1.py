from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from sports_api.api import health
from sports_api.api import nfl_moneyline_market_v1 as api
from sports_api.collectors import nfl_fanduel_moneyline_v1 as collector


EVENT_ID = "401999001"
CAPTURED = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)


def _espn_summary():
    return {
        "header": {
            "id": EVENT_ID,
            "competitions": [
                {
                    "id": EVENT_ID,
                    "date": "2026-09-15T00:15:00Z",
                    "status": {"type": {"state": "pre", "completed": False}},
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {"id": "7", "abbreviation": "DEN", "displayName": "Denver Broncos"},
                        },
                        {
                            "homeAway": "home",
                            "team": {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
                        },
                    ],
                }
            ],
        }
    }


def _landing():
    return {
        "attachments": {
            "events": {
                "fd-event-1": {
                    "eventId": "fd-event-1",
                    "name": "Denver Broncos @ Kansas City Chiefs",
                    "openDate": "2026-09-15T00:15:00Z",
                }
            }
        }
    }


def _moneyline_market(*, away=-105, home=-115):
    return {
        "marketId": "ml-1",
        "eventId": "fd-event-1",
        "marketName": "Moneyline",
        "marketStatus": "OPEN",
        "inPlay": False,
        "sortPriority": 1,
        "runners": [
            {
                "runnerStatus": "ACTIVE",
                "result": {"type": "AWAY"},
                "selectionId": "away-selection",
                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": away}},
            },
            {
                "runnerStatus": "ACTIVE",
                "result": {"type": "HOME"},
                "selectionId": "home-selection",
                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": home}},
            },
        ],
    }


def _event_page(market=None):
    return {"attachments": {"markets": {"ml-1": market or _moneyline_market()}}}


def _payload():
    return collector.collect_fanduel_nfl_moneyline(
        EVENT_ID,
        now_utc=CAPTURED,
        espn_fetcher=lambda event_id: _espn_summary(),
        landing_fetcher=_landing,
        event_page_fetcher=lambda provider_event_id: _event_page(),
    )


def test_denver_kansas_city_exact_id_moneyline_chain():
    out = _payload()
    assert out["official_event_id"] == EVENT_ID
    assert out["identity"]["away_team_id"] == "7"
    assert out["identity"]["home_team_id"] == "12"
    assert out["identity"]["away_abbr"] == "DEN"
    assert out["identity"]["home_abbr"] == "KC"
    assert out["identity"]["provider_event_id"] == "fd-event-1"
    assert out["identity"]["fuzzy_matching"] is False
    assert out["identity"]["synthetic_event_ids"] is False
    assert out["market_semantics"]["projection_weight"] == 0.0
    assert out["market_semantics"]["may_modify_projection"] is False
    assert out["market_semantics"]["multi_book_capable"] is True
    assert len(out["books"]) == 1
    assert out["books"][0]["sportsbook"] == "FanDuel"
    assert out["books"][0]["away_ml"] == -105
    assert out["books"][0]["home_ml"] == -115


def test_default_moneyline_fetch_reuses_render_safe_espn_transport(monkeypatch):
    calls: list[str] = []

    def hosted(event_id: str):
        calls.append(event_id)
        return _espn_summary(), "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl"

    monkeypatch.setattr(collector, "fetch_espn_event_summary_hosted", hosted)
    out = collector.collect_fanduel_nfl_moneyline(
        EVENT_ID,
        now_utc=CAPTURED,
        landing_fetcher=_landing,
        event_page_fetcher=lambda provider_event_id: _event_page(),
    )
    assert calls == [EVENT_ID]
    assert out["official_event_id"] == EVENT_ID
    assert out["identity"]["away_team_id"] == "7"
    assert out["identity"]["home_team_id"] == "12"
    assert out["market_semantics"]["projection_weight"] == 0.0


def test_moneyline_requires_exactly_one_away_and_home_runner():
    broken = _moneyline_market()
    broken["runners"].append(deepcopy(broken["runners"][0]))
    with pytest.raises(collector.NFLMoneylineCollectorError):
        collector.normalize_moneyline_market(
            broken,
            official_event={
                "event_id": EVENT_ID,
                "away": {"team_id": "7", "abbr": "DEN"},
                "home": {"team_id": "12", "abbr": "KC"},
            },
            provider_event={"provider_event_id": "fd-event-1", "kickoff_delta_seconds": 0},
            captured_at_utc=CAPTURED,
        )


def test_closed_or_inplay_moneyline_fails_closed():
    closed = _moneyline_market()
    closed["marketStatus"] = "CLOSED"
    with pytest.raises(collector.NFLMoneylineCollectorError):
        collector.collect_fanduel_nfl_moneyline(
            EVENT_ID,
            now_utc=CAPTURED,
            espn_fetcher=lambda event_id: _espn_summary(),
            landing_fetcher=_landing,
            event_page_fetcher=lambda provider_event_id: _event_page(closed),
        )


def test_api_revalidates_identity_market_and_zero_projection_contract():
    out = api._validate_market_payload(_payload(), EVENT_ID)
    assert out["ready"] is True
    assert out["market_available"] is True
    assert out["book_count"] == 1
    assert out["books"][0]["away_ml"] == -105

    bad = _payload()
    bad["market_semantics"]["projection_weight"] = 0.01
    with pytest.raises(HTTPException) as exc:
        api._validate_market_payload(bad, EVENT_ID)
    assert exc.value.status_code == 503

    bad = _payload()
    bad["identity"]["fuzzy_matching"] = True
    with pytest.raises(HTTPException) as exc:
        api._validate_market_payload(bad, EVENT_ID)
    assert exc.value.status_code == 503


def test_api_rejects_duplicate_books_and_invalid_prices():
    bad = _payload()
    bad["books"].append(deepcopy(bad["books"][0]))
    with pytest.raises(HTTPException):
        api._validate_market_payload(bad, EVENT_ID)

    bad = _payload()
    bad["books"][0]["away_ml"] = 50
    with pytest.raises(HTTPException):
        api._validate_market_payload(bad, EVENT_ID)


def test_market_cache_is_short_lived_and_deep_copy_safe(monkeypatch):
    api._clear_market_snapshot_cache()
    payload = api._validate_market_payload(_payload(), EVENT_ID)
    monkeypatch.setattr(api, "collect_fanduel_nfl_moneyline", lambda event_id: deepcopy(payload))

    first = api._collect_or_reuse_market(EVENT_ID)
    first["books"][0]["away_ml"] = 999
    second = api._collect_or_reuse_market(EVENT_ID)
    assert second["books"][0]["away_ml"] == -105
    assert api.MARKET_SNAPSHOT_TTL_SECONDS == 10.0


def test_status_contract_and_shared_host_registration():
    status = api.moneyline_market_status()
    assert status["status"] == "ready"
    assert status["official_event_id_required"] is True
    assert status["fuzzy_matching"] is False
    assert status["synthetic_event_ids"] is False
    assert status["projection_weight"] == 0.0
    assert status["market_context_only"] is True
    assert status["model_probability_input"] is False
    assert status["stake_sizing_enabled"] is False
    assert status["wager_actions"] is False

    paths = [getattr(route, "path", "") for route in health.router.routes]
    assert paths.count("/api/v1/nfl/moneyline/market") == 1
    assert paths.count("/api/v1/nfl/moneyline/market/status") == 1
    assert "/api/v1/nfl/rushing-yards/market" in paths
    assert "/api/v1/nfl/receiving-yards/market" in paths
    assert "/api/v1/nfl/passing-yards" in paths
