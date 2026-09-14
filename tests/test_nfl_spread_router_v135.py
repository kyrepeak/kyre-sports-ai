from __future__ import annotations

import inspect

import streamlit_memory_lazy_router_v135 as router


def test_v135_router_contract_is_additive_over_v134() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v134"
    assert router.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v4"
    assert router.SPREAD_MARKET == "Spread"
    assert router.PROJECTION_MODEL_ENABLED is True
    assert router.MONTE_CARLO_ENABLED is True
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STAKE_SIZING_ENABLED is False
    assert router.WAGER_ACTIONS_ENABLED is False
    assert router.HTML_RENDER_GUARD == "flatten_generated_html"


def test_v135_temporarily_swaps_only_spread_owner(monkeypatch) -> None:
    original = router.prior.ACTIVE_SPREAD_HUB
    seen: list[str] = []

    def fake_render_app() -> None:
        seen.append(router.prior.ACTIVE_SPREAD_HUB)

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen == ["nfl_spread_hub_v4"]
    assert router.prior.ACTIVE_SPREAD_HUB == original


def test_v135_html_render_guard_blocks_markdown_code_indentation() -> None:
    raw = """
    <article class="ksp4-matchup-card">
      <div class="ksp4-team-grid">
        <section class="ksp4-team-panel">Away</section>
        <div class="ksp4-vs">VS</div>
        <section class="ksp4-team-panel">Home</section>
      </div>
    </article>
    """

    safe = router._flatten_generated_html(raw)

    assert safe.startswith('<article class="ksp4-matchup-card">')
    assert '<div class="ksp4-vs">VS</div>' in safe
    assert '<section class="ksp4-team-panel">Away</section>' in safe
    assert '<section class="ksp4-team-panel">Home</section>' in safe
    assert "\n" not in safe
    assert router.spread_v4._matchup_card is router._html_safe_matchup_card
    assert router.spread_v4._summary_html is router._html_safe_summary_html


def test_v135_source_has_no_model_or_market_reimplementation() -> None:
    source = inspect.getsource(router)
    assert "import streamlit_memory_lazy_router_v134 as prior" in source
    assert "import nfl_spread_hub_v4 as spread_v4" in source
    assert 'ACTIVE_SPREAD_HUB = "nfl_spread_hub_v4"' in source
    assert "nfl_spread_model_v1" not in source
    assert "nfl_spread_mc_v1" not in source
    assert "nfl_spread_hub_v1" not in source
    assert "fetch" not in source.lower()
    assert "simulate" not in source.lower()
