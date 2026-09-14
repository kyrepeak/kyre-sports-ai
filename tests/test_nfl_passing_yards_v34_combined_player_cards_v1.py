from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import nfl_passing_yards_hub_v34 as page
import streamlit_memory_lazy_router_v127 as router


def test_v34_is_composition_only_over_frozen_v33_v28() -> None:
    assert page.DISPLAY_ONLY is True
    assert page.PLAYER_CARD_COMPOSITION_ONLY is True
    assert page.PLAYER_CARD_STEP_COUNT == 10
    assert page.FROZEN_PRIOR == "nfl_passing_yards_hub_v33"
    assert page.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False

    banner = page._visual_build_banner_v34()
    assert "Combined Player Cards" in banner
    assert "ALL 10 STEPS • PLAYER CARDS" in banner
    assert "V33 + V28 FROZEN" in banner
    assert "SPORTSBOOK 0%" in banner
    assert "no analytical recomputation" in banner


def test_split_top_level_children_preserves_generated_nested_cards() -> None:
    grid = (
        '<div class="kpy-qbgrid">'
        '<article class="one"><div><img src="x"><span>A</span></div></article>'
        '<article class="two"><div><b>B</b></div></article>'
        '</div>'
    )
    children = page._split_top_level_children(grid)
    assert len(children) == 2
    assert children[0].startswith('<article class="one">')
    assert children[0].endswith('</article>')
    assert '<img src="x">' in children[0]
    assert children[1].startswith('<article class="two">')
    assert children[1].endswith('</article>')


def test_combined_html_builds_two_complete_player_first_stacks() -> None:
    captured = {
        "identity": ['<article class="kpass29-card">Away QB</article>', '<article class="kpass29-card">Home QB</article>'],
        "profile": ['<section class="kpass30-profile">Away profile</section>', '<section class="kpass30-profile">Home profile</section>'],
        "defense": ['<section class="kpy-defense">Away defense</section>', '<section class="kpy-defense">Home defense</section>'],
        "pressure": ['<section class="kpy-pressure">Away pressure</section>', '<section class="kpy-pressure">Home pressure</section>'],
        "personnel": ['<section class="kpy-personnel">Away personnel</section>', '<section class="kpy-personnel">Home personnel</section>'],
        "environment": ['<section class="kpy-env">Shared environment</section>'],
        "projection": ['<section class="kpy-proj">Away projection</section>', '<section class="kpy-proj">Home projection</section>'],
        "context": ['<section class="kpy8-card">Away context</section>', '<section class="kpy8-card">Home context</section>'],
        "distribution": ['<section class="kpy9-card">Away distribution</section>', '<section class="kpy9-card">Home distribution</section>'],
        "market": ['<section class="kpy10-card">Away market</section>', '<section class="kpy10-card">Home market</section>'],
    }
    html = page._combined_player_cards_html(captured)
    assert html.count('class="kpass34-player"') == 2
    assert html.count('data-combined-step-count="10"') == 2
    assert html.count('class="kpass29-card"') == 2
    assert html.count('class="kpass30-profile"') == 2
    assert html.count('class="kpy-defense"') == 2
    assert html.count('class="kpy-pressure"') == 2
    assert html.count('class="kpy-personnel"') == 2
    assert html.count('class="kpy-env"') == 2
    assert html.count('class="kpy-proj"') == 2
    assert html.count('class="kpy8-card"') == 2
    assert html.count('class="kpy9-card"') == 2
    assert html.count('class="kpy10-card"') == 2
    for step in range(2, 11):
        assert html.count(f'data-passing-step="{step}"') == 2
    assert "Away QB" in html and "Home QB" in html
    assert html.count("Shared environment") == 2


def test_v34_render_is_analytical_value_blind() -> None:
    source = inspect.getsource(page.render_nfl_passing_yards_hub)
    assert "prior.render_nfl_passing_yards_hub()" in source
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
        "projection_adjustment",
        "stake_size",
    ):
        assert forbidden not in source, forbidden

    module_source = inspect.getsource(page)
    for forbidden_import in (
        "import nfl_passing_yards_projection_v1",
        "import nfl_passing_yards_context_v1",
        "import nfl_passing_yards_distribution_v1",
        "import nfl_passing_yards_market_v1",
        "import nfl_passing_yards_market_api_v1",
    ):
        assert forbidden_import not in module_source


def test_router_v127_advances_only_passing_to_v34(monkeypatch) -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v126"
    assert router.ACTIVE_PASSING_YARDS_HUB == "nfl_passing_yards_hub_v34"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    calls: list[tuple[str, str]] = []

    class FakeModule:
        @staticmethod
        def render_nfl_hub(market: str) -> None:
            calls.append(("render", market))

    monkeypatch.setattr(router.root, "_import", lambda name: (calls.append(("import", name)) or FakeModule))
    router._render_nfl_v127("Passing Yards")
    assert calls == [("import", "nfl_passing_yards_hub_v34"), ("render", "Passing Yards")]

    with pytest.raises(RuntimeError):
        router._render_nfl_v127("Receiving Yards")


def test_app_activates_v127_and_preserves_v126_descendant_anchor() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'FROZEN_V126_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V126_NFL_PASSING_YARDS_VISUAL_PARITY_STEP6_FINAL_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V127_NFL_PASSING_YARDS_COMBINED_PLAYER_CARDS_2026-09-13"' in source
    assert "from streamlit_memory_lazy_router_v126 import record_bootstrap_import_ms, render_app" in source
    assert "from streamlit_memory_lazy_router_v126 import render_app as _frozen_v126_render_app" in source
    assert "from streamlit_memory_lazy_router_v127 import record_bootstrap_import_ms, render_app" in source
