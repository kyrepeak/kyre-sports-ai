from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import nfl_passing_yards_hub_v31 as prior
import nfl_passing_yards_hub_v32 as page
import streamlit_memory_lazy_router_v125 as router


def test_v32_is_display_only_step5_over_frozen_v31_v28() -> None:
    assert page.DISPLAY_ONLY is True
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v31"
    assert page.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"
    assert page.VISUAL_BUILD_STEP == 5
    assert page.VISUAL_BUILD_TOTAL == 6
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    banner = page._visual_build_banner_v32()
    assert "VISUAL STEP 5 / 6" in banner
    assert "V31 + V28 FROZEN" in banner
    assert "SPORTSBOOK 0%" in banner
    assert 'style="width:83.333%"' in banner


def test_v32_targets_every_frozen_analytical_card_family() -> None:
    css = page._STEP5_ANALYTICS_CSS
    for selector in (
        "section.kpy-proj",
        "section.kpy8-card",
        "section.kpy9-card",
        "section.kpy10-card",
        ".kpy-projhero>div",
        ".kpy8-hero>div",
        ".kpy9-hero>div",
        ".kpy10-hero>div",
        ".kpy-projmeta>div",
        ".kpy8-meta>div",
        ".kpy9-q>div",
        ".kpy10-metrics>div",
        ".kpy8-active",
        ".kpy9-active",
        ".kpy10-active",
    ):
        assert selector in css

    assert "border:1px solid #2b4b39!important" in css
    assert "border-radius:16px!important" in css
    assert "linear-gradient(145deg,#0b1712" in css
    assert "background:#09140f!important" in css


def test_v32_temporarily_layers_css_and_restores_frozen_v31(monkeypatch) -> None:
    original_css = prior._STEP4_CONTEXT_CSS
    original_banner = prior._visual_build_banner_v31
    observed: dict[str, object] = {}

    def fake_render() -> None:
        observed["css"] = prior._STEP4_CONTEXT_CSS
        observed["banner"] = prior._visual_build_banner_v31

    monkeypatch.setattr(prior, "render_nfl_passing_yards_hub", fake_render)
    page.render_nfl_passing_yards_hub()

    assert page._STEP5_ANALYTICS_CSS in str(observed["css"])
    assert observed["banner"] is page._visual_build_banner_v32
    assert prior._STEP4_CONTEXT_CSS == original_css
    assert prior._visual_build_banner_v31 is original_banner


def test_v32_render_owns_no_analytical_recomputation() -> None:
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


def test_router_v125_advances_only_passing_to_v32(monkeypatch) -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v124"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v32"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    calls: list[tuple[str, str]] = []

    class FakeModule:
        @staticmethod
        def render_nfl_hub(market: str) -> None:
            calls.append(("render", market))

    monkeypatch.setattr(router.root, "_import", lambda name: (calls.append(("import", name)) or FakeModule))
    router._render_nfl_v125("Passing Yards")
    assert calls == [("import", "nfl_passing_yards_hub_v32"), ("render", "Passing Yards")]

    with pytest.raises(RuntimeError):
        router._render_nfl_v125("Rushing Yards")


def test_app_activates_v125_and_preserves_v124_heartbeat() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'FROZEN_V124_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V124_NFL_PASSING_YARDS_VISUAL_PARITY_STEP4_CONTEXT_CARDS_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V125_NFL_PASSING_YARDS_VISUAL_PARITY_STEP5_ANALYTICAL_READOUTS_2026-09-13"' in source
    assert "from streamlit_memory_lazy_router_v125 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v124 import render_app as _frozen_v124_render_app" in source


def test_v32_public_surface_has_no_new_model_or_market_owner_imports() -> None:
    module_source = inspect.getsource(page)
    assert "import nfl_passing_yards_hub_v31 as prior" in module_source
    for forbidden_import in (
        "import nfl_passing_yards_projection_v1",
        "import nfl_passing_yards_distribution_v1",
        "import nfl_passing_yards_market_v1",
        "import nfl_passing_yards_market_api_v1",
    ):
        assert forbidden_import not in module_source
