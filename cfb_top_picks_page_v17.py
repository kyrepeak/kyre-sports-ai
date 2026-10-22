"""CFB Top Picks V17 — Page 2 route-locked successor over frozen V16."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode

import streamlit as st

import cfb_top_picks_page_v16 as prior

MODEL_VERSION = "CFB TOP PICKS V17 • PAGE2 ROUTE LOCK V1"
PAGE_MARKER = "CFB_TOP_PICKS_PAGE2_ROUTE_LOCK_V1_ACTIVE"
PAGE2_ENDPOINT = prior.PAGE2_ENDPOINT
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT_LABEL = "College Football"
TOP_PICKS_MARKET = "Top Picks"


def _c(value: Any) -> str:
    return str(value or "").strip()


def _page1_handoff(row: Mapping[str, Any], kind: str) -> str:
    params = {
        ROUTE_QUERY_SPORT: CFB_SPORT_LABEL,
        ROUTE_QUERY_MARKET: TOP_PICKS_MARKET,
        "top_pick_id": _c(row.get("candidate_id")),
        "top_pick_kind": kind,
        "top_pick_date": _c(row.get("selected_date") or _c(row.get("kickoff_iso"))[:10]),
    }
    return "?" + urlencode({key: value for key, value in params.items() if value})


def _back_href(snapshot: Mapping[str, Any]) -> str:
    params = {
        ROUTE_QUERY_SPORT: CFB_SPORT_LABEL,
        ROUTE_QUERY_MARKET: TOP_PICKS_MARKET,
        "top_pick_date": _c(snapshot.get("selected_date")),
    }
    return "?" + urlencode({key: value for key, value in params.items() if value})


def render_page2_html(payload: Mapping[str, Any]) -> str:
    snapshot = payload.get("selection_snapshot") or {}
    if not snapshot:
        return (
            '<div data-testid="cfb-top-picks-page2-v1-root">'
            '<div class="p2-unavail">The selected Page 1 candidate could not be verified. '
            'Return to Top Picks and tap a current card.</div></div>'
        )
    return prior._safe(
        f'''<div data-testid="cfb-top-picks-page2-v1-root"><a class="p2-back" href="{escape(_back_href(snapshot))}">← Back to Top Picks</a><div class="p2-shell">{prior._hero(snapshot)}<div class="p2-grid">{prior._verdict(payload)}{prior._lab(payload)}{prior._projection(payload)}{prior._drivers(payload)}{prior._market(payload)}{prior._notes(payload,"risks","RISKS / WHAT COULD GO WRONG")}{prior._notes(payload,"flip_conditions","WHAT WOULD FLIP THE PICK")}{prior._sources(payload)}</div><div class="p2-foot">PAGE 2 ANALYTICS LAB • MODEL OUTPUTS OWNED BY KYRE SPORTS API • SPORTSBOOKS PROVIDE MARKET CONTEXT ONLY</div></div></div>'''
    )


def render_cfb_hub(market_name: str = "Top Picks") -> None:
    candidate = prior._qp("top_pick_id")
    if not candidate:
        original = prior.page1._handoff
        prior.page1._handoff = _page1_handoff
        try:
            return prior.page1.render_cfb_hub(market_name)
        finally:
            prior.page1._handoff = original

    st.markdown(prior.CSS, unsafe_allow_html=True)
    try:
        payload = prior._load_page2(
            candidate,
            prior._qp("top_pick_kind"),
            prior._qp("top_pick_date"),
        )
    except Exception as exc:
        st.error(f"Top Picks Page 2 could not load: {type(exc).__name__}")
        return
    st.markdown(render_page2_html(payload), unsafe_allow_html=True)


__all__ = [
    "MODEL_VERSION",
    "PAGE_MARKER",
    "PAGE2_ENDPOINT",
    "render_cfb_hub",
    "render_page2_html",
]
