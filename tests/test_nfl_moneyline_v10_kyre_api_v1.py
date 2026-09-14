from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path

import pandas as pd
import pytest

import nfl_moneyline_market_api_v1 as api
import nfl_moneyline_hub_v10 as v10
import streamlit_memory_lazy_router_v129 as router


NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
EVENT_ID = "401772901"


def _payload(*, event_id: str = EVENT_ID, away_ml: int = -110, home_ml: int = 100):
    stamp = NOW.isoformat()
    return {
        "schema_version": "nfl_moneyline_market_v1",
        "official_event_id": event_id,
        "captured_at_utc": stamp,
        "ready": True,
        "market_available": True,
        "identity": {
            "official_event_id": event_id,
            "away_team_id": "7",
            "home_team_id": "12",
            "team_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "model_probability_input": False,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
        "books": [
            {
                "official_event_id": event_id,
                "official_away_team_id": "7",
                "official_home_team_id": "12",
                "sportsbook": "FanDuel",
                "provider": "Kyre Sports API / FanDuel",
                "market_type": "moneyline",
                "line_status": "active",
                "away_ml": away_ml,
                "home_ml": home_ml,
                "updated_at_utc": stamp,
                "projection_weight": 0.0,
            }
        ],
    }


def test_valid_exact_id_payload_is_market_only():
    out = api.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert out["ready"] is True
    assert out["official_event_id"] == EVENT_ID
    assert len(out["books"]) == 1
    assert out["books"][0]["sportsbook"] == "FanDuel"
    assert out["projection_weight"] == 0.0
    assert out["market_context_only"] is True
    assert out["may_modify_projection"] is False
    assert out["model_probability_input"] is False
    assert out["stake_sizing_enabled"] is False
    assert out["wager_actions"] is False


def test_event_identity_mismatch_fails_closed():
    out = api.validate_event_payload(_payload(event_id="401772999"), EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "identity mismatch" in out["reason"].lower()
    assert out["books"] == []


def test_projection_weight_or_identity_drift_fails_closed():
    payload = _payload()
    payload["market_semantics"]["projection_weight"] = 0.01
    out = api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "safety contract" in out["reason"].lower()

    payload = _payload()
    payload["identity"]["fuzzy_matching"] = True
    out = api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "safety contract" in out["reason"].lower()


def test_duplicate_book_and_bad_market_values_fail_closed():
    payload = _payload()
    payload["books"].append(dict(payload["books"][0]))
    out = api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "invalid or ambiguous" in out["reason"].lower()

    payload = _payload(away_ml=-99)
    out = api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "invalid or ambiguous" in out["reason"].lower()

    payload = _payload()
    payload["books"][0]["updated_at_utc"] = "not-a-time"
    out = api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
    assert out["ready"] is False
    assert "invalid or ambiguous" in out["reason"].lower()


def test_one_fanduel_pair_uses_frozen_v5_summary_and_stays_limited(monkeypatch):
    validated = api.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    monkeypatch.setattr(api, "fetch_event_market", lambda event_id: validated)
    pregame = pd.DataFrame([
        {
            "game_id": EVENT_ID,
            "away_team": "Denver Broncos",
            "home_team": "Kansas City Chiefs",
            "away_abbr": "DEN",
            "home_abbr": "KC",
        }
    ])

    snapshots, diag = api.fetch_nfl_moneyline_markets(pregame, "2026-09-14")
    snap = snapshots[EVENT_ID]

    assert diag["games_requested"] == 1
    assert diag["games_with_market"] == 1
    assert snap["ready"] is True
    assert snap["usable_books"] == 1
    assert snap["quality"] == "LIMITED"
    assert snap["quality"] != "MEDIUM"
    assert snap["best_away"] == {"price": -110, "book": "FanDuel"}
    assert snap["best_home"] == {"price": 100, "book": "FanDuel"}
    assert snap["consensus_away_no_vig"] is not None
    assert snap["consensus_home_no_vig"] is not None
    assert snap["rows"][0]["provider"] == "Kyre Sports API / FanDuel"


def test_v10_temporarily_swaps_only_v5_transport_and_restores(monkeypatch):
    original = v10.frozen_v5.market
    seen = {}

    def render(market):
        seen["market"] = market
        seen["transport"] = v10.frozen_v5.market
        return "ok"

    monkeypatch.setattr(v10.frozen_hub, "render_nfl_hub", render)
    assert v10.render_nfl_hub("Moneyline") == "ok"
    assert seen["market"] == "Moneyline"
    assert seen["transport"] is v10.kyre_market
    assert v10.frozen_v5.market is original


def test_v10_restores_transport_even_when_frozen_surface_raises(monkeypatch):
    original = v10.frozen_v5.market

    def boom(market):
        assert v10.frozen_v5.market is v10.kyre_market
        raise RuntimeError("synthetic witness failure")

    monkeypatch.setattr(v10.frozen_hub, "render_nfl_hub", boom)
    with pytest.raises(RuntimeError, match="synthetic witness failure"):
        v10.render_nfl_hub("Moneyline")
    assert v10.frozen_v5.market is original


def test_v129_advances_only_exact_nfl_moneyline():
    source = inspect.getsource(router)
    direct = inspect.getsource(router._render_nfl_v129)
    render = inspect.getsource(router.render_app)
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v128"
    assert router.ACTIVE_MONEYLINE_HUB == "nfl_moneyline_hub_v10"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert 'MONEYLINE_MARKET = "Moneyline"' in source
    assert "module.render_nfl_hub(market)" in direct
    assert "return prior.render_app()" in render
    assert "Passing Yards" not in direct


def test_app_activates_v129_and_preserves_v128_descendant_anchor():
    source = Path("app.py").read_text()
    assert 'from streamlit_memory_lazy_router_v129 import record_bootstrap_import_ms, render_app' in source
    assert 'from streamlit_memory_lazy_router_v128 import render_app as _frozen_v128_render_app' in source
    assert 'from streamlit_memory_lazy_router_v128 import record_bootstrap_import_ms, render_app' in source
    assert 'FROZEN_V128_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V128_NFL_PASSING_YARDS_PRODUCTION_CLEANUP_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V129_NFL_MONEYLINE_KYRE_API_TRANSPORT_2026-09-14"' in source


def test_v10_and_adapter_do_not_own_frozen_analytics():
    wrapper_source = inspect.getsource(v10)
    adapter_source = inspect.getsource(api)
    assert v10.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert v10.STAKE_SIZING_ENABLED is False
    assert api.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert api.STAKE_SIZING_ENABLED is False

    forbidden_wrapper = (
        "np.random",
        "default_rng",
        "monte_carlo",
        "_expected_return(",
        "_fair_american(",
        "QUALIFIED_EDGE =",
        "QUALIFIED_EV =",
        "LEAN_EDGE =",
        "MAX_COMFORTABLE_INTERVAL =",
    )
    for token in forbidden_wrapper:
        assert token not in wrapper_source, token

    # The adapter must delegate these market calculations to the frozen V5 owner.
    assert "frozen._enrich(row)" in adapter_source
    assert "frozen._summary(rows)" in adapter_source
    assert "implied_probability(" not in adapter_source
    assert "away_no_vig" not in adapter_source
    assert "consensus_away_no_vig" not in adapter_source
    assert "monte_carlo" not in adapter_source.lower()
    assert "_expected_return(" not in adapter_source
    assert "_fair_american(" not in adapter_source
