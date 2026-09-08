"""Regression checks for mixed-division CFB Moneyline hotfix wrapper."""
from __future__ import annotations

import inspect

import cfb_moneyline_hub_v3 as hub


def test_wrapper_is_additive_over_frozen_step5():
    assert hub.FROZEN_CFB_MONEYLINE_HUB == "cfb_moneyline_hub_v2"
    assert hub.MARKET == "Moneyline"


def test_hotfix_render_never_mutates_frozen_provider_globals():
    source = inspect.getsource(hub)

    assert "schedule_v2.load_with_diagnostics" in source
    assert "team_data_v2.load_matchup_team_data" in source
    assert "prior.model.project_matchup" in source

    forbidden = (
        "prior.schedule =",
        "prior.team_data =",
        "setattr(prior",
        "__dict__[",
    )
    for token in forbidden:
        assert token not in source


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
