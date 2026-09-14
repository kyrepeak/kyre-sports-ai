from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from sports_api.api import health
from sports_api.api import nfl_spread_market_v1 as api
from sports_api.collectors import nfl_fanduel_spread_v1 as collector


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


def _spread_market(*, away_spread=3.5, home_spread=-3.5, away_price=-110, home_price=-110):
    return {
        "marketId": "spread-1",
        "eventId": "fd-event-1",
        "marketName": "Spread",
        "marketStatus": "OPEN",
        "inPlay": False,
        "sortPriority": 1,
        "runners": [
            {
                "runnerStatus": "ACTIVE",
                "result": {"type": "AWAY"},
                "selectionId": "away-selection",
                "handicap": away_spread,
                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": away_price}},
            },
            {
                "runnerStatus": "ACTIVE",
                "result": {"type": "HOME"},
                "selectionId": "home-selection",
                "handicap": home_spread,
                "winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": home_price}},
            },
        ],
    }


def _event_page(market=None):
    return {"attachments": {"markets": {"spread-1": market or _spread_market()}}}


def _payload():
    return collector.collect_fanduel_nfl_spread(
        EVENT_ID,
        now_utc=CAPTURED,
        espn_fetcher=lambda event_id: _espn_summary(),
        landing_fetcher=_landing,
        event_page_fetcher=lambda provider_event_id: _event_page(),
    )


def test_denver_kansas_city_exact_id_spread_chain():
    out = _payload()
    assert out["schema_version"] == "nfl_spread_market_v1"
    assert out["market"] == "spread"
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
    assert out["market_semantics"]["model_probability_input"] is False
    assert out["market_semantics"]["multi_book_capable"] is True
    assert len(out["books"]) == 1
    book = out["books"][0]
    assert book["sportsbook"] == "FanDuel"
    assert book["away_spread"] == 3.5
    assert book["home_spread"] == -3.5
    assert book["away_price"] == -110
    assert book["home_price"] == -110


def test_default_spread_fetch_reuses_render_safe_espn_transport(monkeypatch):
    calls: list[str] = []

    def hosted(event_id: str):
        calls.append(event_id)
        return _espn_summary(), "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl"

    monkeypatch.setattr(collector, "fetch_espn_event_summary_hosted", hosted)
    out = collector.collect_fanduel_nfl_spread(
        EVENT_ID,
        now_utc=CAPTURED,
        landing_fetcher=_landing,
        event_page_fetcher=lambda provider_event_id: _event_page(),
    )
    assert calls == [EVENT_ID]
    assert out["official_event_id"] == EVENT_ID
    assert out["market_semantics"]["projection_weight"] == 0.0


def test_spread_requires_exactly_one_away_and_home_runner():
    broken = _spread_market()
    broken["runners"].append(deepcopy(broken["runners"][0]))
    with pytest.raises(collector.NFLSpreadCollectorError):
        collector.normalize_spread_market(
            broken,
            official_event={
                "event_id": EVENT_ID,
                "away": {"team_id": "7", "abbr": "DEN"},
                "home": {"team_id": "12", "abbr": "KC"},
            },
            provider_event={"provider_event_id": "fd-event-1", "kickoff_delta_seconds": 0},
            captured_at_utc=CAPTURED,
        )


def test_spread_pair_must_be_opposites():
    broken = _spread_market(away_spread=3.5, home_spread=-2.5)
    with pytest.raises(collector.NFLSpreadCollectorError):
        collector.collect_fanduel_nfl_spread(
            EVENT_ID,
            now_utc=CAPTURED,
            espn_fetcher=lambda event_id: _espn_summary(),
            landing_fetcher=_landing,
            event_page_fetcher=lambda provider_event_id: _event_page(broken),
        )


def test_closed_or_inplay_spread_fails_closed():
    closed = _spread_market()
    closed["marketStatus"] = "CLOSED"
    with pytest.raises(collector.NFLSpreadCollectorError):
        collector.collect_fanduel_nfl_spread(
            EVENT_ID,
            now_utc=CAPTURED,
            espn_fetcher=lambda event_id: _espn_summary(),
            landing_fetcher=_landing,
            event_page_fetcher=lambda provider_event_id: _event_page(closed),
        )

    live = _spread_market()
    live["inPlay"] = True
    with pytest.raises(collector.NFLSpreadCollectorError):
        collector.collect_fanduel_nfl_spread(
            EVENT_ID,
            now_utc=CAPTURED,
            espn_fetcher=lambda event_id: _espn_summary(),
            landing_fetcher=_landing,
            event_page_fetcher=lambda provider_event_id: _event_page(live),
        )


def test_api_revalidates_identity_line_price_and_zero_projection_contract():
    out = api._validate_market_payload(_payload(), EVENT_ID)
    assert out["ready"] is True
    assert out["market_available"] is True
    assert out["book_count"] == 1
    assert out["books"][0]["away_spread"] == 3.5

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

    bad = _payload()
    bad["books"][0]["home_spread"] = -2.5
    with pytest.raises(HTTPException) as exc:
        api._validate_market_payload(bad, EVENT_ID)
    assert exc.value.status_code == 503


def test_api_rejects_duplicate_books_and_invalid_prices():
    bad = _payload()
    bad["books"].append(deepcopy(bad["books"][0]))
    with pytest.raises(HTTPException):
        api._validate_market_payload(bad, EVENT_ID)

    bad = _payload()
    bad["books"][0]["away_price"] = 50
    with pytest.raises(HTTPException):
        api._validate_market_payload(bad, EVENT_ID)


def test_market_cache_is_short_lived_and_deep_copy_safe(monkeypatch):
    api._clear_market_snapshot_cache()
    payload = api._validate_market_payload(_payload(), EVENT_ID)
    monkeypatch.setattr(api, "collect_fanduel_nfl_spread", lambda event_id: deepcopy(payload))

    first = api._collect_or_reuse_market(EVENT_ID)
    first["books"][0]["away_spread"] = 99.0
    second = api._collect_or_reuse_market(EVENT_ID)
    assert second["books"][0]["away_spread"] == 3.5
    assert api.MARKET_SNAPSHOT_TTL_SECONDS == 10.0


def test_status_contract_and_shared_host_registration():
    status = api.spread_market_status()
    assert status["status"] == "ready"
    assert status["market"] == "spread"
    assert status["official_event_id_required"] is True
    assert status["fuzzy_matching"] is False
    assert status["synthetic_event_ids"] is False
    assert status["projection_weight"] == 0.0
    assert status["market_context_only"] is True
    assert status["model_probability_input"] is False
    assert status["stake_sizing_enabled"] is False
    assert status["wager_actions"] is False

    paths = [getattr(route, "path", "") for route in health.router.routes]
    assert paths.count("/api/v1/nfl/spread/market") == 1
    assert paths.count("/api/v1/nfl/spread/market/status") == 1
    assert paths.count("/api/v1/nfl/moneyline/market") == 1
    assert "/api/v1/nfl/rushing-yards/market" in paths
    assert "/api/v1/nfl/receiving-yards/market" in paths
    assert "/api/v1/nfl/passing-yards" in paths
