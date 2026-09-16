from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v37 as page
import streamlit_memory_lazy_router_v149 as router


def test_v37_is_presentation_only_over_certified_v36() -> None:
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v36"
    assert page.MARKET == "Over/Under"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.ACTIVE_LOGO_RESOLVER == "cfb_over_under_logo_resolver_v3"


def test_v37_uses_phoenix_time_and_exact_logo_resolver() -> None:
    source = inspect.getsource(page)
    assert 'ZoneInfo("America/Phoenix")' in source
    assert "_kickoff_phoenix" in source
    assert "logo_v3.resolve_visuals" in source
    assert "runtime_display._find_snapshot" in source
    assert "runtime_display._merge_game_snapshot" in source


def test_v37_keeps_model_flow_but_compacts_steps_5_through_10() -> None:
    source = inspect.getsource(page.render_over_under_hub)
    assert "runtime_slate.analyze_game" in source
    assert 'result.get("explosive_engine")' in source
    assert 'result.get("red_zone_engine")' in source
    assert 'result.get("third_down_engine")' in source
    assert 'result.get("turnover_engine")' in source
    assert 'result.get("environment_engine")' in source
    assert 'result.get("history_engine")' in source
    assert "_render_factor_cards" in source
    assert "st.expander" in source


def test_v37_preserves_deep_evidence_and_full_slate_scan() -> None:
    source = inspect.getsource(page.render_over_under_hub)
    assert "_model_step" in source
    assert "_step3_readable" in source
    assert "scan_slate" in source
    assert "rank_slate" in source
    assert "st.data_editor" in source


def test_v149_is_additive_over_v148_and_targets_only_cfb_over_under() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v148"
    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v37"
    assert router.CFB_SPORT_LABEL == "College Football"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False

    route_source = inspect.getsource(router._over_under_route_active)
    assert "ks_sport_touch" in route_source
    assert "ks_cfb_market_touch" in route_source


def test_v149_restores_root_router_hooks_after_direct_render() -> None:
    source = inspect.getsource(router._render_direct_cfb_over_under)
    assert "original_selectbox" in source
    assert "original_render_nfl" in source
    assert "original_prefixes" in source
    assert "finally:" in source
    assert "root.st.selectbox = original_selectbox" in source
    assert "root._render_nfl = original_render_nfl" in source
    assert "root._ROUTE_MODULE_PREFIXES = original_prefixes" in source
