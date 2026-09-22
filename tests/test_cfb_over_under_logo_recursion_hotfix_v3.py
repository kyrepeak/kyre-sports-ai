"""Regression checks for CFB O/U ESPN logo recursion hotfix V3."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v3_logo_hotfix_v3 as ui
import streamlit_memory_lazy_router_v42 as router


def _game():
    return {
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "away_team_slug": "florida-a-m",
        "away_conference": "SWAC",
        "home_team": "Miami (FL)",
        "home_team_slug": "miami-fl",
        "home_conference": "ACC",
        "kickoff_et": "8:00 PM ET",
        "venue": "Hard Rock Stadium",
        "broadcast": "ACCN",
        "status": "Scheduled",
        "neutral_site": False,
        "identity_verified": True,
        "date_matches_query": True,
        "identity_key": "ncaa:6604311",
        "espn_event_id": "",
    }


def _away():
    return {
        "team": "Florida A&M",
        "team_slug": "florida-a-m",
        "conference": "SWAC",
        "record_text": "1-1",
        "ap_rank": None,
        "rank_source": "NCAA AP rankings — unranked",
    }


def _home():
    return {
        "team": "Miami (FL)",
        "team_slug": "miami-fl",
        "conference": "ACC",
        "record_text": "1-0",
        "ap_rank": 7,
        "rank_source": "NCAA AP rankings",
    }


def _visuals():
    return {
        "away": {
            "team_id": "50",
            "name": "Florida A&M",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/50.png",
            "record": "1-1",
        },
        "home": {
            "team_id": "2390",
            "name": "Miami",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/2390.png",
            "record": "1-0",
            "rank": 7,
        },
    }


def test_v3_uses_immutable_step1_hero_when_mutable_symbol_points_back_to_v3(monkeypatch):
    monkeypatch.setattr(ui.logo_resolver, "resolve_visuals", lambda game: _visuals())
    monkeypatch.setattr(ui, "_FROZEN_STEP2_RANKINGS_PANEL", lambda *a, **k: "<STEP2/>")
    monkeypatch.setattr(ui, "_FROZEN_STEP3_ENGINE_PANEL", lambda *a, **k: "<STEP3/>")

    # This recreates the exact nested-wrapper condition that caused V2 to
    # recurse: the public Step-1 hero symbol points to the composite hotfix hero.
    monkeypatch.setattr(ui.step1, "_enhanced_hero", ui._hero_with_nonrecursive_espn_logos)

    html = ui._hero_with_nonrecursive_espn_logos(_game(), _away(), _home())

    assert "/50.png" in html
    assert "/2390.png" in html
    assert "TEAM LOGOS VERIFIED" in html
    assert "<STEP2/>" in html
    assert "<STEP3/>" in html


def test_v3_does_not_consult_mutable_step1_hero_symbol(monkeypatch):
    monkeypatch.setattr(ui.logo_resolver, "resolve_visuals", lambda game: _visuals())
    monkeypatch.setattr(ui, "_FROZEN_STEP2_RANKINGS_PANEL", lambda *a, **k: "")
    monkeypatch.setattr(ui, "_FROZEN_STEP3_ENGINE_PANEL", lambda *a, **k: "")

    def explode(*args, **kwargs):
        raise AssertionError("mutable Step-1 hero symbol was consulted")

    monkeypatch.setattr(ui.step1, "_enhanced_hero", explode)

    html = ui._hero_with_nonrecursive_espn_logos(_game(), _away(), _home())
    assert "/50.png" in html
    assert "/2390.png" in html


def test_v3_wrapper_patches_active_step3_hero_and_restores(monkeypatch):
    original = ui.step3._enhanced_hero_v3
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)

    def fake_render(*args, **kwargs):
        seen["during"] = ui.step3._enhanced_hero_v3
        return "ok"

    monkeypatch.setattr(ui.step3, "render_over_under_hub", fake_render)
    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["during"] is ui._hero_with_nonrecursive_espn_logos
    assert ui.step3._enhanced_hero_v3 is original


def test_router_v42_only_advances_cfb_over_under(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )

    def render_cfb_hub(market, section_header, status_info, team_logo, h):
        seen["market"] = market

    module = types.SimpleNamespace(render_cfb_hub=render_cfb_hub)

    def fake_import(name):
        seen["module"] = name
        return module

    monkeypatch.setattr(router.root, "_import", fake_import)
    router._render_nfl_or_cfb_v42("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v3_logo_hotfix_v3"
    assert seen["market"] == "Over/Under"


def test_router_v42_delegates_other_markets_and_non_cfb(monkeypatch):
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
    router._render_nfl_or_cfb_v42("Moneyline")
    router._render_nfl_or_cfb_v42("Game Total")

    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v42("Over/Under")

    assert seen == ["Moneyline", "Game Total", "Over/Under"]


def test_render_app_temporarily_patches_v41_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v41
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v41

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v42
    assert router.prior._render_nfl_or_cfb_v41 is original
