from datetime import datetime, timedelta, timezone
from pathlib import Path

import nfl_receiving_yards_market_api_v1 as market


def _payload(now: datetime) -> dict:
    return {
        "schema_version": market.SCHEMA_VERSION,
        "official_event_id": "401999001",
        "sportsbook": "FanDuel",
        "captured_at_utc": now.isoformat(),
        "market_available": True,
        "identity": {
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
        "props": [
            {
                "official_event_id": "401999001",
                "official_athlete_id": "12345",
                "official_team_id": "1",
                "player_name": "Verified Receiver",
                "position": "WR",
                "market_type": "receiving_yards",
                "line": 64.5,
                "over_odds": -110,
                "under_odds": -110,
                "sportsbook": "FanDuel",
                "line_status": "active",
            }
        ],
    }


def test_fresh_exact_id_market_passes_and_stays_market_only():
    now = datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc)
    out = market.validate_event_payload(_payload(now), "401999001", now_utc=now)
    assert out["ready"] is True
    assert out["market_available"] is True
    assert out["projection_weight"] == 0.0
    assert out["may_modify_projection"] is False
    assert out["props"][0]["official_athlete_id"] == "12345"


def test_stale_market_fails_closed():
    now = datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc)
    payload = _payload(now - timedelta(seconds=market.MAX_MARKET_AGE_SECONDS + 1))
    out = market.validate_event_payload(payload, "401999001", now_utc=now)
    assert out["ready"] is False
    assert "stale" in out["reason"].lower()


def test_duplicate_athlete_market_fails_closed():
    now = datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc)
    payload = _payload(now)
    payload["props"].append(dict(payload["props"][0]))
    out = market.validate_event_payload(payload, "401999001", now_utc=now)
    assert out["ready"] is False
    assert "duplicate" in out["reason"].lower()


def test_step8_surface_keeps_no_projection_and_zero_influence_contract():
    hub = Path("nfl_receiving_yards_hub_v8.py").read_text(encoding="utf-8")
    router = Path("streamlit_memory_lazy_router_v119.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'NO_PROJECTION_LABEL = "NO PROJECTION"' in hub
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in hub
    assert "nfl_receiving_yards_hub_v8" in router
    assert "streamlit_memory_lazy_router_v119" in app
    assert "STREAMLIT_MAIN_V119_NFL_RECEIVING_YARDS_STEP8_FANDUEL_FULL_LINEUP_2026-09-13" in app
