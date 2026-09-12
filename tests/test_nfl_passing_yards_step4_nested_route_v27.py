from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_hub_v19 as v19
import nfl_passing_yards_hub_v25 as v25
import nfl_passing_yards_hub_v27 as v27
import nfl_passing_yards_pressure_v5 as pressure_v5


ROOT = Path(__file__).resolve().parents[1]


def test_v27_defeats_v25_nested_pressure_v4_shadow_and_restores(monkeypatch) -> None:
    """Prove the real V27 -> V26 -> V25 nesting resolves Step 4 to Pressure V5."""
    original_v25_module = v25.pressure_v4
    original_v19_module = v19.pressure_v3
    observed = {}

    def fake_v24_render():
        # At this exact point V26 has applied its V19 proxy and V25 has then
        # applied its own proxy. The final active build must still resolve to V5.
        observed["active_builder"] = v19.pressure_v3.build_pressure_matchup
        observed["v25_builder"] = v25.pressure_v4.build_pressure_matchup
        return "nested-rendered"

    monkeypatch.setattr(v25.prior, "render_nfl_passing_yards_hub", fake_v24_render)
    assert v27.render_nfl_passing_yards_hub() == "nested-rendered"
    assert observed["active_builder"] is pressure_v5.build_pressure_matchup
    assert observed["v25_builder"] is pressure_v5.build_pressure_matchup
    assert v25.pressure_v4 is original_v25_module
    assert v19.pressure_v3 is original_v19_module


def test_v27_proxy_forwards_frozen_v25_pressure_module_surface() -> None:
    proxy = v27._PressureV5ModuleProxy(v25.pressure_v4)
    assert proxy.build_pressure_matchup is pressure_v5.build_pressure_matchup
    assert proxy.FROZEN_PRIOR == v25.pressure_v4.FROZEN_PRIOR


def test_router_advances_only_passing_yards_to_v27_and_keeps_v26_contract() -> None:
    source = (ROOT / "nfl_hub_v35.py").read_text(encoding="utf-8")
    assert "from nfl_passing_yards_hub_v26 import render_nfl_passing_yards_hub as render_v26" in source
    assert "return render_v26()" in source
    assert "from nfl_passing_yards_hub_v27 import render_nfl_passing_yards_hub as render_v27" in source
    assert "return render_v27()" in source
    assert 'if market == "Passing Yards"' in source
    assert "return base.render_nfl_hub(market)" in source
    assert "0.0% sportsbook projection influence" in source


def test_v27_is_route_only_and_contains_no_model_or_market_math() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v27.py").read_text(encoding="utf-8")
    assert "pressure_v5.build_pressure_matchup" in source
    assert "finally" in source
    for forbidden in (
        "evaluate_market",
        "projection_yards",
        "over_ev",
        "under_ev",
        "fair_odds",
        "monte_carlo",
        "sportsbook_influence = 1",
    ):
        assert forbidden not in source
