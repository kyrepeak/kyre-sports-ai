from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
from typing import Any

import pytest
import requests

import nfl_passing_yards_hub_v20 as v20
import nfl_passing_yards_hub_v21 as v21
import nfl_passing_yards_hub_v22 as v22
import nfl_passing_yards_hub_v23 as v23
import nfl_passing_yards_hub_v24 as v24
import nfl_passing_yards_hub_v34 as frozen_v34
import nfl_passing_yards_hub_v35 as page
import nfl_passing_yards_market_api_v1 as market_v1
import nfl_passing_yards_market_api_v2 as market_v2
import streamlit_memory_lazy_router_v128 as router


EVENT_ID = "401772510"
ATHLETE_ID = "4431611"
TEAM_ID = "12"
NOW = datetime(2026, 9, 14, 2, 0, 0, tzinfo=timezone.utc)


def _payload(*, captured_at: datetime = NOW) -> dict[str, Any]:
    return {
        "schema_version": market_v1.SCHEMA_VERSION,
        "official_event_id": EVENT_ID,
        "captured_at_utc": captured_at.isoformat(),
        "market_available": True,
        "identity": {
            "fuzzy_matching": False,
            "player_name_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "stake_sizing_enabled": False,
        },
        "props": [
            {
                "official_event_id": EVENT_ID,
                "official_athlete_id": ATHLETE_ID,
                "official_team_id": TEAM_ID,
                "market_type": "passing_yards",
                "sportsbook": "FanDuel",
                "line_status": "active",
                "line": 249.5,
                "over_odds": -110,
                "under_odds": -110,
            }
        ],
    }


class _Response:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_market_v2_transport_is_bounded_and_safety_contract_is_frozen() -> None:
    assert market_v2.FROZEN_VALIDATION_OWNER == "nfl_passing_yards_market_api_v1"
    assert market_v2.MAX_REQUEST_ATTEMPTS == 1
    assert market_v2.REQUEST_CONNECT_TIMEOUT_SECONDS == 3.0
    assert market_v2.REQUEST_READ_TIMEOUT_SECONDS == 15.0
    assert market_v2.HOT_CACHE_TTL_SECONDS == 20.0
    assert market_v2.MAX_MARKET_AGE_SECONDS == market_v1.MAX_MARKET_AGE_SECONDS == 300
    assert market_v2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert market_v2.STAKE_SIZING_ENABLED is False


def test_market_v2_hot_cache_avoids_duplicate_streamlit_rerun_request(monkeypatch) -> None:
    market_v2.reset_transport_cache()
    calls: list[dict[str, Any]] = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        return _Response(_payload())

    monkeypatch.setattr(market_v2._SESSION, "get", fake_get)
    first = market_v2.fetch_event_market(EVENT_ID, now_utc=NOW, base_url="https://example.test")
    second = market_v2.fetch_event_market(EVENT_ID, now_utc=NOW, base_url="https://example.test")

    assert first["ready"] is True
    assert first["transport_source"] == "network"
    assert first["request_attempts"] == 1
    assert second["ready"] is True
    assert second["transport_source"] == "hot-cache"
    assert second["request_attempts"] == 0
    assert len(calls) == 1
    assert calls[0]["timeout"] == (3.0, 15.0)
    assert second["projection_weight"] == 0.0


def test_market_v2_read_timeout_can_use_only_still_fresh_certified_cache(monkeypatch) -> None:
    market_v2.reset_transport_cache()
    monkeypatch.setattr(market_v2._SESSION, "get", lambda *a, **k: _Response(_payload()))
    seeded = market_v2.fetch_event_market(EVENT_ID, now_utc=NOW, base_url="https://example.test")
    assert seeded["ready"] is True

    # Make it older than the short rerun cache so the network is tried again.
    market_v2._PAYLOAD_CACHE[EVENT_ID]["stored_monotonic"] -= market_v2.HOT_CACHE_TTL_SECONDS + 1.0

    def read_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout("simulated")

    monkeypatch.setattr(market_v2._SESSION, "get", read_timeout)
    rescued = market_v2.fetch_event_market(
        EVENT_ID,
        now_utc=NOW + timedelta(seconds=45),
        base_url="https://example.test",
    )
    assert rescued["ready"] is True
    assert rescued["transport_source"] == "fresh-cache-after-transient-error"
    assert rescued["request_attempts"] == 1
    assert "ReadTimeout" in rescued["transport_warning"]
    assert rescued["age_seconds"] == pytest.approx(45.0)
    assert rescued["projection_weight"] == 0.0
    assert rescued["stake_sizing_enabled"] is False


def test_market_v2_rejects_cached_payload_after_certified_freshness_window(monkeypatch) -> None:
    market_v2.reset_transport_cache()
    monkeypatch.setattr(market_v2._SESSION, "get", lambda *a, **k: _Response(_payload()))
    assert market_v2.fetch_event_market(EVENT_ID, now_utc=NOW, base_url="https://example.test")["ready"] is True
    market_v2._PAYLOAD_CACHE[EVENT_ID]["stored_monotonic"] -= market_v2.HOT_CACHE_TTL_SECONDS + 1.0

    def read_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout("simulated")

    monkeypatch.setattr(market_v2._SESSION, "get", read_timeout)
    out = market_v2.fetch_event_market(
        EVENT_ID,
        now_utc=NOW + timedelta(seconds=market_v1.MAX_MARKET_AGE_SECONDS + 1),
        base_url="https://example.test",
    )
    assert out["ready"] is False
    assert out["transport_source"] == "network-failed-closed"
    assert "ReadTimeout" in out["reason"]
    assert out["projection_weight"] == 0.0


def test_market_v2_invalid_identity_still_fails_closed_without_network(monkeypatch) -> None:
    market_v2.reset_transport_cache()
    called = False

    def fake_get(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not run for invalid event ID")

    monkeypatch.setattr(market_v2._SESSION, "get", fake_get)
    out = market_v2.fetch_event_market("not-an-id", now_utc=NOW)
    assert out["ready"] is False
    assert out["projection_weight"] == 0.0
    assert called is False


def test_v35_suppresses_only_v20_to_v24_certification_captions() -> None:
    class FakeStreamlit:
        def __init__(self) -> None:
            self.captions: list[str] = []

        def caption(self, body, *args, **kwargs):
            self.captions.append(str(body))
            return "delegated"

    fake = FakeStreamlit()
    proxy = page._CaptionCleanupStreamlitProxy(fake)
    for version in range(20, 25):
        assert proxy.caption(f"NFL PASSING YARDS V{version} • developer certification text") is None
    assert proxy.caption("Model probabilities are estimates — not guarantees.") == "delegated"
    assert proxy.caption("Useful user-facing caption") == "delegated"
    assert fake.captions == [
        "Model probabilities are estimates — not guarantees.",
        "Useful user-facing caption",
    ]


def test_v35_temporarily_routes_v20_to_market_v2_and_restores_all_owners(monkeypatch) -> None:
    originals = {owner: owner.st for owner in (v20, v21, v22, v23, v24)}
    original_market_api = v20.market_api
    observed: dict[str, Any] = {}

    def fake_render() -> None:
        observed["market_api"] = v20.market_api
        observed["proxies"] = [isinstance(owner.st, page._CaptionCleanupStreamlitProxy) for owner in originals]

    monkeypatch.setattr(frozen_v34, "render_nfl_passing_yards_hub", fake_render)
    page.render_nfl_passing_yards_hub()

    assert observed["market_api"] is market_v2
    assert observed["proxies"] == [True, True, True, True, True]
    assert v20.market_api is original_market_api
    assert all(owner.st is original for owner, original in originals.items())


def test_v35_restores_patches_even_if_frozen_page_raises(monkeypatch) -> None:
    originals = {owner: owner.st for owner in (v20, v21, v22, v23, v24)}
    original_market_api = v20.market_api

    def boom() -> None:
        raise RuntimeError("synthetic render failure")

    monkeypatch.setattr(frozen_v34, "render_nfl_passing_yards_hub", boom)
    with pytest.raises(RuntimeError, match="synthetic render failure"):
        page.render_nfl_passing_yards_hub()
    assert v20.market_api is original_market_api
    assert all(owner.st is original for owner, original in originals.items())


def test_v35_is_production_cleanup_only_over_frozen_v34_v28() -> None:
    assert page.PRODUCTION_CLEANUP_ONLY is True
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v34"
    assert page.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"
    assert page.ACTIVE_MARKET_TRANSPORT == "nfl_passing_yards_market_api_v2"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False
    source = inspect.getsource(page.render_nfl_passing_yards_hub)
    for forbidden in (
        "build_baseline_projection",
        "build_context_projection",
        "build_distribution",
        "evaluate_market",
        "projection_yards",
        "fair_odds",
        "no_vig",
        "over_ev",
        "under_ev",
        "stake_size",
        "projection_adjustment",
    ):
        assert forbidden not in source, forbidden


def test_router_v128_advances_only_passing_to_v35(monkeypatch) -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v127"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v35"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    calls: list[tuple[str, str]] = []

    class FakeModule:
        @staticmethod
        def render_nfl_hub(market: str) -> None:
            calls.append(("render", market))

    monkeypatch.setattr(router.root, "_import", lambda name: (calls.append(("import", name)) or FakeModule))
    router._render_nfl_v128("Passing Yards")
    assert calls == [("import", "nfl_passing_yards_hub_v35"), ("render", "Passing Yards")]

    with pytest.raises(RuntimeError):
        router._render_nfl_v128("Receiving Yards")


def test_app_activates_v128_and_preserves_v127_compatibility_anchor() -> None:
    source = open("app.py", "r", encoding="utf-8").read()
    assert 'FROZEN_V127_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V127_NFL_PASSING_YARDS_COMBINED_PLAYER_CARDS_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V128_NFL_PASSING_YARDS_PRODUCTION_CLEANUP_2026-09-13"' in source
    assert "from streamlit_memory_lazy_router_v128 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v127 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v127 import render_app as _frozen_v127_render_app" in source
