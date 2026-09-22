"""Regression checks for additive Moneyline Router V5."""
import types

import streamlit_memory_lazy_router_v5 as r


def test_moneyline_routes_directly_to_v167(monkeypatch):
    games = object()
    seen = {}

    monkeypatch.setattr(r.frozen_router.frozen, "_load_mlb_schedule", lambda: (games, "2026-09-07"))
    monkeypatch.setattr(r.st, "caption", lambda text: seen.setdefault("caption", text))

    def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
        seen["args"] = (games_df, section_header, status_info, team_logo, h)

    module = types.SimpleNamespace(render_moneyline_hub=render_moneyline_hub)
    monkeypatch.setattr(
        r.frozen_router.frozen,
        "_import",
        lambda name: (seen.setdefault("module", name), module)[1],
    )

    r._render_mlb_v5_base("Moneyline")

    assert seen["module"] == "mlb_moneyline_hub_v167"
    assert seen["args"][0] is games
    assert "Moneyline" in seen["caption"]


def test_non_moneyline_delegates_to_frozen_base(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        r.frozen_router,
        "_BASE_MLB_ROUTE",
        lambda market: seen.setdefault("market", market),
    )

    r._render_mlb_v5_base("Hits")

    assert seen["market"] == "Hits"


def test_render_app_temporarily_swaps_v4_hook_and_restores(monkeypatch):
    original = r.frozen_router._render_mlb_v4_base
    seen = {}

    def delegated_render():
        seen["hook"] = r.frozen_router._render_mlb_v4_base

    monkeypatch.setattr(r.frozen_router, "render_app", delegated_render)

    r.render_app()

    assert seen["hook"] is r._render_mlb_v5_base
    assert r.frozen_router._render_mlb_v4_base is original
