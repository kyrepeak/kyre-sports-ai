from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import nfl_passing_yards_hub_v31 as page
import streamlit_memory_lazy_router_v124 as router


def test_v31_is_additive_display_only_step4_over_frozen_v30():
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v30"
    assert page.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"
    assert page.VISUAL_BUILD_STEP == 4
    assert page.VISUAL_BUILD_TOTAL == 6
    assert page.DISPLAY_ONLY is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_step4_context_css_covers_all_frozen_context_card_families():
    css = page._STEP4_CONTEXT_CSS
    for selector in (
        ".kpy-defense",
        ".kpy-pressure",
        ".kpy-personnel",
        ".kpy-env",
        ".kpy-dmetric",
        ".kpy-xmetric",
        ".kpy-imetric",
        ".kpy-envmetric",
        ".kpy28-weapon-pill",
        ".kpy-envteam",
    ):
        assert selector in css

    # Locked green/black visual family used by certified Passing Steps 2-3.
    for token in ("#2b4b39", "#0b1712", "#09140f", "#8be2ac", "#91cda4"):
        assert token in css
    assert "@media(max-width:820px)" in css
    assert "!important" in css


def test_step4_preserves_semantic_context_states_in_visual_css():
    css = page._STEP4_CONTEXT_CSS
    for semantic_class in (
        ".kpy-grade.favorable",
        ".kpy-grade.tough",
        ".kpy-grade.balanced",
        ".kpy-xgrade.low-pressure",
        ".kpy-xgrade.high-pressure",
        ".kpy-xgrade.moderate",
        ".kpy-ilabel.help",
        ".kpy-ilabel.hurt",
        ".kpy-envlabel.controlled",
        ".kpy-envlabel.watch",
    ):
        assert semantic_class in css


def test_visual_build_banner_advances_to_step4_of6():
    html = page._visual_build_banner_v31()
    assert "Visual Parity Build" in html
    assert "VISUAL STEP 4 / 6" in html
    assert "V30 + V28 FROZEN" in html
    assert "SPORTSBOOK 0%" in html
    assert 'style="width:66.666%"' in html
    assert "Opponent defense, pressure, weapons/injuries, and game environment" in html


def test_render_temporarily_applies_context_css_and_banner_then_restores(monkeypatch):
    original_css = page.prior._STEP3_VISUAL_CSS
    original_banner = page.prior._visual_build_banner_v30

    def boom():
        assert page._STEP4_CONTEXT_CSS in page.prior._STEP3_VISUAL_CSS
        assert page.prior._visual_build_banner_v30 is page._visual_build_banner_v31
        raise RuntimeError("stop inside frozen V30")

    monkeypatch.setattr(page.prior, "render_nfl_passing_yards_hub", boom)
    with pytest.raises(RuntimeError, match="stop inside frozen V30"):
        page.render_nfl_passing_yards_hub()

    assert page.prior._STEP3_VISUAL_CSS == original_css
    assert page.prior._visual_build_banner_v30 is original_banner


def test_v31_is_presentation_only_and_does_not_own_context_or_model_math():
    source = Path("nfl_passing_yards_hub_v31.py").read_text()
    render_source = inspect.getsource(page.render_nfl_passing_yards_hub)

    for forbidden in (
        "nfl_passing_yards_projection",
        "nfl_passing_yards_distribution",
        "nfl_passing_yards_market_edge",
        "projection_yards",
        "fair_odds",
        "no_vig",
        "expected_value",
        "stake_size",
        "projection_adjustment",
        "over_odds",
        "under_odds",
    ):
        assert forbidden not in source
        assert forbidden not in render_source

    assert "build_pass_defense_profile" not in source
    assert "build_pressure_matchup" not in source
    assert "build_personnel_matchup" not in source
    assert "build_environment_context" not in source


def test_router_v124_advances_only_passing(monkeypatch):
    called: list[str] = []

    monkeypatch.setattr(router, "_passing_route_active", lambda: True)
    monkeypatch.setattr(router, "_render_direct_passing", lambda: called.append("passing"))
    monkeypatch.setattr(router.prior, "render_app", lambda: called.append("prior"))
    router.render_app()
    assert called == ["passing"]

    called.clear()
    monkeypatch.setattr(router, "_passing_route_active", lambda: False)
    router.render_app()
    assert called == ["prior"]

    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v123"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v31"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_router_direct_handler_rejects_non_passing_markets():
    with pytest.raises(RuntimeError, match="Passing Yards only"):
        router._render_nfl_v124("Receiving Yards")


def test_app_activates_v124_and_preserves_v123_rollback():
    text = Path("app.py").read_text()
    assert "FROZEN_V123_DEPLOYMENT_HEARTBEAT" in text
    assert "STREAMLIT_MAIN_V123_NFL_PASSING_YARDS_VISUAL_PARITY_STEP3_QB_PROFILE_2026-09-13" in text
    assert "STREAMLIT_MAIN_V124_NFL_PASSING_YARDS_VISUAL_PARITY_STEP4_CONTEXT_CARDS_2026-09-13" in text
    assert "from streamlit_memory_lazy_router_v123 import record_bootstrap_import_ms, render_app" in text
    assert "from streamlit_memory_lazy_router_v124 import record_bootstrap_import_ms, render_app" in text
