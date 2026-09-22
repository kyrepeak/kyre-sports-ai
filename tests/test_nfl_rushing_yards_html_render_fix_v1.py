from pathlib import Path

import nfl_rushing_yards_hub_v1 as context_page
import nfl_rushing_yards_hub_v2 as projection_page
import nfl_rushing_yards_hub_v3 as market_page
import nfl_rushing_yards_hub_v10 as frozen_v10
import nfl_rushing_yards_hub_v11 as page
import streamlit_memory_lazy_router_v106 as frozen_router
import streamlit_memory_lazy_router_v107 as router


def test_v11_is_display_only_additive_over_frozen_v10():
    assert page.FROZEN_PRIOR == "nfl_rushing_yards_hub_v10"
    assert page.DISPLAY_ONLY is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert frozen_v10.FROZEN_PRIOR == "nfl_rushing_yards_hub_v9"


def test_html_normalizer_removes_markdown_code_indentation_only():
    raw = """
        <article class="krush-proj">
          <div>63.2</div>
        </article>
    """
    normalized = page._normalize_html(raw)
    assert normalized.startswith('<article class="krush-proj">')
    assert normalized.endswith("</article>")
    assert "63.2" in normalized
    assert not normalized.startswith("    ")


def test_normalized_builder_preserves_non_string_values_and_card_content():
    token = {"same": "object"}
    assert page._normalize_html(token) is token

    wrapped = page._normalized_builder(lambda value: f"\n        <article>{value}</article>\n    ")
    assert wrapped("SAFE") == "<article>SAFE</article>"


def test_v11_targets_only_three_historical_html_builders():
    source = Path("nfl_rushing_yards_hub_v11.py").read_text()
    assert "context_page._game_card" in source
    assert "projection_page._projection_card" in source
    assert "market_page._market_card" in source
    assert "prior.render_nfl_rushing_yards_hub()" in source
    assert "finally:" in source
    assert "build_event_projections" not in source
    assert "fetch_event_market" not in source
    assert "market_for_athlete" not in source


def test_frozen_historical_card_builders_remain_present_and_unchanged_owners():
    assert callable(context_page._game_card)
    assert callable(projection_page._projection_card)
    assert callable(market_page._market_card)
    assert context_page.MODEL_VERSION.startswith("NFL RUSHING YARDS V1")
    assert projection_page.MODEL_VERSION.startswith("NFL RUSHING YARDS V2")
    assert market_page.MODEL_VERSION.startswith("NFL RUSHING YARDS V3")


def test_router_v107_advances_only_active_rushing_page_owner():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v106"
    assert router.ACTIVE_PAGE == "nfl_rushing_yards_hub_v11"
    assert router.RUSHING_YARDS_MARKET == frozen_router.RUSHING_YARDS_MARKET == "Rushing Yards"


def test_router_v107_restores_frozen_v106_active_page_after_render(monkeypatch):
    original = frozen_router.ACTIVE_PAGE
    observed = []

    def fake_render():
        observed.append(frozen_router.ACTIVE_PAGE)

    monkeypatch.setattr(frozen_router, "render_app", fake_render)
    router.render_app()
    assert observed == ["nfl_rushing_yards_hub_v11"]
    assert frozen_router.ACTIVE_PAGE == original


def test_app_activates_v107_and_preserves_v106_heartbeat():
    source = Path("app.py").read_text()
    assert "streamlit_memory_lazy_router_v107 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V106_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V106_NFL_RUSHING_YARDS_PERFORMANCE_FAST_ROUTE_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V107_NFL_RUSHING_YARDS_HTML_RENDER_REPAIR_2026-09-12"' in source


def test_display_repair_does_not_enable_betting_actions_or_sportsbook_influence():
    source = Path("nfl_rushing_yards_hub_v11.py").read_text()
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    forbidden = ("probability_enabled = True", "ev_enabled = True", "grading_enabled = True", "wager_actions = True")
    assert not any(token in source for token in forbidden)
