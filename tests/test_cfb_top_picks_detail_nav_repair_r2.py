from __future__ import annotations

import importlib
import sys
import types

MODULE = "cfb_top_picks_page_v11"
EVENT_ID = "401856732"


class _Spinner:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Board:
    def __init__(self):
        self.html_calls: list[str] = []

    def html(self, value: str):
        self.html_calls.append(value)


def _row() -> dict:
    return {
        "rank": 1,
        "event_id": EVENT_ID,
        "away": "Ole Miss",
        "home": "Texas",
        "pick": "Ole Miss",
        "odds": "-473",
        "probability_value": 0.83,
        "probability": 83,
        "reliability": 0.94,
        "time": "Sat, 4:30 PM",
        "network": "ABC",
        "source": "Kyre Moneyline model • fair price",
    }


def _load(monkeypatch, *, selected_event: str = EVENT_ID):
    board = _Board()
    detail_calls: list[tuple[str, str]] = []

    fake_st = types.SimpleNamespace(
        query_params={},
        markdown=lambda *a, **k: None,
        empty=lambda: board,
        spinner=lambda *a, **k: _Spinner(),
    )

    fake_details = types.ModuleType("cfb_top_picks_details_v5")

    def build_pick_detail(row, slate_day):
        detail_calls.append((str(row.get("event_id")), str(slate_day)))
        return {
            "benefits_risks": {
                "benefits": [{"text": "Ole Miss owns the verified model edge."}],
                "risks": [{"text": "Road variance remains a verified risk."}],
            },
            "source_freshness_audit": {"material_fact_count": 2, "sources": ["schedule", "model"]},
        }

    fake_details.build_pick_detail = build_pick_detail

    fake_prior = types.ModuleType("cfb_top_picks_page_v10")
    fake_prior.CSS = ""
    fake_prior.MARKET_QUERY = "top_pick_market"
    fake_prior.MARKETS = ("MONEYLINE", "SPREAD", "OVER/UNDER")
    fake_prior.MARKET_LABELS = {"MONEYLINE": "Moneyline", "SPREAD": "Spread", "OVER/UNDER": "Over/Under"}
    fake_prior._normalize_market = lambda value: str(value or "MONEYLINE").upper()
    fake_prior._detail_href_for_market = lambda event_id="", market="MONEYLINE": (
        "?ks_sport=College+Football&ks_cfb_market=Top+Picks"
        f"&top_pick_market={market}&top_pick_detail={event_id}"
    )
    fake_prior._loading_detail = lambda row: {"loading": True}

    def query_value(key):
        if key == "top_pick_market":
            return "MONEYLINE"
        if key == "top_pick_detail":
            return selected_event
        return ""

    fake_prior.base = types.SimpleNamespace(
        TOP_PICK_DETAIL_QUERY="top_pick_detail",
        _query_value=query_value,
    )
    fake_prior.build_market_top_picks = lambda selected, limit=10: ([_row()], {"slate_date": "2026-10-24"})

    def prior_page_html(picks, diag, slate_day, selected_event="", selected_detail=None, selected_market="MONEYLINE"):
        legacy_card = (
            '<a class="tp2-card" href="?ks_sport=College+Football&amp;ks_cfb_market=Top+Picks'
            f'&amp;top_pick_market={selected_market}&amp;top_pick_detail={EVENT_ID}">GAME</a>'
        )
        detail = ""
        if selected_event and selected_detail is not None:
            detail = (
                '<details class="tp4-details" open data-testid="cfb-top-picks-details-1">'
                '<summary>SUMMARY</summary>'
                '<div class="tp4-panel" data-testid="cfb-top-picks-detail-panel-1">LEGACY RESEARCH</div>'
                '</details>'
            )
        return (
            '<section data-cfb-top-picks-visual="v5">'
            '<div class="tp3-live" data-testid="cfb-top-picks-live-status">LIVE</div>'
            '<div class="tp2-board" data-testid="cfb-top-picks-card-board">'
            + legacy_card
            + '</div>'
            + detail
            + '</section>'
        )

    fake_prior._page_html = prior_page_html

    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "cfb_top_picks_page_v10", fake_prior)
    monkeypatch.setitem(sys.modules, "cfb_top_picks_details_v5", fake_details)
    sys.modules.pop(MODULE, None)
    return importlib.import_module(MODULE), board, detail_calls


def test_selected_top_pick_loads_real_detail_provider_without_v10_details_attribute(monkeypatch):
    page, board, detail_calls = _load(monkeypatch)

    page.render_top_picks_page()

    assert detail_calls == [(EVENT_ID, "2026-10-24")]
    assert len(board.html_calls) == 2
    assert "cfb-top-picks-decision-snapshot-1" in board.html_calls[-1]


def test_top_pick_links_keep_runtime_v5_canonical_route_and_exact_event(monkeypatch):
    page, _, _ = _load(monkeypatch, selected_event="")
    picks = [_row()]
    html = page._page_html(
        picks,
        {"slate_date": "2026-10-24"},
        "2026-10-24",
        selected_market="MONEYLINE",
    )

    assert "sport=cfb" in html
    assert "market=top-picks" in html
    assert f"top_pick_detail={EVENT_ID}" in html
    assert "ks_sport=" not in html
    assert "ks_cfb_market=" not in html
