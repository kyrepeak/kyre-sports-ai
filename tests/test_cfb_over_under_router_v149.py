from __future__ import annotations

import importlib
import importlib.util
import inspect
from pathlib import Path


def _load(name: str):
    spec = importlib.util.find_spec(name)
    assert spec is not None, f"expected V149 module {name} to exist"
    return importlib.import_module(name)


def test_v149_page_is_additive_over_frozen_v37() -> None:
    page = _load("cfb_over_under_clean_page_v38")
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v37"
    assert page.MARKET == "Over/Under"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_v149_page_exposes_compact_presentation_contract() -> None:
    page = _load("cfb_over_under_clean_page_v38")
    assert page.PHOENIX_TIMEZONE == "America/Phoenix"
    assert page.ACTIVE_LOGO_RESOLVER == "cfb_over_under_logo_resolver_v3"
    source = inspect.getsource(page)
    assert "Quick Read" in source
    assert "Steps 5–10" in source or "Steps 5-10" in source
    assert "st.expander" in source


def test_v149_router_targets_only_exact_cfb_over_under_state() -> None:
    router = _load("streamlit_memory_lazy_router_v149")
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v148"
    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v38"
    assert router.CFB_SPORT_LABEL == "College Football"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
    source = inspect.getsource(router._over_under_route_active)
    assert "ks_sport_touch" in source
    assert "ks_cfb_market_touch" in source
    assert "CFB_SPORT_LABEL" in source
    assert "OVER_UNDER_MARKET" in source


def test_v149_router_restores_root_hooks_after_direct_render() -> None:
    router = _load("streamlit_memory_lazy_router_v149")
    source = inspect.getsource(router._render_direct_cfb_over_under)
    assert "original_selectbox" in source
    assert "original_render_nfl" in source
    assert "original_prefixes" in source
    assert "finally:" in source
    assert "root.st.selectbox = original_selectbox" in source
    assert "root._render_nfl = original_render_nfl" in source
    assert "root._ROUTE_MODULE_PREFIXES = original_prefixes" in source


def test_v149_app_bootstrap_is_active_and_v148_is_frozen() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'FROZEN_V148_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V148_CFB_MONEYLINE_MONSTER_DASHBOARD_2026-09-16"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_DASHBOARD_2026-09-16"' in source
    assert "from streamlit_memory_lazy_router_v149 import record_bootstrap_import_ms, render_app" in source
