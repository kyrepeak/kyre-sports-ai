from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import nfl_spread_market_api_v1 as adapter


EVENT_ID = "401872931"
NOW = datetime(2026, 9, 14, 19, 45, 0, tzinfo=timezone.utc)


def _payload():
    captured = "2026-09-14T19:44:55+00:00"
    return {
        "schema_version": "nfl_spread_market_v1",
        "service": "Kyre Sports API",
        "sport": "nfl",
        "market": "spread",
        "official_event_id": EVENT_ID,
        "captured_at_utc": captured,
        "ready": True,
        "market_available": True,
        "identity": {
            "official_authority": "ESPN",
            "official_event_id": EVENT_ID,
            "provider_event_id": "35601246",
            "away_team_id": "7",
            "home_team_id": "12",
            "away_abbr": "DEN",
            "home_abbr": "KC",
            "kickoff_delta_seconds": 0,
            "team_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
        },
        "books": [
            {
                "official_event_id": EVENT_ID,
                "sportsbook": "FanDuel",
                "provider": "FanDuel via Kyre Sports API",
                "provider_event_id": "35601246",
                "market_id": "spread-1",
                "away_spread": 2.5,
                "home_spread": -2.5,
                "away_price": -115,
                "home_price": -105,
                "updated_at_utc": captured,
                "line_status": "active",
            }
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "model_probability_input": False,
            "multi_book_capable": True,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def test_adapter_accepts_certified_exact_event_spread():
    out = adapter.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert out["ready"] is True
    assert out["market_available"] is True
    assert out["official_event_id"] == EVENT_ID
    assert out["identity"]["away_abbr"] == "DEN"
    assert out["identity"]["home_abbr"] == "KC"
    assert out["books"][0]["away_spread"] == 2.5
    assert out["books"][0]["home_spread"] == -2.5
    assert out["books"][0]["away_price"] == -115
    assert out["books"][0]["home_price"] == -105
    assert out["projection_weight"] == 0.0
    assert out["market_context_only"] is True
    assert out["model_probability_input"] is False
    assert out["stake_sizing_enabled"] is False
    assert out["wager_actions"] is False


def test_adapter_fails_closed_on_wrong_event_or_unsafe_identity():
    wrong_event = adapter.validate_event_payload(_payload(), "401000000", now_utc=NOW)
    assert wrong_event["ready"] is False

    fuzzy = _payload()
    fuzzy["identity"]["fuzzy_matching"] = True
    out = adapter.validate_event_payload(fuzzy, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False

    synthetic = _payload()
    synthetic["identity"]["synthetic_event_ids"] = True
    out = adapter.validate_event_payload(synthetic, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False


def test_adapter_fails_closed_on_bad_spread_pair_price_or_projection_weight():
    bad_pair = _payload()
    bad_pair["books"][0]["home_spread"] = -1.5
    assert adapter.validate_event_payload(bad_pair, EVENT_ID, now_utc=NOW)["ready"] is False

    bad_price = _payload()
    bad_price["books"][0]["away_price"] = -90
    assert adapter.validate_event_payload(bad_price, EVENT_ID, now_utc=NOW)["ready"] is False

    weighted = _payload()
    weighted["market_semantics"]["projection_weight"] = 0.01
    assert adapter.validate_event_payload(weighted, EVENT_ID, now_utc=NOW)["ready"] is False


def test_adapter_rejects_stale_capture():
    stale = _payload()
    stale["captured_at_utc"] = "2026-09-14T19:30:00+00:00"
    stale["books"][0]["updated_at_utc"] = "2026-09-14T19:30:00+00:00"
    out = adapter.validate_event_payload(stale, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "stale" in out["reason"].lower()


def test_spread_formatters_are_display_only():
    assert adapter.fmt_spread(2.5) == "+2.5"
    assert adapter.fmt_spread(-2.5) == "-2.5"
    assert adapter.fmt_american(114) == "+114"
    assert adapter.fmt_american(-115) == "-115"


def test_router_v132_is_additive_over_frozen_v131():
    source = Path("streamlit_memory_lazy_router_v132.py").read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v131"' in source
    assert 'SPREAD_MARKET = "Spread"' in source
    assert 'ACTIVE_SPREAD_HUB = "nfl_spread_hub_v1"' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'STAKE_SIZING_ENABLED = False' in source
    assert 'WAGER_ACTIONS_ENABLED = False' in source
    assert "return _load_prior().render_app()" in source


def test_spread_page_keeps_model_and_monte_carlo_off():
    source = Path("nfl_spread_hub_v1.py").read_text(encoding="utf-8")
    assert 'FROZEN_SLATE_OWNER = "nfl_hub_v1"' in source
    assert 'MARKET_OWNER = "nfl_spread_market_api_v1"' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert '"projection_model": "OFF"' in source
    assert '"monte_carlo": "OFF"' in source
    assert '"rankings_recommendations": "OFF"' in source
    assert '_safe(market.get("official_event_id")) == _safe(game.get("game_id"))' in source


def test_app_bootstraps_v132_and_preserves_v131_heartbeat():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'FROZEN_V131_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V131_NFL_MONEYLINE_PERFORMANCE_FAST_ROUTE_2026-09-14"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V132_NFL_SPREAD_KYRE_API_TRANSPORT_2026-09-14"' in source
    assert "from streamlit_memory_lazy_router_v132 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v131 import record_bootstrap_import_ms, render_app" not in source.split("try:", 1)[1]
