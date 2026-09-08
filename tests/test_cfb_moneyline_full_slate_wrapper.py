"""Regression checks for CFB Moneyline Hub V4 full-slate wrapper."""
from __future__ import annotations

import inspect

import cfb_moneyline_hub_v4 as hub


def test_v4_is_additive_over_frozen_mixed_division_hub():
    assert hub.FROZEN_CFB_MONEYLINE_HUB == "cfb_moneyline_hub_v3"
    assert hub.MARKET == "Moneyline"


def test_moneyline_render_uses_schedule_v3_and_frozen_team_model_stack():
    source = inspect.getsource(hub)
    assert "schedule_v3.load_with_diagnostics" in source
    assert "team_data_v2.load_matchup_team_data" in source
    assert "frozen_step5.model.project_matchup" in source

    forbidden = (
        "def win_probability",
        "fair_moneyline =",
        "expected_value =",
        "np.random",
        "def simulate",
        "prior.schedule =",
        "prior.team_data =",
    )
    for token in forbidden:
        assert token not in source


def test_non_moneyline_delegates_to_frozen_hotfix(monkeypatch):
    seen = []
    monkeypatch.setattr(
        hub.frozen_hotfix,
        "render_cfb_hub",
        lambda market, *args: seen.append(market),
    )

    hub.render_cfb_hub("Over/Under")
    hub.render_cfb_hub("Game Total")

    assert seen == ["Over/Under", "Game Total"]
