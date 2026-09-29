from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v245 as router


APP = Path("app.py").read_text(encoding="utf-8")
ROUTER = Path("streamlit_memory_lazy_router_v245.py").read_text(encoding="utf-8")


def test_v245_is_additive_over_frozen_v244():
    assert 'import streamlit_memory_lazy_router_v244 as prior' in ROUTER
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v244"
    assert router.MAY_MODIFY_TOP_PICKS_PRODUCT is False
    assert router.MAY_MODIFY_EXISTING_CFB_PRODUCTS is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.HISTORY_PROJECTION_INFLUENCE == 0.0


def test_v245_app_entrypoint_is_active():
    assert "from streamlit_memory_lazy_router_v245 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V244 compatibility" in APP


def test_v245_appends_top_picks_only_to_cfb_market_selector(monkeypatch):
    calls = []

    def fake_selectbox(label, options, *args, **kwargs):
        calls.append((label, list(options), args, kwargs))
        return list(options)[0]

    monkeypatch.setattr(router.st, "selectbox", fake_selectbox)

    def callback():
        router.st.selectbox(
            "🎯 CFB Market",
            ["Moneyline", "Over/Under", "Game Total"],
            key="ks_cfb_market_touch",
        )
        router.st.selectbox("🎯 NFL Market", ["Moneyline", "Spread"])

    router._with_top_picks_selectbox(callback)

    assert calls[0][1] == ["Moneyline", "Over/Under", "Game Total", "Top Picks"]
    assert calls[0][1].count("Top Picks") == 1
    assert calls[1][1] == ["Moneyline", "Spread"]


def test_v245_does_not_duplicate_existing_top_picks(monkeypatch):
    seen = []

    def fake_selectbox(label, options, *args, **kwargs):
        seen.extend(list(options))
        return list(options)[0]

    monkeypatch.setattr(router.st, "selectbox", fake_selectbox)
    router._with_top_picks_selectbox(
        lambda: router.st.selectbox(
            "🎯 CFB Market",
            ["Moneyline", "Over/Under", "Game Total", "Top Picks"],
        )
    )
    assert seen.count("Top Picks") == 1
