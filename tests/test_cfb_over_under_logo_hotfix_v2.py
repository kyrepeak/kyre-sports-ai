"""Regression checks for CFB O/U ESPN logo hotfix V2."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v3_logo_hotfix_v2 as ui
import streamlit_memory_lazy_router_v41 as router


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


def test_direct_composite_hero_forces_resolver_inside_step1_call(monkeypatch):
    seen = {"resolver_called": 0}

    def resolver(game):
        seen["resolver_called"] += 1
        return _visuals()

    monkeypatch.setattr(ui.logo_resolver, "resolve_visuals", resolver)
    monkeypatch.setattr(ui.step2, "_rankings_panel", lambda *a, **k: "<STEP2/>")
    monkeypatch.setattr(ui.step3, "_engine_panel", lambda *a, **k: "<STEP3/>")

    original = ui.step1._visuals_for_game
    html = ui._hero_with_forced_espn_logos(_game(), _away(), _home())

    assert seen["resolver_called"] == 1
    assert "/50.png" in html
    assert "/2390.png" in html
    assert "TEAM LOGOS VERIFIED" in html
    assert "<STEP2/>" in html
    assert "<STEP3/>" in html
    assert ui.step1._visuals_for_game is original


def test_v2_wrapper_patches_active_step3_hero_not_step1_global(monkeypatch):
    original = ui.step3._enhanced_hero_v3
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)

    def fake_render(*args, **kwargs):
        seen["during"] = ui.step3._enhanced_hero_v3
        return "ok"

    monkeypatch.setattr(ui.step3, "render_over_under_hub", fake_render)
    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["during"] is ui._hero_with_forced_espn_logos
    assert ui.step3._enhanced_hero_v3 is original


def test_router_v41_only_advances_cfb_over_under(monkeypatch):
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
    router._render_nfl_or_cfb_v41("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v3_logo_hotfix_v2"
    assert seen["market"] == "Over/Under"


def test_router_v41_delegates_moneyline_game_total_and_non_cfb(monkeypatch):
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
    router._render_nfl_or_cfb_v41("Moneyline")
    router._render_nfl_or_cfb_v41("Game Total")

    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v41("Over/Under")

    assert seen == ["Moneyline", "Game Total", "Over/Under"]


def test_render_app_temporarily_patches_v40_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v40
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v40

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v41
    assert router.prior._render_nfl_or_cfb_v40 is original
