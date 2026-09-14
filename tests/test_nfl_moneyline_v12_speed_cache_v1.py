from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path

import pandas as pd
import pytest

import nfl_moneyline_market_api_v1 as v1
import nfl_moneyline_market_api_v2 as v2
import nfl_moneyline_hub_v12 as v12
import streamlit_memory_lazy_router_v131 as router


NOW = datetime(2026, 9, 14, 18, 0, 0, tzinfo=timezone.utc)
EVENT_ID = "401772901"


def _payload(*, event_id: str = EVENT_ID):
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
                "away_ml": -110,
                "home_ml": 100,
                "updated_at_utc": stamp,
                "projection_weight": 0.0,
            }
        ],
    }


def _validated():
    out = v1.validate_event_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert out["ready"] is True
    return out


def _clock(monkeypatch):
    clock = {"utc": NOW, "mono": 1000.0}
    monkeypatch.setattr(v2, "_utc_now", lambda: clock["utc"])
    monkeypatch.setattr(v2, "monotonic", lambda: clock["mono"])
    return clock


def _failed_refresh():
    out = v1._fail("Kyre Sports API request failed: ReadTimeout", event_id=EVENT_ID)
    out["request_attempts"] = 2
    return out


def test_hot_cache_avoids_repeat_http_and_reages_quotes(monkeypatch):
    v2._clear_transport_cache()
    clock = _clock(monkeypatch)
    calls = {"count": 0}
    good = _validated()

    def fresh(event_id, **kwargs):
        calls["count"] += 1
        assert event_id == EVENT_ID
        return deepcopy(good)

    monkeypatch.setattr(v2.frozen, "fetch_event_market", fresh)

    first = v2.fetch_event_market(EVENT_ID)
    clock["utc"] += timedelta(seconds=5)
    clock["mono"] += 5
    second = v2.fetch_event_market(EVENT_ID)

    assert calls["count"] == 1
    assert first["transport_cache_source"] == "fresh"
    assert second["transport_cache_source"] == "hot"
    assert second["transport_http_avoided"] is True
    assert second["books"][0]["age_seconds"] == 5
    assert second["projection_weight"] == 0.0
    assert second["stake_sizing_enabled"] is False


def test_cache_key_includes_api_base_url(monkeypatch):
    v2._clear_transport_cache()
    _clock(monkeypatch)
    calls = []
    good = _validated()

    def fresh(event_id, **kwargs):
        calls.append((event_id, kwargs.get("base_url")))
        return deepcopy(good)

    monkeypatch.setattr(v2.frozen, "fetch_event_market", fresh)
    v2.fetch_event_market(EVENT_ID, base_url="https://api-a.example")
    v2.fetch_event_market(EVENT_ID, base_url="https://api-b.example")

    assert calls == [
        (EVENT_ID, "https://api-a.example"),
        (EVENT_ID, "https://api-b.example"),
    ]


def test_refresh_failure_reuses_last_good_only_while_non_stale(monkeypatch):
    v2._clear_transport_cache()
    clock = _clock(monkeypatch)
    good = _validated()
    calls = {"count": 0}

    def fresh(event_id, **kwargs):
        calls["count"] += 1
        return deepcopy(good) if calls["count"] == 1 else _failed_refresh()

    monkeypatch.setattr(v2.frozen, "fetch_event_market", fresh)
    assert v2.fetch_event_market(EVENT_ID)["ready"] is True

    clock["utc"] += timedelta(seconds=46)
    clock["mono"] += 46
    fallback = v2.fetch_event_market(EVENT_ID)

    assert calls["count"] == 2
    assert fallback["ready"] is True
    assert fallback["transport_cache_source"] == "last_good"
    assert fallback["stale_safe_reuse"] is True
    assert fallback["books"][0]["age_seconds"] == 46
    assert fallback["refresh_request_attempts"] == 2
    assert "ReadTimeout" in fallback["refresh_failure_reason"]


def test_last_good_is_rejected_after_frozen_stale_boundary(monkeypatch):
    v2._clear_transport_cache()
    clock = _clock(monkeypatch)
    good = _validated()
    calls = {"count": 0}

    def fresh(event_id, **kwargs):
        calls["count"] += 1
        return deepcopy(good) if calls["count"] == 1 else _failed_refresh()

    monkeypatch.setattr(v2.frozen, "fetch_event_market", fresh)
    assert v2.fetch_event_market(EVENT_ID)["ready"] is True

    clock["utc"] += timedelta(seconds=v2.STALE_SECONDS + 1)
    clock["mono"] += v2.STALE_SECONDS + 1
    failed = v2.fetch_event_market(EVENT_ID)

    assert calls["count"] == 2
    assert failed["ready"] is False
    assert failed["transport_cache_source"] == "fresh_failure"
    assert failed["stale_safe_reuse"] is False


def test_slate_wrapper_keeps_frozen_summary_math(monkeypatch):
    v2._clear_transport_cache()
    good = _validated()
    good["transport_cache_source"] = "hot"
    monkeypatch.setattr(v2, "fetch_event_market", lambda event_id: deepcopy(good))
    pregame = pd.DataFrame([
        {
            "game_id": EVENT_ID,
            "away_team": "Denver Broncos",
            "home_team": "Kansas City Chiefs",
            "away_abbr": "DEN",
            "home_abbr": "KC",
        }
    ])

    snapshots, diag = v2.fetch_nfl_moneyline_markets(pregame, "2026-09-14")
    snap = snapshots[EVENT_ID]

    assert diag["games_requested"] == 1
    assert diag["games_with_market"] == 1
    assert diag["hot_cache_hits"] == 1
    assert snap["ready"] is True
    assert snap["quality"] == "LIMITED"
    assert snap["usable_books"] == 1
    assert snap["best_away"] == {"price": -110, "book": "FanDuel"}
    assert snap["best_home"] == {"price": 100, "book": "FanDuel"}


def test_v12_swaps_only_v10_adapter_and_restores(monkeypatch):
    original = v12.v10.kyre_market
    seen = {}

    def render(market):
        seen["market"] = market
        seen["adapter"] = v12.v10.kyre_market
        return "ok"

    monkeypatch.setattr(v12.frozen_v11, "render_nfl_hub", render)
    assert v12.render_nfl_hub("Moneyline") == "ok"
    assert seen["market"] == "Moneyline"
    assert seen["adapter"] is v12.speed_market
    assert v12.v10.kyre_market is original


def test_v12_restores_adapter_when_frozen_v11_raises(monkeypatch):
    original = v12.v10.kyre_market

    def boom(market):
        assert v12.v10.kyre_market is v12.speed_market
        raise RuntimeError("synthetic V12 witness failure")

    monkeypatch.setattr(v12.frozen_v11, "render_nfl_hub", boom)
    with pytest.raises(RuntimeError, match="synthetic V12 witness failure"):
        v12.render_nfl_hub("Moneyline")
    assert v12.v10.kyre_market is original


def test_v131_advances_only_exact_nfl_moneyline():
    direct = inspect.getsource(router._render_nfl_v131)
    render = inspect.getsource(router.render_app)
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v130"
    assert router.ACTIVE_MONEYLINE_HUB == "nfl_moneyline_hub_v12"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STAKE_SIZING_ENABLED is False
    assert "module.render_nfl_hub(market)" in direct
    assert "return prior.render_app()" in render
    assert "Passing Yards" not in direct
    assert "Receiving Yards" not in direct
    assert "Rushing Yards" not in direct


def test_app_activates_v131_and_preserves_v130_anchor():
    source = Path("app.py").read_text()
    assert 'from streamlit_memory_lazy_router_v131 import record_bootstrap_import_ms, render_app' in source
    assert 'from streamlit_memory_lazy_router_v130 import render_app as _frozen_v130_render_app' in source
    assert 'FROZEN_V130_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V130_NFL_MONEYLINE_NO_FLASH_2026-09-14"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V131_NFL_MONEYLINE_V12_SPEED_CACHE_2026-09-14"' in source


def test_v12_speed_layer_does_not_own_frozen_analytics():
    adapter_source = inspect.getsource(v2)
    wrapper_source = inspect.getsource(v12)
    assert v2.FROZEN_ADAPTER == "nfl_moneyline_market_api_v1"
    assert v12.FROZEN_HUB == "nfl_moneyline_hub_v11"
    assert v2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v2.STAKE_SIZING_ENABLED is False
    assert v12.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert v12.STAKE_SIZING_ENABLED is False

    forbidden = (
        "np.random",
        "default_rng",
        "monte_carlo",
        "implied_probability(",
        "away_no_vig",
        "consensus_away_no_vig",
        "_expected_return(",
        "_fair_american(",
        "QUALIFIED_EDGE =",
        "QUALIFIED_EV =",
        "LEAN_EDGE =",
    )
    for token in forbidden:
        assert token not in adapter_source, token
        assert token not in wrapper_source, token

    assert "frozen._snapshot_from_event(game, event_market)" in adapter_source
