from __future__ import annotations

import ast
from pathlib import Path
import sys
import types

import streamlit_memory_lazy_router_v1 as router


def _fake_st():
    return types.SimpleNamespace(
        session_state={},
        caption=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        markdown=lambda *args, **kwargs: None,
    )


def test_app_bootstrap_does_not_replay_legacy_wrapper_chain():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_v1" in source
    assert "subprocess" not in source
    assert "urllib" not in source
    assert "exec(" not in source
    assert "FROZEN_PRE_LIVE_COMMIT" not in source


def test_router_has_no_eager_production_route_imports():
    source = Path("streamlit_memory_lazy_router_v1.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    eager = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            eager.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            eager.append(node.module)

    forbidden_prefixes = (
        "mlb_",
        "wnba_",
        "hit_hub_",
        "moneyline_hub_",
        "spread_hub_",
        "totals_hub_",
        "live_game_hub_",
        "slate_hub_",
        "nfl_hub_",
    )
    assert not [name for name in eager if name.startswith(forbidden_prefixes)]


def test_route_change_purges_stale_sport_market_module_graph(monkeypatch):
    fake_st = _fake_st()
    monkeypatch.setattr(router, "st", fake_st)

    stale_names = [
        "wnba_fake_memory_chain",
        "mlb_fake_memory_chain",
        "hit_hub_fake_memory_chain",
        "spread_hub_fake_memory_chain",
    ]
    for name in stale_names:
        sys.modules[name] = types.ModuleType(name)
    unrelated = types.ModuleType("kyre_unrelated_keep")
    sys.modules["kyre_unrelated_keep"] = unrelated

    try:
        removed = router._purge_route_modules_if_needed("MLB:Slate")
        assert removed >= len(stale_names)
        assert all(name not in sys.modules for name in stale_names)
        assert sys.modules.get("kyre_unrelated_keep") is unrelated
        assert fake_st.session_state[router._ROUTE_TOKEN_KEY] == "MLB:Slate"

        # Same route must not repeatedly churn the import graph on every rerun.
        assert router._purge_route_modules_if_needed("MLB:Slate") == 0
    finally:
        for name in stale_names + ["kyre_unrelated_keep"]:
            sys.modules.pop(name, None)


def test_mlb_moneyline_loads_only_selected_market_module(monkeypatch):
    imports = []
    rendered = []
    monkeypatch.setattr(router, "st", _fake_st())
    monkeypatch.setattr(router, "_load_mlb_schedule", lambda: (object(), "2026-09-02"))

    moneyline = types.SimpleNamespace(
        render_moneyline_hub=lambda *args: rendered.append("moneyline")
    )

    def fake_import(name):
        imports.append(name)
        if name == "mlb_moneyline_hub_v164":
            return moneyline
        raise AssertionError(f"unexpected eager import: {name}")

    monkeypatch.setattr(router, "_import", fake_import)
    router._render_mlb("Moneyline")

    assert imports == ["mlb_moneyline_hub_v164"]
    assert rendered == ["moneyline"]


def test_wnba_points_loads_schedule_bridge_then_points_only(monkeypatch):
    imports = []
    rendered = []
    monkeypatch.setattr(router, "st", _fake_st())

    bridge = types.SimpleNamespace(
        install_wnba_api_schedule_bridge=lambda: rendered.append("bridge")
    )
    points = types.SimpleNamespace(
        render_wnba_points_hub=lambda *args: rendered.append("points")
    )

    def fake_import(name):
        imports.append(name)
        if name == "wnba_api_schedule_bridge_v1":
            return bridge
        if name == "wnba_points_hub_v19847":
            return points
        raise AssertionError(f"unexpected eager import: {name}")

    monkeypatch.setattr(router, "_import", fake_import)
    router._render_wnba("Points")

    assert imports == ["wnba_api_schedule_bridge_v1", "wnba_points_hub_v19847"]
    assert rendered == ["bridge", "points"]


def test_nfl_route_loads_only_nfl_hub(monkeypatch):
    imports = []
    rendered = []
    monkeypatch.setattr(router, "st", _fake_st())

    nfl = types.SimpleNamespace(render_nfl_hub=lambda market: rendered.append(market))

    def fake_import(name):
        imports.append(name)
        if name == "nfl_hub_v18":
            return nfl
        raise AssertionError(f"unexpected eager import: {name}")

    monkeypatch.setattr(router, "_import", fake_import)
    router._render_nfl("Moneyline")

    assert imports == ["nfl_hub_v18"]
    assert rendered == ["Moneyline"]


def test_market_contracts_keep_all_current_routes():
    assert "Pitcher Strikeouts" in router.MLB_MARKETS
    assert "Daily Game Picks" in router.MLB_MARKETS
    assert "Rebounds + Assists" in router.WNBA_MARKETS
    assert "Daily Picks" in router.WNBA_MARKETS
    assert "Anytime TD" in router.NFL_MARKETS
