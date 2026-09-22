"""Regression tests for the V15 visible-data handoff."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v15_visible_data_path as ui
import cfb_schedule_v4 as schedule_v4
import streamlit_memory_lazy_router_v55 as router


def test_reconciled_triplet_replaces_all_three_objects(monkeypatch):
    corrected_game = {"game_date": "2026-09-10", "venue": "Hard Rock Stadium"}
    corrected_away = {"team": "Florida A&M", "record_text": "1-1"}
    corrected_home = {"team": "Miami (FL)", "record_text": "1-0", "ap_rank": 7}

    monkeypatch.setattr(
        ui.deep_data,
        "reconcile_matchup",
        lambda game, day: ({
            "game": corrected_game,
            "away": corrected_away,
            "home": corrected_home,
        }, {}),
    )

    g, a, h = ui._reconciled_triplet(
        {"game_date": "2026-09-10", "venue": "Venue unavailable"},
        {"team": "Florida A&M", "record_text": "0-0"},
        {"team": "Miami (FL)", "record_text": "0-0", "ap_rank": None},
    )
    assert g == corrected_game
    assert a == corrected_away
    assert h == corrected_home


def test_hero_passes_reconciled_profiles_into_frozen_stack(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        ui.deep_data,
        "reconcile_matchup",
        lambda game, day: ({
            "game": {
                "game_date": "2026-09-10",
                "venue": "Hard Rock Stadium",
                "broadcast": "ACC Network",
            },
            "away": {"team": "Florida A&M", "record_text": "1-1"},
            "home": {"team": "Miami (FL)", "record_text": "1-0", "ap_rank": 7},
        }, {}),
    )

    def frozen_hero(game, away, home):
        captured["game"] = dict(game)
        captured["away"] = dict(away)
        captured["home"] = dict(home)
        return "FROZEN"

    monkeypatch.setattr(ui.frozen_v14, "_FROZEN_V13_HERO", frozen_hero)
    monkeypatch.setattr(
        ui.frozen_v14,
        "_current_data_panel",
        lambda game, away, home: "PANEL",
    )

    html = ui._hero_v15(
        {"game_date": "2026-09-10", "venue": "Venue unavailable"},
        {"team": "Florida A&M", "record_text": "0-0"},
        {"team": "Miami (FL)", "record_text": "0-0", "ap_rank": None},
    )

    assert html == "FROZENPANEL"
    assert captured["game"]["venue"] == "Hard Rock Stadium"
    assert captured["game"]["broadcast"] == "ACC Network"
    assert captured["away"]["record_text"] == "1-1"
    assert captured["home"]["record_text"] == "1-0"
    assert captured["home"]["ap_rank"] == 7


def test_render_temporarily_routes_visible_schedule_through_v4(monkeypatch):
    seen = {}

    def fake_render(*args, **kwargs):
        seen["hero"] = ui.frozen_v14._hero_v14
        seen["base_schedule"] = ui.base_hub.schedule
        seen["step1_schedule"] = ui.step1_ui.schedule
        return "ok"

    monkeypatch.setattr(ui.frozen_v14, "render_over_under_hub", fake_render)
    original_hero = ui.frozen_v14._hero_v14
    original_base = ui.base_hub.schedule
    original_step1 = ui.step1_ui.schedule

    assert ui.render_over_under_hub() == "ok"
    assert seen["hero"] is ui._hero_v15
    assert seen["base_schedule"] is schedule_v4
    assert seen["step1_schedule"] is schedule_v4
    assert ui.frozen_v14._hero_v14 is original_hero
    assert ui.base_hub.schedule is original_base
    assert ui.step1_ui.schedule is original_step1


def test_router_v55_routes_only_cfb_over_under(monkeypatch):
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

    router._render_nfl_or_cfb_v55("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v15_visible_data_path"
    assert seen["market"] == "Over/Under"


def test_router_v55_delegates_non_target_routes(monkeypatch):
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
    router._render_nfl_or_cfb_v55("Moneyline")
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v55("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]
