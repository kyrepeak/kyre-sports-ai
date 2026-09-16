from __future__ import annotations

import inspect

import streamlit_memory_lazy_router_v148 as router


def test_v148_is_additive_over_frozen_v147() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v147"
    assert router.ACTIVE_PAGE == "cfb_moneyline_clean_page_v1"
    assert router.CFB_SPORT_LABEL == "College Football"
    assert router.MONEYLINE_MARKET == "Moneyline"


def test_v148_preserves_frozen_model_boundary() -> None:
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_v148_targets_only_exact_cfb_moneyline_state() -> None:
    source = inspect.getsource(router._moneyline_route_active)
    assert 'ks_sport_touch' in source
    assert 'ks_cfb_market_touch' in source
    assert 'CFB_SPORT_LABEL' in source
    assert 'MONEYLINE_MARKET' in source


def test_v148_restores_root_router_hooks_after_direct_render() -> None:
    source = inspect.getsource(router._render_direct_cfb_moneyline)
    assert 'original_selectbox' in source
    assert 'original_render_nfl' in source
    assert 'original_prefixes' in source
    assert 'finally:' in source
    assert 'root.st.selectbox = original_selectbox' in source
    assert 'root._render_nfl = original_render_nfl' in source
    assert 'root._ROUTE_MODULE_PREFIXES = original_prefixes' in source


def test_v148_injects_frozen_evidence_styles_without_editing_frozen_owner() -> None:
    source = inspect.getsource(router._install_frozen_moneyline_styles)
    assert 'cfb_moneyline_hub_v5' in source
    assert '_STEP3_CSS' in source
    assert 'frozen._CSS' in source
