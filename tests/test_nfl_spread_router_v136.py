from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import streamlit_memory_lazy_router_v132 as route_v132
import streamlit_memory_lazy_router_v136 as router


def test_v136_static_standalone_contract() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v135"
    assert router.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v4"
    assert router.SPREAD_MARKET == "Spread"
    assert router.ROUTE_QUERY_SPORT == route_v132.ROUTE_QUERY_SPORT
    assert router.ROUTE_QUERY_MARKET == route_v132.ROUTE_QUERY_MARKET
    assert router.STANDALONE_SPREAD_ROUTE is True
    assert router.ACTIVE_SPREAD_V135_DEPENDENCY is False
    assert router.PROJECTION_MODEL_ENABLED is True
    assert router.MONTE_CARLO_ENABLED is True
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STAKE_SIZING_ENABLED is False
    assert router.WAGER_ACTIONS_ENABLED is False
    assert router.HTML_RENDER_GUARD == "flatten_generated_html"
    assert router.HTML_RENDER_GUARD_SCOPE == "route_purge_reimport_safe"


def test_v136_active_spread_source_has_no_v135_or_model_dependency() -> None:
    source = Path("streamlit_memory_lazy_router_v136.py").read_text(encoding="utf-8")

    assert "import streamlit_memory_lazy_router_v132 as route_v132" in source
    assert "import nfl_spread_hub_v4 as spread_v4" in source
    assert "import streamlit_memory_lazy_router_v135" not in source
    assert "import streamlit_memory_lazy_router_v134" not in source
    assert "import streamlit_memory_lazy_router_v133" not in source
    assert "def _load_frozen_non_spread" in source
    assert "nfl_spread_model_v1" not in source
    assert "nfl_spread_mc_v1" not in source
    assert "nfl_spread_market_api_v1" not in source
    assert "simulate_game_spread" not in source
    assert "requests.get" not in source


def test_v136_exact_spread_route_never_loads_v135(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    old_active_hub = route_v132.ACTIVE_SPREAD_HUB

    def original_import(name: str) -> object:
        calls.append(("original_import", name))
        return {"name": name}

    def guard(importer, name: str) -> object:
        calls.append(("guard", name))
        return importer(name)

    def direct_render() -> str:
        assert route_v132.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v4"
        guarded_module = route_v132.root._import("nfl_spread_hub_v4")
        assert guarded_module == {"name": "nfl_spread_hub_v4"}
        calls.append(("direct", route_v132.ACTIVE_SPREAD_HUB))
        return "V136_DIRECT_SPREAD"

    def forbidden_v135_load():
        raise AssertionError("active V136 Spread route must never load V135")

    monkeypatch.setattr(route_v132, "_fast_route_active", lambda: True)
    monkeypatch.setattr(route_v132, "_render_direct_spread", direct_render)
    monkeypatch.setattr(route_v132.root, "_import", original_import)
    monkeypatch.setattr(router, "_guard_route_import", guard)
    monkeypatch.setattr(router, "_load_frozen_non_spread", forbidden_v135_load)

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


def test_v136_restores_query_then_takes_direct_spread_route_without_v135(monkeypatch) -> None:
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
        router,
        "_load_frozen_non_spread",
        lambda: (_ for _ in ()).throw(AssertionError("V135 must not load")),
    )

    assert router.render_app() == "RESTORED_DIRECT"
    assert restored == ["restored"]


def test_v136_non_spread_routes_lazy_delegate_to_frozen_v135(monkeypatch) -> None:
    restored: list[str] = []
    delegated: list[str] = []
    frozen = SimpleNamespace(
        render_app=lambda: delegated.append("v135") or "FROZEN_V135_ROUTE"
    )

    monkeypatch.setattr(route_v132, "_fast_route_active", lambda: False)
    monkeypatch.setattr(
        route_v132,
        "_restore_spread_route_from_query",
        lambda: restored.append("checked") or False,
    )
    monkeypatch.setattr(router, "_load_frozen_non_spread", lambda: frozen)

    assert router.render_app() == "FROZEN_V135_ROUTE"
    assert restored == ["checked"]
    assert delegated == ["v135"]


def test_v136_self_contained_guard_flattens_fresh_v4_import() -> None:
    raw_card = """
    <article class="ksp4-matchup-card">
      <section class="ksp4-team-panel ksp4-away">Away</section>
      <div class="ksp4-vs">VS</div>
      <section class="ksp4-team-panel ksp4-home">Home</section>
    </article>
    """
    raw_summary = """
    <div class="ksp4-summary-grid">
      <div class="ksp4-summary-tile">Summary</div>
    </div>
    """
    fresh_v4 = SimpleNamespace(
        _matchup_card=lambda *args, **kwargs: raw_card,
        _summary_html=lambda *args, **kwargs: raw_summary,
    )

    def importer(name: str):
        assert name == "nfl_spread_hub_v4"
        return fresh_v4

    guarded = router._guard_route_import(importer, "nfl_spread_hub_v4")

    assert "\n" not in guarded._matchup_card()
    assert "\n" not in guarded._summary_html()
    assert '<div class="ksp4-vs">VS</div>' in guarded._matchup_card()
    assert guarded._KSP4_HTML_RENDER_GUARD == router.HTML_RENDER_GUARD


def test_v136_non_spread_import_is_not_modified() -> None:
    module = SimpleNamespace()

    def importer(name: str):
        return module

    assert router._guard_route_import(importer, "not_nfl_spread_v4") is module
    assert not hasattr(module, "_KSP4_HTML_RENDER_GUARD")
