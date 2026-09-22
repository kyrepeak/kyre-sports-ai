from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v77 as router

ROOT = Path(__file__).resolve().parents[1]


class _FakeST:
    def __init__(self, session_state=None, query_params=None):
        self.session_state = dict(session_state or {})
        self.query_params = dict(query_params or {})


def test_v77_keeps_frozen_v76_lazy_on_fast_import_path():
    source = (ROOT / "streamlit_memory_lazy_router_v77.py").read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v76"' in source
    assert "import streamlit_memory_lazy_router_v76 as prior" not in source
    assert "importlib.import_module(FROZEN_ROUTER)" in source
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v35"' in source
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")


def test_v77_restores_only_exact_cfb_over_under_query(monkeypatch):
    fake = _FakeST(
        query_params={
            router.ROUTE_QUERY_SPORT: router.CFB_SPORT_LABEL,
            router.ROUTE_QUERY_MARKET: router.OVER_UNDER_MARKET,
        }
    )
    monkeypatch.setattr(router, "st", fake)

    assert router._restore_fast_route_from_query() is True
    assert fake.session_state["ks_sport_touch"] == router.CFB_SPORT_LABEL
    assert fake.session_state["ks_cfb_market_touch"] == router.OVER_UNDER_MARKET
    assert router._fast_route_active() is True


def test_v77_does_not_override_existing_widget_state(monkeypatch):
    fake = _FakeST(
        session_state={"ks_sport_touch": "MLB"},
        query_params={
            router.ROUTE_QUERY_SPORT: router.CFB_SPORT_LABEL,
            router.ROUTE_QUERY_MARKET: router.OVER_UNDER_MARKET,
        },
    )
    monkeypatch.setattr(router, "st", fake)

    assert router._restore_fast_route_from_query() is False
    assert fake.session_state["ks_sport_touch"] == "MLB"


def test_v77_query_persistence_and_clear_are_exact(monkeypatch):
    fake = _FakeST()
    monkeypatch.setattr(router, "st", fake)

    router._persist_fast_route_query()
    assert fake.query_params == {
        router.ROUTE_QUERY_SPORT: router.CFB_SPORT_LABEL,
        router.ROUTE_QUERY_MARKET: router.OVER_UNDER_MARKET,
    }

    router._clear_fast_route_query()
    assert fake.query_params == {}


def test_app_keeps_frozen_contracts_static_but_runtime_imports_only_v77():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "if TYPE_CHECKING:" in source
    assert "from streamlit_memory_lazy_router_v63 import render_app" in source
    assert "from streamlit_memory_lazy_router_v76 import render_app" in source
    assert "from streamlit_memory_lazy_router_v77 import record_bootstrap_import_ms, render_app" in source
    assert "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11" in source
