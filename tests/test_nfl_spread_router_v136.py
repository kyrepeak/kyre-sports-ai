from __future__ import annotations

from pathlib import Path

import pytest

import streamlit_memory_lazy_router_v132 as route_v132
import streamlit_memory_lazy_router_v135 as frozen
import streamlit_memory_lazy_router_v136 as router


def test_v136_static_standalone_contract() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v135"
    assert router.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v4"
    assert router.SPREAD_MARKET == "Spread"
    assert router.ROUTE_QUERY_SPORT == route_v132.ROUTE_QUERY_SPORT
    assert router.ROUTE_QUERY_MARKET == route_v132.ROUTE_QUERY_MARKET
    assert router.STANDALONE_SPREAD_ROUTE is True
    assert router.PROJECTION_MODEL_ENABLED is True
    assert router.MONTE_CARLO_ENABLED is True
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STAKE_SIZING_ENABLED is False
    assert router.WAGER_ACTIONS_ENABLED is False
    assert router.HTML_RENDER_GUARD == "flatten_generated_html"
    assert router.HTML_RENDER_GUARD_SCOPE == "route_purge_reimport_safe"


def test_v136_reuses_frozen_route_and_guard_instead_of_reimplementing_analytics() -> None:
    source = Path("streamlit_memory_lazy_router_v136.py").read_text(encoding="utf-8")

    assert "import streamlit_memory_lazy_router_v132 as route_v132" in source
    assert "import streamlit_memory_lazy_router_v135 as frozen" in source
    assert "import streamlit_memory_lazy_router_v134" not in source
    assert "import streamlit_memory_lazy_router_v133" not in source
    assert "nfl_spread_model_v1" not in source
    assert "nfl_spread_mc_v1" not in source
    assert "nfl_spread_market_api_v1" not in source
    assert "simulate_game_spread" not in source
    assert "requests.get" not in source
    assert "._matchup_card =" not in source
    assert "._summary_html =" not in source


def test_v136_exact_spread_route_bypasses_v135_owner_swap_chain(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    old_active_hub = route_v132.ACTIVE_SPREAD_HUB

    def original_import(name: str) -> object:
        calls.append(("original_import", name))
        return {"name": name}

    def frozen_guard(importer, name: str) -> object:
        calls.append(("guard", name))
        return importer(name)

    def direct_render() -> str:
        assert route_v132.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v4"
        guarded_module = route_v132.root._import("nfl_spread_hub_v4")
        assert guarded_module == {"name": "nfl_spread_hub_v4"}
        calls.append(("direct", route_v132.ACTIVE_SPREAD_HUB))
        return "V136_DIRECT_SPREAD"

    def forbidden_frozen_render() -> None:
        raise AssertionError("V135 chain must not own the active V136 Spread route")

    monkeypatch.setattr(route_v132, "_fast_route_active", lambda: True)
    monkeypatch.setattr(route_v132, "_render_direct_spread", direct_render)
    monkeypatch.setattr(route_v132.root, "_import", original_import)
    monkeypatch.setattr(frozen, "_guard_route_import", frozen_guard)
    monkeypatch.setattr(frozen, "render_app", forbidden_frozen_render)

    assert router.render_app() == "V136_DIRECT_SPREAD"
    assert calls == [
        ("guard", "nfl_spread_hub_v4"),
        ("original_import", "nfl_spread_hub_v4"),
        ("direct", "nfl_spread_hub_v4"),
    ]
    assert route_v132.ACTIVE_SPREAD_HUB == old_active_hub
    assert route_v132.root._import is original_import


def test_v136_restores_v132_owner_and_importer_when_direct_route_raises(monkeypatch) -> None:
    old_active_hub = route_v132.ACTIVE_SPREAD_HUB

    def original_import(name: str) -> object:
        return {"name": name}

    def explode() -> None:
        assert route_v132.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v4"
        assert route_v132.root._import is not original_import
        raise RuntimeError("synthetic direct-route failure")

    monkeypatch.setattr(route_v132, "_fast_route_active", lambda: True)
    monkeypatch.setattr(route_v132, "_render_direct_spread", explode)
    monkeypatch.setattr(route_v132.root, "_import", original_import)

    with pytest.raises(RuntimeError, match="synthetic direct-route failure"):
        router.render_app()

    assert route_v132.ACTIVE_SPREAD_HUB == old_active_hub
    assert route_v132.root._import is original_import


def test_v136_restores_query_then_takes_direct_spread_route(monkeypatch) -> None:
    states = iter((False, True))
    restored: list[str] = []

    monkeypatch.setattr(route_v132, "_fast_route_active", lambda: next(states))
    monkeypatch.setattr(
        route_v132,
        "_restore_spread_route_from_query",
        lambda: restored.append("restored") or True,
    )
    monkeypatch.setattr(route_v132, "_render_direct_spread", lambda: "RESTORED_DIRECT")
    monkeypatch.setattr(
        frozen,
        "render_app",
        lambda: (_ for _ in ()).throw(AssertionError("frozen route should not run")),
    )

    assert router.render_app() == "RESTORED_DIRECT"
    assert restored == ["restored"]


def test_v136_non_spread_routes_delegate_to_frozen_v135(monkeypatch) -> None:
    restored: list[str] = []
    delegated: list[str] = []

    monkeypatch.setattr(route_v132, "_fast_route_active", lambda: False)
    monkeypatch.setattr(
        route_v132,
        "_restore_spread_route_from_query",
        lambda: restored.append("checked") or False,
    )
    monkeypatch.setattr(
        frozen,
        "render_app",
        lambda: delegated.append("v135") or "FROZEN_V135_ROUTE",
    )

    assert router.render_app() == "FROZEN_V135_ROUTE"
    assert restored == ["checked"]
    assert delegated == ["v135"]


def test_v136_guard_adapter_uses_v135_certified_guard(monkeypatch) -> None:
    calls: list[str] = []
    marker = object()

    def importer(name: str) -> object:
        calls.append(f"import:{name}")
        return marker

    def guard(inner_importer, name: str) -> object:
        calls.append(f"guard:{name}")
        return inner_importer(name)

    monkeypatch.setattr(frozen, "_guard_route_import", guard)

    assert router._guard_route_import(importer, "nfl_spread_hub_v4") is marker
    assert calls == ["guard:nfl_spread_hub_v4", "import:nfl_spread_hub_v4"]
