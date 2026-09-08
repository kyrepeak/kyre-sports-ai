"""Regression checks for Router V22 root Hits interception."""
import types

import streamlit_memory_lazy_router_v22 as r


def test_hits_intercepts_at_actual_router_v3_root(monkeypatch):
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

    r._render_mlb_v22_root("1+ Hit")

    assert seen["module"] == "mlb_hit_hub_v1321"
    assert seen["install"] == "1+ Hit"
    assert seen["args"][0] is games


def test_non_hits_delegate_to_frozen_router_v3_callable(monkeypatch):
    seen = []
    monkeypatch.setattr(r, "_BASE_ROOT_ROUTE", lambda market: seen.append(market))
    r._render_mlb_v22_root("Moneyline")
    r._render_mlb_v22_root("Matchup Explorer")
    assert seen == ["Moneyline", "Matchup Explorer"]


def test_render_app_patches_router_v3_root_and_restores(monkeypatch):
    original = r.root_router._render_mlb_v3
    seen = {}

    def delegated_render():
        seen["hook"] = r.root_router._render_mlb_v3

    monkeypatch.setattr(r.prior, "render_app", delegated_render)
    r.render_app()

    assert seen["hook"] is r._render_mlb_v22_root
    assert r.root_router._render_mlb_v3 is original


def test_v22_documents_exact_root_boundary():
    assert r.ROOT_ROUTE == "streamlit_memory_lazy_router_v3._render_mlb_v3"
