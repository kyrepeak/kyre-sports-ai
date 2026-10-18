from __future__ import annotations

import importlib
import sys
import types

MODULE = "cfb_top_picks_page_v10"


def _load(monkeypatch):
    fake_st = types.SimpleNamespace(
        query_params={},
        markdown=lambda *args, **kwargs: None,
        empty=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    sys.modules.pop(MODULE, None)
    return importlib.import_module(MODULE)


def test_market_query_normalization_and_safe_default(monkeypatch):
    page = _load(monkeypatch)
    assert page._normalize_market("Moneyline") == "MONEYLINE"
    assert page._normalize_market("spread") == "SPREAD"
    assert page._normalize_market("Over/Under") == "OVER/UNDER"
    assert page._normalize_market("totals") == "OVER/UNDER"
    assert page._normalize_market("not-a-market") == "MONEYLINE"


def test_market_tabs_are_real_click_targets_with_exactly_one_active(monkeypatch):
    page = _load(monkeypatch)
    html = page._market_tabs_html("SPREAD")
    assert html.count("<a ") == 3
    assert html.count("tp1-chip active") == 1
    assert 'data-market="MONEYLINE"' in html
    assert 'data-market="SPREAD"' in html
    assert 'data-market="OVER/UNDER"' in html
    assert "top_pick_market=SPREAD" in html
    assert "top_pick_market=MONEYLINE" in html
    assert "top_pick_market=OVER%2FUNDER" in html


def test_detail_href_preserves_selected_market_and_exact_event(monkeypatch):
    page = _load(monkeypatch)
    href = page._detail_href_for_market("401234567", "OVER/UNDER")
    assert "ks_sport=College+Football" in href
    assert "ks_cfb_market=Top+Picks" in href
    assert "top_pick_market=OVER%2FUNDER" in href
    assert "top_pick_detail=401234567" in href


def test_market_ranker_returns_only_selected_market_and_reranks(monkeypatch):
    page = _load(monkeypatch)
    candidates = [
        {"event_id": "1", "market": "MONEYLINE", "probability_value": 0.70, "reliability": 0.7},
        {"event_id": "2", "market": "SPREAD", "probability_value": 0.61, "reliability": 0.9},
        {"event_id": "3", "market": "SPREAD", "probability_value": 0.74, "reliability": 0.6},
        {"event_id": "4", "market": "SPREAD", "probability_value": 0.74, "reliability": 0.8},
        {"event_id": "5", "market": "OVER/UNDER", "probability_value": 0.81, "reliability": 0.9},
    ]
    out = page._rank_market(candidates, "SPREAD", limit=10)
    assert [row["event_id"] for row in out] == ["4", "3", "2"]
    assert [row["rank"] for row in out] == [1, 2, 3]
    assert all(row["market"] == "SPREAD" for row in out)


def test_page_html_replaces_static_tabs_and_preserves_market_on_card_links(monkeypatch):
    page = _load(monkeypatch)
    original = page.base._detail_href
    html = page._page_html(
        [{"rank": 1, "event_id": "401", "market": "SPREAD"}],
        {"games_analyzed": 1},
        "2026-10-24",
        selected_market="SPREAD",
    )
    assert page.base._detail_href is original
    assert 'data-testid="cfb-top-picks-market-tabs"' in html
    assert html.count("tp1-chip active") == 1
    assert 'data-market="SPREAD"' in html
    assert "top_pick_market=SPREAD" in html
    assert "top_pick_detail=401" in html
    assert "<div class=\"tp1-chip active\">Moneyline</div>" not in html


def test_router_successor_owns_v10_and_restores_parent_pointers(monkeypatch):
    calls = []
    seen = []
    owners = [types.SimpleNamespace(TOP_PICKS_PAGE="old8"), types.SimpleNamespace(TOP_PICKS_PAGE="old7"), types.SimpleNamespace(TOP_PICKS_PAGE="old6")]
    prior = types.ModuleType("streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9")
    prior.TOP_PICKS_PAGE = "cfb_top_picks_page_v9"
    prior._page_owner_chain = lambda: tuple(owners)
    prior._protect_cfb_detail_route = lambda: False
    prior.record_bootstrap_import_ms = lambda value: None

    def _render_app():
        seen.append([owner.TOP_PICKS_PAGE for owner in owners])
        calls.append("render")
        return "ok"

    prior.current_parent = types.SimpleNamespace(render_app=_render_app)
    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9", prior)
    sys.modules.pop("streamlit_memory_lazy_router_cfb_top_picks_market_tabs_r1", None)
    router = importlib.import_module("streamlit_memory_lazy_router_cfb_top_picks_market_tabs_r1")
    assert router.render_app() == "ok"
    assert calls == ["render"]
    assert seen == [[router.TOP_PICKS_PAGE, router.TOP_PICKS_PAGE, router.TOP_PICKS_PAGE]]
    assert [owner.TOP_PICKS_PAGE for owner in owners] == ["old8", "old7", "old6"]
