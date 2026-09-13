from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from sports_api.api import nfl_rushing_yards_market_v1 as api
from sports_api.collectors import nfl_fanduel_rushing_yards_v1 as market


def _runner(role: str, selection_id: str, line: float, odds: int) -> dict:
    return {
        "runnerStatus": "ACTIVE",
        "selectionId": selection_id,
        "handicap": line,
        "result": {"type": role},
        "winRunnerOdds": {
            "americanDisplayOdds": {"americanOddsInt": odds},
        },
    }


def _canonical_market(*, line: float = 64.5) -> dict:
    return {
        "marketId": "rush-market-1",
        "marketName": "Player Rushing Yards",
        "marketStatus": "OPEN",
        "inPlay": False,
        "runners": [
            _runner("OVER", "sel-over", line, -110),
            _runner("UNDER", "sel-under", line, -110),
        ],
    }


def _espn_roster() -> dict:
    return {
        "athletes": [
            {
                "items": [
                    {
                        "id": "4430807",
                        "displayName": "Exact Runner",
                        "jersey": "28",
                        "position": {"abbreviation": "RB"},
                    },
                    {
                        "id": "3915511",
                        "displayName": "Exact Quarterback",
                        "jersey": "9",
                        "position": {"abbreviation": "QB"},
                    },
                    {
                        "id": "9999999",
                        "displayName": "Defender",
                        "jersey": "28",
                        "position": {"abbreviation": "CB"},
                    },
                ]
            }
        ]
    }


def _valid_payload() -> dict:
    return {
        "schema_version": market.SCHEMA_VERSION,
        "ready": True,
        "market_available": True,
        "official_event_id": "401872925",
        "sportsbook": "FanDuel",
        "captured_at_utc": "2026-09-13T02:30:00+00:00",
        "props": [
            {
                "official_event_id": "401872925",
                "official_athlete_id": "4430807",
                "official_team_id": "4",
                "player_name": "Exact Runner",
                "position": "RB",
                "market_type": "rushing_yards",
                "line": 64.5,
                "over_odds": -110,
                "under_odds": -110,
                "sportsbook": "FanDuel",
                "line_status": "active",
            }
        ],
        "identity": {
            "official_authority": "ESPN",
            "event_identity": "exact",
            "player_identity": "exact",
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "probability_enabled": False,
            "fair_odds_enabled": False,
            "ev_enabled": False,
            "grading_enabled": False,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def test_status_contract_keeps_market_post_projection_and_risk_actions_off():
    status = api.rushing_yards_market_status()
    assert status["schema_version"] == "nfl_rushing_yards_market_v1"
    assert status["provider"] == "FanDuel"
    assert status["projection_weight"] == 0.0
    assert status["market_context_only"] is True
    assert status["may_modify_projection"] is False
    assert status["probability_enabled"] is False
    assert status["fair_odds_enabled"] is False
    assert status["ev_enabled"] is False
    assert status["grading_enabled"] is False
    assert status["stake_sizing_enabled"] is False
    assert status["wager_actions"] is False


def test_market_classifier_accepts_only_canonical_rushing_yards():
    assert market.is_rushing_yards_market({"marketName": "Player Rushing Yards"}) is True
    assert market.is_rushing_yards_market({"marketName": "Alternate Rushing Yards"}) is False
    assert market.is_rushing_yards_market({"marketName": "Longest Rushing Yard"}) is False
    assert market.is_rushing_yards_market({"marketName": "Team Rushing Yards"}) is False
    assert market.is_rushing_yards_market({"marketName": "Player Passing Yards"}) is False


def test_roster_identity_requires_exact_team_jersey_and_position_not_name():
    roster = market.parse_espn_rusher_roster(_espn_roster(), "4")
    assert {row["athlete_id"] for row in roster} == {"4430807", "3915511"}

    resolved = market.reconcile_provider_rusher(
        {"team": "CIN", "number": "28", "position": "RB", "name": "Wrong Name Is Ignored"},
        {"4": roster},
    )
    assert resolved["athlete_id"] == "4430807"
    assert resolved["team_id"] == "4"
    assert resolved["position"] == "RB"

    with pytest.raises(market.NFLRushingYardsCollectorError):
        market.reconcile_provider_rusher(
            {"team": "CIN", "number": "28", "position": "WR"},
            {"4": roster},
        )


def test_normalize_market_binds_exact_fanduel_selection_to_espn_athlete():
    roster = market.parse_espn_rusher_roster(_espn_roster(), "4")
    row = market.normalize_rushing_yards_market(
        _canonical_market(),
        official_event_id="401872925",
        provider_event_id="fd-event-1",
        players={"fd-player-1": {"team": "CIN", "number": "28", "position": "RB"}},
        by_selection={"sel-over": ["fd-player-1"], "sel-under": ["fd-player-1"]},
        rosters_by_team={"4": roster},
        captured_at_utc=datetime(2026, 9, 13, 2, 30, tzinfo=timezone.utc),
    )
    assert row is not None
    assert row["official_event_id"] == "401872925"
    assert row["official_athlete_id"] == "4430807"
    assert row["official_team_id"] == "4"
    assert row["market_type"] == "rushing_yards"
    assert row["line"] == 64.5
    assert row["over_odds"] == -110
    assert row["under_odds"] == -110
    assert row["sportsbook"] == "FanDuel"


def test_normalize_market_fails_closed_on_mismatched_two_way_line():
    raw = _canonical_market()
    raw["runners"][1]["handicap"] = 65.5
    roster = market.parse_espn_rusher_roster(_espn_roster(), "4")
    with pytest.raises(market.NFLRushingYardsCollectorError):
        market.normalize_rushing_yards_market(
            raw,
            official_event_id="401872925",
            provider_event_id="fd-event-1",
            players={"fd-player-1": {"team": "CIN", "number": "28", "position": "RB"}},
            by_selection={"sel-over": ["fd-player-1"], "sel-under": ["fd-player-1"]},
            rosters_by_team={"4": roster},
            captured_at_utc=datetime(2026, 9, 13, 2, 30, tzinfo=timezone.utc),
        )


def test_route_rejects_any_semantics_that_can_feed_market_back_into_projection(monkeypatch):
    payload = _valid_payload()
    payload["market_semantics"]["projection_weight"] = 0.01
    monkeypatch.setattr(api, "collect_fanduel_nfl_rushing_yards_hosted", lambda event_id: payload)
    with pytest.raises(HTTPException) as exc:
        api.rushing_yards_market("401872925")
    assert exc.value.status_code == 503
    assert "safety contract" in str(exc.value.detail)


def test_route_rejects_duplicate_exact_athlete_markets(monkeypatch):
    payload = _valid_payload()
    payload["props"].append(dict(payload["props"][0]))
    monkeypatch.setattr(api, "collect_fanduel_nfl_rushing_yards_hosted", lambda event_id: payload)
    with pytest.raises(HTTPException) as exc:
        api.rushing_yards_market("401872925")
    assert exc.value.status_code == 503
    assert "row identity contract" in str(exc.value.detail)


def test_route_accepts_valid_exact_id_market_without_projection_controls(monkeypatch):
    payload = _valid_payload()
    monkeypatch.setattr(api, "collect_fanduel_nfl_rushing_yards_hosted", lambda event_id: payload)
    result = api.rushing_yards_market("401872925")
    assert result == payload
    assert result["market_semantics"]["projection_weight"] == 0.0
    assert result["market_semantics"]["may_modify_projection"] is False
    assert result["market_semantics"]["probability_enabled"] is False
    assert result["market_semantics"]["ev_enabled"] is False
    assert result["market_semantics"]["grading_enabled"] is False
    assert result["market_semantics"]["stake_sizing_enabled"] is False
