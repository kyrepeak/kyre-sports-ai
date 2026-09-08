"""Regression checks for mixed-division CFB Moneyline hotfix wrapper."""
from __future__ import annotations

import cfb_moneyline_hub_v3 as hub


def test_wrapper_is_additive_over_frozen_step5():
    assert hub.FROZEN_CFB_MONEYLINE_HUB == "cfb_moneyline_hub_v2"
    assert hub.MARKET == "Moneyline"


def test_render_temporarily_swaps_only_data_providers(monkeypatch):
    original_schedule = hub.prior.schedule
    original_team_data = hub.prior.team_data
    seen = {}

    def fake_render(*args, **kwargs):
        seen["schedule"] = hub.prior.schedule
        seen["team_data"] = hub.prior.team_data

    monkeypatch.setattr(hub.prior, "render_moneyline_hub", fake_render)
    monkeypatch.setattr(hub.st, "caption", lambda *a, **k: None)

    hub.render_moneyline_hub()

    assert seen["schedule"] is hub.schedule_v2
    assert seen["team_data"] is hub.team_data_v2
    assert hub.prior.schedule is original_schedule
    assert hub.prior.team_data is original_team_data


def test_non_moneyline_delegates_to_frozen_hub(monkeypatch):
    seen = []
    monkeypatch.setattr(
        hub.prior,
        "render_cfb_hub",
        lambda market, *args: seen.append(market),
    )
    hub.render_cfb_hub("Over/Under")
    hub.render_cfb_hub("Game Total")
    assert seen == ["Over/Under", "Game Total"]
