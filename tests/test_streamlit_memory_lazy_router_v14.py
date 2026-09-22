"""Regression checks for additive Moneyline Router V14."""
import types

import streamlit_memory_lazy_router_v14 as r


def test_moneyline_routes_directly_to_v176(monkeypatch):
    games = object()
    seen = {}
    monkeypatch.setattr(r._FROZEN, "_load_mlb_schedule", lambda: (games, "2026-09-08"))
    monkeypatch.setattr(r.st, "caption", lambda text: seen.setdefault("caption", text))

    def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
        seen["args"] = (games_df, section_header, status_info, team_logo, h)

    module = types.SimpleNamespace(render_moneyline_hub=render_moneyline_hub)
    monkeypatch.setattr(
        r._FROZEN,
        "_import",
        lambda name: (seen.setdefault("module", name), module)[1],
    )

    r._render_mlb_v14_base("Moneyline")
    assert seen["module"] == "mlb_moneyline_hub_v176"
    assert seen["args"][0] is games
    assert "Moneyline" in seen["caption"]


def test_non_moneyline_uses_captured_frozen_v13_route(monkeypatch):
    seen = {}
    monkeypatch.setattr(r, "_BASE_MLB_ROUTE", lambda market: seen.setdefault("market", market))
    r._render_mlb_v14_base("Hits")
    assert seen["market"] == "Hits"


def test_render_app_temporarily_swaps_v13_hook_and_restores(monkeypatch):
    original = r.frozen_router._render_mlb_v13_base
    seen = {}

    def delegated_render():
        seen["hook"] = r.frozen_router._render_mlb_v13_base

    monkeypatch.setattr(r.frozen_router, "render_app", delegated_render)
    r.render_app()

    assert seen["hook"] is r._render_mlb_v14_base
    assert r.frozen_router._render_mlb_v13_base is original
