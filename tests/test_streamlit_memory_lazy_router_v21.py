"""Regression checks for additive strict no-TOUGH Router V21."""
import types

import streamlit_memory_lazy_router_v21 as r


def test_hits_routes_directly_to_v1321(monkeypatch):
    games = object()
    seen = {}
    monkeypatch.setattr(r._FROZEN, "_load_mlb_schedule", lambda: (games, "2026-09-08"))
    monkeypatch.setattr(r.st, "caption", lambda text: seen.setdefault("caption", text))
    monkeypatch.setattr(r._FROZEN, "_install_step8f_for_market", lambda market: seen.setdefault("install", market))

    def render_hit_hub(games_df, section_header, status_info, team_logo, h):
        seen["args"] = (games_df, section_header, status_info, team_logo, h)

    module = types.SimpleNamespace(render_hit_hub=render_hit_hub)
    monkeypatch.setattr(
        r._FROZEN,
        "_import",
        lambda name: (seen.setdefault("module", name), module)[1],
    )

    r._render_mlb_v21_base("1+ Hit")

    assert seen["module"] == "mlb_hit_hub_v1321"
    assert seen["install"] == "1+ Hit"
    assert seen["args"][0] is games


def test_non_hits_delegate_through_frozen_router_v20(monkeypatch):
    seen = []
    monkeypatch.setattr(r, "_BASE_MLB_ROUTE", lambda market: seen.append(market))
    r._render_mlb_v21_base("Moneyline")
    r._render_mlb_v21_base("Matchup Explorer")
    assert seen == ["Moneyline", "Matchup Explorer"]


def test_render_app_restores_v20_hook(monkeypatch):
    original = r.frozen_router._render_mlb_v20_base
    seen = {}

    def delegated_render():
        seen["hook"] = r.frozen_router._render_mlb_v20_base

    monkeypatch.setattr(r.frozen_router, "render_app", delegated_render)
    r.render_app()

    assert seen["hook"] is r._render_mlb_v21_base
    assert r.frozen_router._render_mlb_v20_base is original
