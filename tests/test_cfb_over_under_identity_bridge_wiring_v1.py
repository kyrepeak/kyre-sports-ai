"""UI/router regressions for the additive CFB O/U identity bridge path."""
from __future__ import annotations

from pathlib import Path
import types

import cfb_over_under_clean_page_v31 as page
import cfb_over_under_slate_v15_identity_bridge as bridge
import cfb_schedule_v7_future_slate as schedule_v7
import streamlit_memory_lazy_router_v71 as router


def test_clean_page_v31_preserves_v7_schedule_and_injects_only_v15_runtime():
    globals_ = page._RENDER_V31.__globals__
    assert globals_["schedule_v6"] is schedule_v7
    assert globals_["frozen_page"].runtime_slate is bridge
    assert page.ACTIVE_SCHEDULE == "cfb_schedule_v7_future_slate"
    assert page.ACTIVE_RUNTIME_SLATE == "cfb_over_under_slate_v15_identity_bridge"
    assert page.FROZEN_RUNTIME_SLATE == "cfb_over_under_slate_v14_runtime"
    assert bridge.MARKET_PROJECTION_WEIGHT == 0.0


def test_clean_page_v31_preserves_certified_v30_browser_contract_markers():
    certified_markers = (
        "CFB O/U • CLEAN PAGE V30 ACTIVE",
        "FUTURE SLATE COVERAGE ACTIVE",
        "OFFICIAL ESPN IDENTITY RECOVERY",
        "NO FUZZY MATCHING",
        "NO SYNTHETIC IDS",
        "FRESHNESS FIREWALL ACTIVE",
        "0.0% PROJECTION INFLUENCE",
        "FROZEN PROJECTION MATH PRESERVED",
        "READABLE STEPS 4-12 ACTIVE",
    )
    for marker in certified_markers:
        assert marker in page._V31_MARKER

    assert "CFB O/U • CLEAN PAGE V31 ACTIVE" in page._V31_MARKER
    assert "DOWNSTREAM IDENTITY BRIDGE ACTIVE" in page._V31_MARKER
    assert "NO FUZZY GAME MATCHING" in page._V31_MARKER
    assert "0.0% SPORTSBOOK PROJECTION INFLUENCE" in page._V31_MARKER
    assert "FROZEN V14 PROJECTION MATH PRESERVED" in page._V31_MARKER


def test_router_v71_only_advances_cfb_over_under(monkeypatch):
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

    router._render_nfl_or_cfb_v71("Over/Under")

    assert seen["module"] == "cfb_over_under_clean_page_v31"
    assert seen["market"] == "Over/Under"


def test_router_v71_delegates_every_other_route(monkeypatch):
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
    router._render_nfl_or_cfb_v71("Moneyline")

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v71("Over/Under")

    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v70_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v70
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v70}),
    )

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v71
    assert router.prior._render_nfl_or_cfb_v70 is original


def test_app_entrypoint_advances_only_to_v71_and_retains_v70_guard():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v70 import render_app as _frozen_v70_render_app" in text
    assert "from streamlit_memory_lazy_router_v71 import render_app" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V71_CFB_OU_DOWNSTREAM_IDENTITY_BRIDGE_2026-09-11"'
        in text
    )
    assert "No fuzzy game matching. No synthetic IDs." in text
