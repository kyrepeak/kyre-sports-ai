"""Router V57 regression tests."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v57 as router


def test_router_v57_routes_cfb_ou_directly_to_clean_page(monkeypatch):
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
    router._render_nfl_or_cfb_v57("Over/Under")
    assert seen["module"] == "cfb_over_under_clean_page_v17"
    assert seen["market"] == "Over/Under"


def test_router_v57_delegates_other_routes(monkeypatch):
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
    router._render_nfl_or_cfb_v57("Moneyline")
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v57("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]
