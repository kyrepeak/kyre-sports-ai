"""Regression tests for V16 runtime handoff and Router V56."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v16_runtime_team_data as ui
import cfb_schedule_v5_runtime_snapshot as schedule_v5
import streamlit_memory_lazy_router_v56 as router


def test_hero_v16_uses_profiles_it_is_given_without_refetch(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        ui.frozen_v14,
        "_FROZEN_V13_HERO",
        lambda game, away, home: (
            captured.update({
                "game": dict(game),
                "away": dict(away),
                "home": dict(home),
            })
            or "HERO"
        ),
    )
    monkeypatch.setattr(
        ui.frozen_v14,
        "_current_data_panel",
        lambda game, away, home: "PANEL",
    )

    html = ui._hero_v16(
        {"venue": "Hard Rock Stadium"},
        {"record_text": "1-1"},
        {"record_text": "1-0", "ap_rank": 7},
    )
    assert html == "HEROPANEL"
    assert captured["away"]["record_text"] == "1-1"
    assert captured["home"]["record_text"] == "1-0"


def test_render_patches_central_team_data_and_runtime_schedule(monkeypatch):
    seen = {}

    def fake_render(*args, **kwargs):
        seen["team_data"] = ui.base_hub.team_data
        seen["hero"] = ui.frozen_v15._hero_v15
        seen["deep_data"] = ui.deep_slate.deep_data
        seen["diag"] = ui.frozen_v14._team_data_diagnostics_v14
        seen["schedule"] = ui.frozen_v15.schedule_v4
        return "ok"

    monkeypatch.setattr(ui, "_reset_runtime_caches_once", lambda: None)
    monkeypatch.setattr(ui.frozen_v15, "render_over_under_hub", fake_render)

    original_team = ui.base_hub.team_data
    original_hero = ui.frozen_v15._hero_v15
    original_deep = ui.deep_slate.deep_data
    original_diag = ui.frozen_v14._team_data_diagnostics_v14
    original_sched = ui.frozen_v15.schedule_v4

    assert ui.render_over_under_hub() == "ok"
    assert seen["team_data"] is ui.runtime_team_data
    assert seen["hero"] is ui._hero_v16
    assert seen["deep_data"] is ui.runtime_deep
    assert seen["diag"] is ui._team_data_diagnostics_v16
    assert seen["schedule"] is schedule_v5

    assert ui.base_hub.team_data is original_team
    assert ui.frozen_v15._hero_v15 is original_hero
    assert ui.deep_slate.deep_data is original_deep
    assert ui.frozen_v14._team_data_diagnostics_v14 is original_diag
    assert ui.frozen_v15.schedule_v4 is original_sched


def test_runtime_diagnostic_green():
    html = ui._team_data_diagnostics_v16({
        "runtime_status": "GREEN",
        "runtime_snapshot_used": True,
        "runtime_issues": [],
    })
    assert "CURRENT TEAM DATA PATH GREEN" in html
    assert "verified local runtime snapshot" in html


def test_router_v56_only_advances_cfb_over_under(monkeypatch):
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

    router._render_nfl_or_cfb_v56("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v16_runtime_team_data"
    assert seen["market"] == "Over/Under"


def test_router_v56_delegates_other_routes(monkeypatch):
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
    router._render_nfl_or_cfb_v56("Moneyline")
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v56("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]
