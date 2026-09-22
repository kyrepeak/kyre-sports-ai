from __future__ import annotations

from datetime import datetime, timedelta, timezone

import nfl_rushing_yards_market_api_v1 as market


EVENT_ID = "401872925"
ATHLETE_ID = "4430807"
TEAM_ID = "4"
NOW = datetime(2026, 9, 13, 2, 45, tzinfo=timezone.utc)


def _payload(*, captured_at: datetime | None = None, props: list[dict] | None = None) -> dict:
    stamp = captured_at or (NOW - timedelta(seconds=30))
    return {
        "schema_version": market.SCHEMA_VERSION,
        "ready": True,
        "market_available": True,
        "official_event_id": EVENT_ID,
        "sportsbook": "FanDuel",
        "captured_at_utc": stamp.isoformat(),
        "props": props
        if props is not None
        else [
            {
                "official_event_id": EVENT_ID,
                "official_athlete_id": ATHLETE_ID,
                "official_team_id": TEAM_ID,
                "player_name": "Verified rusher",
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


def test_fresh_exact_id_event_payload_is_accepted_without_model_features():
    result = market.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert result["ready"] is True
    assert result["market_available"] is True
    assert result["official_event_id"] == EVENT_ID
    assert len(result["props"]) == 1
    assert result["props"][0]["official_athlete_id"] == ATHLETE_ID
    assert result["projection_weight"] == 0.0
    assert result["may_modify_projection"] is False
    assert result["probability_enabled"] is False
    assert result["fair_odds_enabled"] is False
    assert result["ev_enabled"] is False
    assert result["grading_enabled"] is False
    assert result["stake_sizing_enabled"] is False
    assert result["wager_actions"] is False


def test_stale_market_fails_closed():
    result = market.validate_event_payload(
        _payload(captured_at=NOW - timedelta(seconds=market.MAX_MARKET_AGE_SECONDS + 1)),
        EVENT_ID,
        now_utc=NOW,
    )
    assert result["ready"] is False
    assert "stale" in result["reason"].lower()


def test_future_market_beyond_skew_fails_closed():
    result = market.validate_event_payload(
        _payload(captured_at=NOW + timedelta(seconds=market.MAX_FUTURE_SKEW_SECONDS + 1)),
        EVENT_ID,
        now_utc=NOW,
    )
    assert result["ready"] is False
    assert "future" in result["reason"].lower()


def test_wrong_event_identity_fails_closed():
    payload = _payload()
    payload["official_event_id"] = "401872926"
    result = market.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "identity mismatch" in result["reason"].lower()


def test_safety_contract_cannot_enable_projection_probability_or_grading():
    for key, bad in (
        ("projection_weight", 0.01),
        ("may_modify_projection", True),
        ("probability_enabled", True),
        ("fair_odds_enabled", True),
        ("ev_enabled", True),
        ("grading_enabled", True),
        ("stake_sizing_enabled", True),
        ("wager_actions", True),
    ):
        payload = _payload()
        payload["market_semantics"][key] = bad
        result = market.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
        assert result["ready"] is False, key
        assert "safety contract" in result["reason"].lower(), key


def test_identity_contract_cannot_enable_fuzzy_name_or_synthetic_ids():
    for key in ("player_name_matching", "fuzzy_matching", "synthetic_event_ids", "synthetic_player_ids"):
        payload = _payload()
        payload["identity"][key] = True
        result = market.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
        assert result["ready"] is False, key
        assert "safety contract" in result["reason"].lower(), key


def test_duplicate_exact_athlete_markets_fail_closed():
    row = _payload()["props"][0]
    payload = _payload(props=[dict(row), dict(row)])
    result = market.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "duplicate athlete" in result["reason"].lower()


def test_invalid_market_rows_are_not_promoted_to_ready_props():
    row = dict(_payload()["props"][0])
    row["market_type"] = "alternate_rushing_yards"
    result = market.validate_event_payload(_payload(props=[row]), EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "no certified prop" in result["reason"].lower()


def test_market_for_athlete_requires_exact_athlete_and_team_identity():
    event_market = market.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    exact = market.market_for_athlete(event_market, ATHLETE_ID, TEAM_ID)
    assert exact["ready"] is True
    assert exact["official_athlete_id"] == ATHLETE_ID
    assert exact["official_team_id"] == TEAM_ID
    assert exact["projection_weight"] == 0.0

    wrong_team = market.market_for_athlete(event_market, ATHLETE_ID, "5")
    assert wrong_team["ready"] is False
    assert "unavailable" in wrong_team["reason"].lower()


def test_market_fetch_path_is_isolated_rushing_market_endpoint():
    source = open(market.__file__, encoding="utf-8").read()
    assert '/api/v1/nfl/rushing-yards/market' in source
    assert '/api/v1/nfl/passing-yards' not in source
