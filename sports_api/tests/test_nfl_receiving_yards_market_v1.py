from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from sports_api.api import nfl_receiving_yards_market_v1 as route
from sports_api.collectors import nfl_fanduel_receiving_yards_v1 as collector


EVENT_ID = "401900001"


def _identity() -> dict:
    return {
        "official_authority": "ESPN",
        "event_identity": "exact ESPN event ID + exact team IDs + bounded kickoff equality",
        "player_identity": "FanDuel selection -> FDX player -> exact team/jersey/position ESPN roster row",
        "player_name_matching": False,
        "fuzzy_matching": False,
        "synthetic_event_ids": False,
        "synthetic_player_ids": False,
    }


def _semantics() -> dict:
    return {
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "probability_enabled": False,
        "fair_odds_enabled": False,
        "ev_enabled": False,
        "grading_enabled": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def _prop(
    athlete_id: str = "100",
    *,
    team_id: str = "27",
    position: str = "WR",
) -> dict:
    return {
        "official_event_id": EVENT_ID,
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "player_name": "Display Name Only",
        "position": position,
        "market_type": "receiving_yards",
        "line": 67.5,
        "over_odds": -110,
        "under_odds": -110,
        "sportsbook": "FanDuel",
        "line_status": "active",
        "provider_event_id": "fd-event-1",
        "provider_market_id": f"fd-market-{athlete_id}",
        "provider_player_key": f"fd-player-{athlete_id}",
        "captured_at_utc": "2026-09-13T20:00:00+00:00",
    }


def _payload(props: list[dict] | None = None) -> dict:
    rows = [_prop()] if props is None else props
    return {
        "schema_version": collector.SCHEMA_VERSION,
        "ready": True,
        "market_available": bool(rows),
        "official_event_id": EVENT_ID,
        "sportsbook": "FanDuel",
        "captured_at_utc": "2026-09-13T20:00:00+00:00",
        "props": rows,
        "reason": "",
        "identity": _identity(),
        "market_semantics": _semantics(),
    }


def test_market_detector_accepts_only_canonical_receiving_yards():
    assert collector.is_receiving_yards_market(
        {"marketName": "Player Receiving Yards"}
    ) is True
    assert collector.is_receiving_yards_market(
        {"marketName": "Alternate Receiving Yards"}
    ) is False
    assert collector.is_receiving_yards_market(
        {"marketName": "Team Receiving Yards"}
    ) is False
    assert collector.is_receiving_yards_market(
        {"marketName": "1st Half Receiving Yards"}
    ) is False
    assert collector.is_receiving_yards_market(
        {"marketName": "Longest Reception"}
    ) is False
    assert collector.is_receiving_yards_market(
        {"marketName": "Player Rushing Yards"}
    ) is False


def test_receiver_roster_keeps_only_exact_id_eligible_positions():
    roster = {
        "athletes": [{
            "items": [
                {"id": "100", "displayName": "Wideout", "jersey": "13", "position": {"abbreviation": "WR"}},
                {"id": "101", "displayName": "Tight End", "jersey": "81", "position": {"abbreviation": "TE"}},
                {"id": "102", "displayName": "Halfback", "jersey": "1", "position": {"abbreviation": "HB"}},
                {"id": "103", "displayName": "Fullback", "jersey": "44", "position": {"abbreviation": "FB"}},
                {"id": "104", "displayName": "Quarterback", "jersey": "12", "position": {"abbreviation": "QB"}},
                {"id": "bad", "displayName": "No ID", "jersey": "99", "position": {"abbreviation": "WR"}},
            ]
        }]
    }
    rows = collector.parse_espn_receiver_roster(roster, "27")
    assert [(row["athlete_id"], row["position"]) for row in rows] == [
        ("100", "WR"),
        ("101", "TE"),
        ("102", "RB"),
        ("103", "FB"),
    ]
    assert all(row["team_id"] == "27" for row in rows)


def test_provider_receiver_identity_ignores_player_name_and_uses_exact_keys():
    rosters = {
        "27": [{
            "team_id": "27",
            "athlete_id": "100",
            "jersey": "13",
            "position": "WR",
            "display_name": "Official ESPN Name",
        }]
    }
    provider_player = {
        "team": "TB",
        "number": "13",
        "position": "WR",
        "name": "INTENTIONALLY WRONG DISPLAY NAME",
    }
    resolved = collector.reconcile_provider_receiver(provider_player, rosters)
    assert resolved["athlete_id"] == "100"
    assert resolved["team_id"] == "27"


def test_provider_receiver_ambiguous_exact_identity_fails_closed():
    rosters = {
        "27": [
            {"team_id": "27", "athlete_id": "100", "jersey": "13", "position": "WR", "display_name": "One"},
            {"team_id": "27", "athlete_id": "200", "jersey": "13", "position": "WR", "display_name": "Two"},
        ]
    }
    provider_player = {"team": "TB", "number": "13", "position": "WR"}
    try:
        collector.reconcile_provider_receiver(provider_player, rosters)
    except collector.NFLReceivingYardsMarketCollectorError as exc:
        assert "exactly one ESPN athlete" in str(exc)
    else:
        raise AssertionError("ambiguous exact receiver identity did not fail closed")


def test_market_route_status_exposes_permanent_safety_contract():
    status = route.receiving_yards_market_status()
    assert status["status"] == "ready"
    assert status["schema_version"] == "nfl_receiving_yards_market_v1"
    assert status["provider"] == "FanDuel"
    assert status["official_authority"] == "ESPN"
    assert status["player_name_matching"] is False
    assert status["fuzzy_matching"] is False
    assert status["synthetic_event_ids"] is False
    assert status["synthetic_player_ids"] is False
    assert status["projection_weight"] == 0.0
    assert status["market_context_only"] is True
    assert status["may_modify_projection"] is False
    assert status["probability_enabled"] is False
    assert status["fair_odds_enabled"] is False
    assert status["ev_enabled"] is False
    assert status["grading_enabled"] is False
    assert status["stake_sizing_enabled"] is False
    assert status["wager_actions"] is False


def test_market_route_rejects_duplicate_exact_athlete_rows(monkeypatch):
    first = _prop("100")
    second = deepcopy(first)
    second["provider_market_id"] = "fd-market-duplicate"
    monkeypatch.setattr(
        route,
        "collect_fanduel_nfl_receiving_yards_hosted",
        lambda event_id: _payload([first, second]),
    )

    try:
        route.receiving_yards_market(EVENT_ID)
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "row identity contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("duplicate exact athlete Receiving Yards rows did not fail closed")


def test_market_route_accepts_one_valid_exact_id_prop(monkeypatch):
    expected = _payload([_prop("100", team_id="27", position="WR")])
    monkeypatch.setattr(
        route,
        "collect_fanduel_nfl_receiving_yards_hosted",
        lambda event_id: expected,
    )
    result = route.receiving_yards_market(EVENT_ID)
    assert result == expected
    assert result["market_semantics"]["projection_weight"] == 0.0
    assert result["market_semantics"]["market_context_only"] is True


def test_market_route_rejects_non_receiver_position(monkeypatch):
    bad = _payload([_prop("999", team_id="27", position="QB")])
    monkeypatch.setattr(
        route,
        "collect_fanduel_nfl_receiving_yards_hosted",
        lambda event_id: bad,
    )
    try:
        route.receiving_yards_market(EVENT_ID)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("QB Receiving Yards row did not fail the receiver-only contract")


def test_shared_host_router_registers_receiving_market_once():
    from sports_api.api.health import router as health_router

    paths = [getattr(item, "path", "") for item in health_router.routes]
    assert paths.count("/api/v1/nfl/receiving-yards/market") == 1
    assert paths.count("/api/v1/nfl/receiving-yards/market/status") == 1


def test_frozen_projection_owner_is_not_imported_by_market_collector_or_route():
    import inspect

    collector_source = inspect.getsource(collector)
    route_source = inspect.getsource(route)
    assert "nfl_receiving_yards_projection_v1" not in collector_source
    assert "nfl_receiving_yards_projection_v1" not in route_source
    assert '"projection_weight": 0.0' in collector_source
    assert '"projection_weight": 0.0' in route_source
