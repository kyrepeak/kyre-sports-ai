from datetime import date

from runless_v2 import nba_pra_market_v1 as api


def _dk_rows():
    stamp = "2026-10-24T01:00:00Z"
    base = {
        "provider": "DraftKings",
        "provider_event_id": "evt-1",
        "provider_market_id": "mkt-1",
        "provider_player_id": "player-1",
        "player_name": "Test Player",
        "sportsbook": "DraftKings",
        "line": 34.5,
        "observed_at_utc": stamp,
        "away_team": "Miami Heat",
        "home_team": "Charlotte Hornets",
    }
    return [
        {**base, "side": "over", "price": -110},
        {**base, "side": "under", "price": -110},
    ]


def test_fanduel_no_pra_does_not_gate_global_pra_market(monkeypatch):
    monkeypatch.setattr(
        api,
        "_fetch_fanduel_pra_observations",
        lambda _day: ([], "FANDUEL_NO_PRA"),
    )
    monkeypatch.setattr(
        api,
        "_fetch_draftkings_pra_observations",
        lambda _day: (_dk_rows(), "DRAFTKINGS_OK"),
        raising=False,
    )

    payload = api.collect_nba_pra_market(date(2026, 10, 24))

    assert payload["verification"] == "VERIFIED"
    assert payload["ready"] is True
    assert payload["observation_count"] == 2
    assert payload["player_count"] == 1
    assert {row["sportsbook"] for row in payload["observations"]} == {"DraftKings"}
    assert payload["diagnostic_state"] == "OK"
    health = {row["provider"]: row["state"] for row in payload["provider_health"]}
    assert health["FanDuel"] == "FANDUEL_NO_PRA"
    assert health["DraftKings"] == "DRAFTKINGS_OK"


def test_global_unavailable_requires_all_approved_configured_routes_to_miss(monkeypatch):
    monkeypatch.setattr(
        api,
        "_fetch_fanduel_pra_observations",
        lambda _day: ([], "FANDUEL_NO_PRA"),
    )
    monkeypatch.setattr(
        api,
        "_fetch_draftkings_pra_observations",
        lambda _day: ([], "DRAFTKINGS_NO_PRA"),
        raising=False,
    )

    payload = api.collect_nba_pra_market(date(2026, 10, 24))

    assert payload["verification"] == "UNAVAILABLE"
    assert payload["ready"] is False
    assert payload["diagnostic_state"] == "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA"
    health = {row["provider"]: row["state"] for row in payload["provider_health"]}
    assert health == {
        "FanDuel": "FANDUEL_NO_PRA",
        "DraftKings": "DRAFTKINGS_NO_PRA",
    }
