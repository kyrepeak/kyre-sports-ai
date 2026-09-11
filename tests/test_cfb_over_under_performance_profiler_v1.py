"""Regressions for additive CFB O/U performance-profiler Step 1."""
from __future__ import annotations

from pathlib import Path
import types

import cfb_over_under_clean_page_v32 as page
import cfb_over_under_performance_profiler_v1 as profiler
import cfb_over_under_slate_v15_identity_bridge as bridge
import cfb_schedule_v7_future_slate as schedule_v7
import streamlit_memory_lazy_router_v72 as router


def test_profiler_records_named_stage_without_changing_return_value():
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    try:
        value = profiler.timed_call("unit.stage", lambda x: x + 1, 4)
    finally:
        profiler.reset_active_trace(token)

    assert value == 5
    rows = trace.aggregate()
    assert len(rows) == 1
    assert rows[0]["stage"] == "unit.stage"
    assert rows[0]["calls"] == 1
    assert rows[0]["total_ms"] >= 0.0
    assert profiler.PROJECTION_WEIGHT == 0.0
    assert profiler.MAY_MODIFY_PROJECTION is False


def test_clean_page_v32_wraps_certified_v31_dependencies_only():
    globals_ = page._RENDER_V32.__globals__
    assert globals_["schedule_v6"] is page._SCHEDULE_PROXY
    assert globals_["market_adapter"] is page._MARKET_PROXY
    assert globals_["frozen_page"] is page._PAGE_PROXY
    assert globals_["st"] is page._ST_PROXY
    assert globals_["_line_board"] is page._timed_line_board

    assert page._BASE_SCHEDULE is schedule_v7
    assert page._BASE_PAGE.runtime_slate is bridge
    assert page.ACTIVE_SCHEDULE == "cfb_schedule_v7_future_slate"
    assert page.ACTIVE_RUNTIME_SLATE == "cfb_over_under_slate_v15_identity_bridge"
    assert page.FROZEN_RUNTIME_SLATE == "cfb_over_under_slate_v14_runtime"
    assert page.ACTIVE_PERFORMANCE_PROFILER == "cfb_over_under_performance_profiler_v1"


def test_clean_page_v32_preserves_certified_v31_browser_contract():
    required = (
        "CLEAN PAGE V32 ACTIVE",
        "PERFORMANCE PROFILER ACTIVE",
        "MEASUREMENT ONLY",
        "CLEAN PAGE V31 ACTIVE",
        "DOWNSTREAM IDENTITY BRIDGE ACTIVE",
        "FUTURE SLATE COVERAGE ACTIVE",
        "OFFICIAL ESPN IDENTITY RECOVERY",
        "NO FUZZY MATCHING",
        "NO FUZZY GAME MATCHING",
        "NO SYNTHETIC IDS",
        "FRESHNESS FIREWALL ACTIVE",
        "0.0% PROJECTION INFLUENCE",
        "0.0% SPORTSBOOK PROJECTION INFLUENCE",
        "FROZEN PROJECTION MATH PRESERVED",
        "FROZEN V14 PROJECTION MATH PRESERVED",
        "READABLE STEPS 4-12 ACTIVE",
    )
    for marker in required:
        assert marker in page._V32_MARKER


def test_runtime_timing_proxy_delegates_to_v15_without_mutating_result(monkeypatch):
    expected = {"sentinel": object()}
    seen = {}

    def fake_analyze(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(bridge, "analyze_game", fake_analyze)
    proxy = page._RuntimeTimingProxy(bridge)
    result = proxy.analyze_game({"game": 1}, "2026-09-12", 50.5)

    assert result is expected
    assert seen["args"][2] == 50.5


def test_router_v72_only_advances_cfb_over_under(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market, *args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )

    router._render_nfl_or_cfb_v72("Over/Under")

    assert seen["module"] == "cfb_over_under_clean_page_v32"
    assert seen["market"] == "Over/Under"


def test_router_v72_delegates_every_other_route(monkeypatch):
    seen = []
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    router._render_nfl_or_cfb_v72("Moneyline")

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v72("Over/Under")

    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v71_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v71
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v71}),
    )

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v72
    assert router.prior._render_nfl_or_cfb_v71 is original


def test_app_entrypoint_advances_only_to_v72_and_retains_v71_guard():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v71 import render_app as _frozen_v71_render_app" in text
    assert "from streamlit_memory_lazy_router_v72 import render_app" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V72_CFB_OU_PERFORMANCE_PROFILER_2026-09-11"'
        in text
    )
    assert "0.0% sportsbook projection influence" in text
    assert "no fuzzy game matching" in text
    assert "no synthetic IDs" in text
