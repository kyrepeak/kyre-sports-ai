from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import nfl_passing_yards_hub_v32 as prior
import nfl_passing_yards_hub_v33 as page
import streamlit_memory_lazy_router_v126 as router


def test_v33_is_display_only_final_step_over_frozen_v32_v28() -> None:
    assert page.DISPLAY_ONLY is True
    assert page.FINAL_PAGE_COMPLETE is True
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v32"
    assert page.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"
    assert page.VISUAL_BUILD_STEP == page.VISUAL_BUILD_TOTAL == 6
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False

    banner = page._visual_build_banner_v33()
    assert "VISUAL STEP 6 / 6" in banner
    assert "FINAL CERTIFIED" in banner
    assert "V32 + V28 FROZEN" in banner
    assert "SPORTSBOOK 0%" in banner
    assert 'style="width:100%"' in banner
    assert "stake sizing OFF" in banner


def test_v33_final_css_only_marks_completion_state() -> None:
    css = page._STEP6_FINAL_CSS
    assert ".kpass29-fill{width:100%!important}" in css
    assert ".kpass29-buildchip.final" in css
    assert ".kpass33-finalnote" in css
    assert "#3d7651" in css


def test_v33_temporarily_layers_final_css_and_restores_v32(monkeypatch) -> None:
    original_css = prior._STEP5_ANALYTICS_CSS
    original_banner = prior._visual_build_banner_v32
    observed: dict[str, object] = {}

    def fake_render() -> None:
        observed["css"] = prior._STEP5_ANALYTICS_CSS
        observed["banner"] = prior._visual_build_banner_v32

    monkeypatch.setattr(prior, "render_nfl_passing_yards_hub", fake_render)
    page.render_nfl_passing_yards_hub()

    assert page._STEP6_FINAL_CSS in str(observed["css"])
    assert observed["banner"] is page._visual_build_banner_v33
    assert prior._STEP5_ANALYTICS_CSS == original_css
    assert prior._visual_build_banner_v32 is original_banner


def test_v33_render_owns_no_analytical_recomputation() -> None:
    source = inspect.getsource(page.render_nfl_passing_yards_hub)
    for forbidden in (
        "build_baseline_projection",
        "build_context_projection",
        "build_distribution",
        "evaluate_market",
        "projection_yards",
        "fair_odds",
        "no_vig",
        "over_ev",
        "under_ev",
        "stake_size",
        "projection_adjustment",
        "over_odds",
        "under_odds",
    ):
        assert forbidden not in source, forbidden


def test_router_v126_advances_only_passing_to_v33(monkeypatch) -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v125"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v33"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    calls: list[tuple[str, str]] = []

    class FakeModule:
        @staticmethod
        def render_nfl_hub(market: str) -> None:
            calls.append(("render", market))

    monkeypatch.setattr(router.root, "_import", lambda name: (calls.append(("import", name)) or FakeModule))
    router._render_nfl_v126("Passing Yards")
    assert calls == [("import", "nfl_passing_yards_hub_v33"), ("render", "Passing Yards")]

    with pytest.raises(RuntimeError):
        router._render_nfl_v126("Rushing Yards")


def test_app_activates_v126_and_preserves_v125_heartbeat() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'FROZEN_V125_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V125_NFL_PASSING_YARDS_VISUAL_PARITY_STEP5_ANALYTICAL_READOUTS_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V126_NFL_PASSING_YARDS_VISUAL_PARITY_STEP6_FINAL_2026-09-13"' in source
    assert "from streamlit_memory_lazy_router_v126 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v125 import render_app as _frozen_v125_render_app" in source


def test_v33_public_surface_has_no_new_model_or_market_owner_imports() -> None:
    module_source = inspect.getsource(page)
    assert "import nfl_passing_yards_hub_v32 as prior" in module_source
    for forbidden_import in (
        "import nfl_passing_yards_projection_v1",
        "import nfl_passing_yards_distribution_v1",
        "import nfl_passing_yards_market_v1",
        "import nfl_passing_yards_market_api_v1",
    ):
        assert forbidden_import not in module_source
