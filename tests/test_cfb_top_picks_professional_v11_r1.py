from __future__ import annotations

import importlib
import sys
import types

MODULE = "cfb_top_picks_page_v11"


def _load(monkeypatch):
    fake_st = types.SimpleNamespace(query_params={}, markdown=lambda *a, **k: None, empty=lambda: None)
    fake_prior = types.ModuleType("cfb_top_picks_page_v10")
    fake_prior.CSS = ""
    fake_prior.MARKET_QUERY = "top_pick_market"
    fake_prior.MARKETS = ("MONEYLINE", "SPREAD", "OVER/UNDER")
    fake_prior.MARKET_LABELS = {"MONEYLINE": "Moneyline", "SPREAD": "Spread", "OVER/UNDER": "Over/Under"}
    fake_prior._normalize_market = lambda value: str(value or "MONEYLINE").upper()
    fake_prior._detail_href_for_market = lambda event_id="", market="MONEYLINE": f"?top_pick_market={market}&top_pick_detail={event_id}"
    fake_prior._loading_detail = lambda row: {"loading": True}
    fake_prior.details = types.SimpleNamespace(build_pick_detail=lambda row, slate_day: {})
    fake_prior.base = types.SimpleNamespace(
        TOP_PICK_DETAIL_QUERY="top_pick_detail",
        _query_value=lambda key: "",
    )
    fake_prior.build_market_top_picks = lambda selected, limit=10: ([], {"slate_date": "2026-10-24"})
    fake_prior._page_html = lambda picks, diag, slate_day, selected_event="", selected_detail=None, selected_market="MONEYLINE": (
        '<section data-cfb-top-picks-visual="v5">'
        '<div class="tp3-live" data-testid="cfb-top-picks-live-status">LIVE</div>'
        '<div class="tp2-board" data-testid="cfb-top-picks-card-board">CARDS</div>'
        + (
            '<details class="tp4-details" open data-testid="cfb-top-picks-details-1">'
            '<summary>SUMMARY</summary>'
            '<div class="tp4-panel" data-testid="cfb-top-picks-detail-panel-1">LEGACY RESEARCH</div>'
            '</details>'
            if selected_event and selected_detail is not None else ""
        )
        + '</section>'
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "cfb_top_picks_page_v10", fake_prior)
    sys.modules.pop(MODULE, None)
    return importlib.import_module(MODULE)


def _pick(**overrides):
    row = {
        "rank": 1,
        "event_id": "401234567",
        "away": "Ole Miss",
        "home": "Texas",
        "market": "MONEYLINE",
        "pick": "Ole Miss",
        "odds": "-210",
        "probability": 83,
        "probability_value": 0.83,
        "reliability": 0.94,
    }
    row.update(overrides)
    return row


def test_v11_is_presentation_only_successor(monkeypatch):
    page = _load(monkeypatch)
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROBABILITY is False
    assert page.MAY_MODIFY_RANKING is False
    assert page.MAY_MODIFY_SOURCE_DATA is False
    assert page.MAY_MODIFY_OTHER_SPORTS is False
    assert "PROFESSIONAL" in page.MODEL_VERSION


def test_top10_overview_is_fast_scannable_and_preserves_exact_market(monkeypatch):
    page = _load(monkeypatch)
    picks = [_pick(), _pick(rank=2, event_id="401234568", away="Rice", home="UTSA", pick="Rice", probability=72, probability_value=0.72)]
    html = page._top10_overview_html(picks, "MONEYLINE")
    assert 'data-testid="cfb-top-picks-professional-overview"' in html
    assert html.count('class="tp11-rank-row"') == 2
    assert "#1" in html and "#2" in html
    assert "83%" in html and "72%" in html
    assert "Ole Miss" in html and "Rice" in html
    assert "top_pick_market=MONEYLINE" in html
    assert "401234567" in html


def test_decision_snapshot_separates_probability_reliability_fair_and_market(monkeypatch):
    page = _load(monkeypatch)
    detail = {
        "benefits_risks": {
            "benefits": [
                {"text": "Ole Miss owns the verified recent-form edge."},
                {"text": "Ole Miss owns the verified offensive-efficiency edge."},
                {"text": "The frozen model supports the selected side."},
            ],
            "risks": [{"text": "Texas owns the verified historical-series edge."}],
        },
        "source_freshness_audit": {"material_fact_count": 53, "sources": [{"source": "ESPN"}, {"source": "NCAA"}]},
    }
    html = page._decision_snapshot_html(_pick(), detail)
    assert "Model Win Probability" in html
    assert "Model Reliability" in html
    assert "Model Fair Price" in html
    assert "Market Quote" in html
    assert "Model vs Market Edge" in html
    assert "83%" in html and "94%" in html
    assert "53 verified facts" in html
    assert "3 Quick Reasons" in html
    assert "Key Risk" in html
    assert "What Would Change This Pick?" in html


def test_page_html_adds_decision_layer_and_collapses_legacy_research(monkeypatch):
    page = _load(monkeypatch)
    pick = _pick()
    html = page._page_html(
        [pick],
        {"games_analyzed": 44},
        "2026-10-24",
        selected_event="401234567",
        selected_detail={"benefits_risks": {"benefits": [], "risks": []}},
        selected_market="MONEYLINE",
    )
    assert page.PAGE_MARKER in html
    assert 'data-testid="cfb-top-picks-professional-overview"' in html
    assert 'data-testid="cfb-top-picks-decision-snapshot-1"' in html
    assert 'data-testid="cfb-top-picks-deep-research-1"' in html
    assert "Deep verified research" in html
    assert "LEGACY RESEARCH" in html
    assert "Historical context is descriptive only" in html


def test_router_points_existing_owner_chain_to_v11():
    from pathlib import Path
    text = Path("streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9.py").read_text(encoding="utf-8")
    assert 'TOP_PICKS_PAGE = "cfb_top_picks_page_v11"' in text
