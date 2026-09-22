from __future__ import annotations

import inspect
from types import SimpleNamespace

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
    assert router.HTML_RENDER_GUARD_SCOPE == "route_purge_reimport_safe"


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
    assert router.spread_v4._KSP4_HTML_RENDER_GUARD == router.HTML_RENDER_GUARD


def test_v135_reapplies_html_guard_to_post_purge_route_import(monkeypatch) -> None:
    raw_card = """
    <article class="ksp4-matchup-card">
      <section class="ksp4-team-panel ksp4-away">Away</section>
      <div class="ksp4-vs">VS</div>
      <section class="ksp4-team-panel ksp4-home">Home</section>
    </article>
    """
    raw_summary = """
    <div class="ksp4-summary-grid">
      <div class="ksp4-summary-tile">Summary</div>
    </div>
    """
    fresh_v4 = SimpleNamespace(
        _matchup_card=lambda *args, **kwargs: raw_card,
        _summary_html=lambda *args, **kwargs: raw_summary,
    )
    imported: list[str] = []
    rendered: list[str] = []

    def fake_route_import(name: str):
        imported.append(name)
        return fresh_v4

    def fake_prior_render_app() -> None:
        module = router.route_v132.root._import(router.ACTIVE_SPREAD_HUB)
        rendered.append(module._matchup_card())
        rendered.append(module._summary_html())

    monkeypatch.setattr(router.route_v132.root, "_import", fake_route_import)
    monkeypatch.setattr(router.prior, "render_app", fake_prior_render_app)

    router.render_app()

    assert imported == ["nfl_spread_hub_v4"]
    assert len(rendered) == 2
    assert all("\n" not in html for html in rendered)
    assert '<div class="ksp4-vs">VS</div>' in rendered[0]
    assert '<section class="ksp4-team-panel ksp4-away">Away</section>' in rendered[0]
    assert '<section class="ksp4-team-panel ksp4-home">Home</section>' in rendered[0]
    assert '<div class="ksp4-summary-grid">' in rendered[1]
    assert fresh_v4._KSP4_HTML_RENDER_GUARD == router.HTML_RENDER_GUARD
    assert router.route_v132.root._import is fake_route_import


def test_v135_non_spread_import_is_not_modified() -> None:
    module = SimpleNamespace()

    def importer(name: str):
        return module

    assert router._guard_route_import(importer, "not_nfl_spread_v4") is module
    assert not hasattr(module, "_KSP4_HTML_RENDER_GUARD")


def test_v135_source_has_no_model_or_market_reimplementation() -> None:
    source = inspect.getsource(router)
    assert "import streamlit_memory_lazy_router_v134 as prior" in source
    assert "import streamlit_memory_lazy_router_v132 as route_v132" in source
    assert "import nfl_spread_hub_v4 as spread_v4" in source
    assert 'ACTIVE_SPREAD_HUB = "nfl_spread_hub_v4"' in source
    assert "nfl_spread_model_v1" not in source
    assert "nfl_spread_mc_v1" not in source
    assert "nfl_spread_hub_v1" not in source
    assert "fetch" not in source.lower()
    assert "simulate" not in source.lower()
