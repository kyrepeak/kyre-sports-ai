"""CFB Top Picks V10 — interactive market tabs.

Additive successor above frozen V9. Moneyline, Spread and Over/Under become real
query-driven tap controls. Each tab builds its own Top-10 ranking from the same
verified candidate factories/data sources already owned by the frozen engine.
No projection, probability, sportsbook weighting or matchup-research math is
changed. Selected-market state is preserved while opening/closing details.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import re
from typing import Any, Mapping
from urllib.parse import urlencode

import streamlit as st

import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v4 as base
import cfb_top_picks_page_v9 as prior

MODEL_VERSION = "CFB TOP PICKS V10 • INTERACTIVE MARKET TABS R1"
PAGE_MARKER = "CFB_TOP_PICKS_V10_MARKET_TABS_R1_ACTIVE"
MARKET_QUERY = "top_pick_market"
MARKETS = ("MONEYLINE", "SPREAD", "OVER/UNDER")
MARKET_LABELS = {
    "MONEYLINE": "Moneyline",
    "SPREAD": "Spread",
    "OVER/UNDER": "Over/Under",
}
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_OTHER_SPORTS = False

CSS = prior.CSS + r"""
<style id="cfb-top-picks-v10-market-tabs-css">
[data-testid="cfb-top-picks-market-tabs"] a.tp1-chip{
  display:flex;align-items:center;justify-content:center;
  color:inherit;text-decoration:none;cursor:pointer;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation;
}
[data-testid="cfb-top-picks-market-tabs"] a.tp1-chip:focus-visible{
  outline:2px solid rgba(73,190,255,.82);outline-offset:-2px;
}
.tp10-market-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}
</style>
"""

_STATIC_TABS = re.compile(
    r'<div class="tp1-segmented" data-testid="cfb-top-picks-market-tabs">\s*'
    r'<div class="tp1-chip active">Moneyline</div>\s*'
    r'<div class="tp1-chip">Spread</div>\s*'
    r'<div class="tp1-chip">Over/Under</div>\s*'
    r'</div>',
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_market(value: Any) -> str:
    token = _clean(value).upper().replace("_", "/").replace(" ", "")
    aliases = {
        "MONEYLINE": "MONEYLINE",
        "ML": "MONEYLINE",
        "SPREAD": "SPREAD",
        "ATS": "SPREAD",
        "OVER/UNDER": "OVER/UNDER",
        "OVERUNDER": "OVER/UNDER",
        "TOTAL": "OVER/UNDER",
        "TOTALS": "OVER/UNDER",
        "OU": "OVER/UNDER",
        "O/U": "OVER/UNDER",
    }
    return aliases.get(token, "MONEYLINE")


def _market_href(market: Any) -> str:
    params = {
        base.ROUTE_QUERY_SPORT: base.CFB_SPORT_LABEL,
        base.ROUTE_QUERY_MARKET: base.TOP_PICKS_MARKET,
        MARKET_QUERY: _normalize_market(market),
    }
    return "?" + urlencode(params)


def _detail_href_for_market(event_id: str = "", market: Any = "MONEYLINE") -> str:
    params = {
        base.ROUTE_QUERY_SPORT: base.CFB_SPORT_LABEL,
        base.ROUTE_QUERY_MARKET: base.TOP_PICKS_MARKET,
        MARKET_QUERY: _normalize_market(market),
    }
    if _clean(event_id):
        params[base.TOP_PICK_DETAIL_QUERY] = _clean(event_id)
    return "?" + urlencode(params)


def _market_tabs_html(selected_market: Any) -> str:
    selected = _normalize_market(selected_market)
    tabs = []
    for market in MARKETS:
        active = market == selected
        classes = "tp1-chip active" if active else "tp1-chip"
        tabs.append(
            f'<a class="{classes}" data-market="{escape(market)}" '
            f'role="tab" aria-selected="{str(active).lower()}" '
            f'href="{escape(_market_href(market), quote=True)}" target="_self">'
            f'{escape(MARKET_LABELS[market])}</a>'
        )
    return (
        '<div class="tp1-segmented" data-testid="cfb-top-picks-market-tabs" role="tablist">'
        + "".join(tabs)
        + "</div>"
    )


def _rank_market(
    candidates: list[Mapping[str, Any]],
    market: Any,
    limit: int = 10,
) -> list[dict[str, Any]]:
    selected = _normalize_market(market)
    filtered = [
        dict(row)
        for row in candidates
        if _normalize_market(row.get("market")) == selected and _clean(row.get("event_id"))
    ]
    filtered.sort(
        key=lambda row: (
            -engine._f(row.get("probability_value")),
            -engine._f(row.get("reliability")),
            _clean(row.get("event_id")),
        )
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in filtered:
        event_id = _clean(row.get("event_id"))
        if event_id in seen:
            continue
        item = dict(row)
        item["rank"] = len(out) + 1
        out.append(item)
        seen.add(event_id)
        if len(out) >= max(0, int(limit)):
            break
    return out


def _candidate_for_market(
    selected_market: str,
    row: Mapping[str, Any],
    market_context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if selected_market == "MONEYLINE":
        return engine._moneyline_candidate(row, market_context)
    if selected_market == "SPREAD":
        return engine._spread_candidate(row, market_context)
    return engine._ou_candidate(row, market_context)


def build_market_top_picks(
    selected_market: Any,
    start_day: str | None = None,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected = _normalize_market(selected_market)
    requested = start_day or datetime.now(engine.PHOENIX).date().isoformat()
    slate_day, games, slate_diag = engine.resolve_slate(
        requested,
        minimum_games=max(1, int(limit)),
    )
    if not games:
        return [], {
            "status": "EMPTY",
            "version": MODEL_VERSION,
            "selected_market": selected,
            "requested_date": requested,
            "slate_date": slate_day,
            "games_analyzed": 0,
            "candidate_count": 0,
            "pick_count": 0,
            "slate": slate_diag,
            "sportsbook_projection_weight": 0.0,
            "sportsbook_may_modify_projection": False,
        }

    market_map, spread_diag = engine.market_context.load_market_context(slate_day)
    odds_payload, total_diag = engine.total_market.load_odds_for_date(slate_day, "FanDuel")
    games_with_totals, attach_diag = engine.total_market.attach_market_lines(games, odds_payload)
    analyzed, money_diag = engine.moneyline_slate.scan_slate(games_with_totals, slate_day)

    candidates: list[dict[str, Any]] = []
    for row in analyzed:
        game = dict(row.get("game") or {})
        event_id = engine._identity(game)
        candidate = _candidate_for_market(selected, row, market_map.get(event_id) or {})
        if candidate is not None:
            candidates.append(candidate)

    picks = _rank_market(candidates, selected, limit=limit)
    games_by_event = {
        engine._identity(game): dict(game)
        for game in games_with_totals
        if engine._identity(game)
    }
    picks = engine.team_identity.enrich_ranked_picks(picks, games_by_event)

    return picks, {
        "status": "GREEN" if picks else "NO_QUALIFIED_PICKS",
        "version": MODEL_VERSION,
        "selected_market": selected,
        "requested_date": requested,
        "slate_date": slate_day,
        "auto_advanced_days": int(slate_diag.get("auto_advanced_days") or 0),
        "games": len(games),
        "games_analyzed": int(money_diag.get("games_analyzed") or 0),
        "candidate_count": len(candidates),
        "candidate_counts": {selected: len(candidates)},
        "pick_count": len(picks),
        "selected_counts": {selected: len(picks)},
        "market_context": spread_diag,
        "total_market": total_diag,
        "total_attach": attach_diag,
        "moneyline_scan": money_diag,
        "sportsbook_projection_weight": 0.0,
        "sportsbook_may_modify_projection": False,
        "ranking_method": f"{selected} probability/reliability; one pick per event",
    }


def _page_html(
    picks: list[dict],
    diag: dict,
    slate_day: str,
    selected_event: str = "",
    selected_detail: dict | None = None,
    *,
    selected_market: Any = "MONEYLINE",
) -> str:
    selected = _normalize_market(selected_market)
    original_detail_href = base._detail_href
    base._detail_href = lambda event_id="": _detail_href_for_market(event_id, selected)
    try:
        html = prior._page_html(picks, diag, slate_day, selected_event, selected_detail)
    finally:
        base._detail_href = original_detail_href

    html, count = _STATIC_TABS.subn(_market_tabs_html(selected), html, count=1)
    if count != 1:
        raise RuntimeError("Top Picks V10 could not find the frozen static market-tab block.")

    root = 'data-cfb-top-picks-visual="v5">'
    if root in html:
        marker = (
            root
            + f'<div class="tp10-market-marker" data-testid="cfb-top-picks-v10-market-tabs" '
            f'data-selected-market="{escape(selected)}">{PAGE_MARKER}</div>'
        )
        html = html.replace(root, marker, 1)
    return html


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    selected_market = _normalize_market(base._query_value(MARKET_QUERY))
    label = MARKET_LABELS[selected_market]
    with st.spinner(f"Building the verified College Football {label} Top 10..."):
        picks, diag = build_market_top_picks(selected_market, limit=10)

    slate_day = str(diag.get("slate_date") or "Today")
    selected_event = base._query_value(base.TOP_PICK_DETAIL_QUERY)
    selected_row = next(
        (row for row in picks if _clean(row.get("event_id")) == selected_event),
        None,
    )

    board = st.empty()
    initial = prior._loading_detail(selected_row) if selected_row is not None else None
    board.html(
        _page_html(
            picks,
            diag,
            slate_day,
            selected_event,
            initial,
            selected_market=selected_market,
        )
    )

    if selected_row is not None:
        with st.spinner("Loading verified matchup research..."):
            selected_detail = prior.details.build_pick_detail(selected_row, slate_day)
        board.html(
            _page_html(
                picks,
                diag,
                slate_day,
                selected_event,
                selected_detail,
                selected_market=selected_market,
            )
        )

    if not picks:
        st.markdown(
            f'<div class="tp3-empty">No verified {escape(label)} Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market) != "Top Picks":
        raise RuntimeError("CFB Top Picks V10 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS",
    "MARKETS",
    "MARKET_LABELS",
    "MARKET_QUERY",
    "MODEL_VERSION",
    "PAGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_detail_href_for_market",
    "_market_href",
    "_market_tabs_html",
    "_normalize_market",
    "_page_html",
    "_rank_market",
    "build_market_top_picks",
    "render_cfb_hub",
    "render_top_picks_page",
]
