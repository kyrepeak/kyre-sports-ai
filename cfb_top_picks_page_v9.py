"""CFB Top Picks Research V2 Step 9 — final certified presentation.

Thin additive wrapper over frozen Step 8. It removes the obsolete visible audit
footer now superseded by Sources + Freshness, preventing raw audit markup from
surfacing in the customer-facing panel.
"""
from __future__ import annotations

import re

import streamlit as st

import cfb_top_picks_details_v5 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v4 as base
import cfb_top_picks_page_v6 as reasoning_owner
import cfb_top_picks_page_v8 as prior

MODEL_VERSION = "CFB TOP PICKS V9 • RESEARCH V2 STEP 9 FULL-SLATE CERTIFIED"
PAGE_MARKER = "CFB_TOP_PICKS_RESEARCH_V2_STEP9_FULL_SLATE_CERTIFIED"
FINAL_CERT_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False

CSS = prior.CSS + r"""
<style>
.tp9-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}
</style>
"""

_AUDIT_BLOCK = re.compile(
    r'\s*<div class="tp4-audit">.*?</div>',
    re.IGNORECASE | re.DOTALL,
)


def _detail_card(row: dict, detail: dict) -> str:
    html = prior._detail_card(row, detail)
    cleaned, count = _AUDIT_BLOCK.subn("", html, count=1)
    if count != 1:
        raise RuntimeError("Step 9 could not remove the obsolete frozen audit footer.")
    if '<div class="tp4-audit">' in cleaned or "&lt;div class=&quot;tp4-audit" in cleaned:
        raise RuntimeError("Step 9 raw audit markup leak detected.")

    rank = int(row.get("rank") or 0)
    reasoning = detail.get("market_reasoning") or {}
    reasoning_status = str(reasoning.get("status") or "").strip().upper()
    reasoning_token = f'data-testid="cfb-top-picks-market-reasoning-{rank}"'
    reasoning_count = cleaned.count(reasoning_token)

    if reasoning_count > 1:
        raise RuntimeError("Step 9 market reasoning preservation produced a duplicate reasoning block.")

    if reasoning_status in {"READY", "PARTIAL"} and reasoning_count == 0:
        sources_html = prior._sources_html(row, detail)
        if sources_html not in cleaned:
            raise RuntimeError(
                "Step 9 could not find the Sources + Freshness boundary required to restore market reasoning."
            )
        reasoning_html = reasoning_owner._market_reasoning_html(row, detail)
        if reasoning_token not in reasoning_html:
            raise RuntimeError("Step 9 V6 reasoning owner did not render the expected final reasoning identity.")
        cleaned = cleaned.replace(sources_html, reasoning_html + "\n" + sources_html, 1)
        reasoning_count = cleaned.count(reasoning_token)

    if reasoning_status in {"READY", "PARTIAL"} and reasoning_count != 1:
        raise RuntimeError(
            "Step 9 failed closed because READY/PARTIAL market reasoning was not preserved exactly once."
        )

    return cleaned


def _loading_detail(row: dict) -> dict:
    return dict(prior._loading_detail(row))


def _page_html(picks, diag, slate_day, selected_event="", selected_detail=None) -> str:
    html = prior._page_html(picks, diag, slate_day, selected_event, selected_detail)
    if selected_event and selected_detail is not None:
        selected = next(
            (r for r in picks if str(r.get("event_id") or "").strip() == str(selected_event).strip()),
            None,
        )
        if selected is not None:
            frozen = prior._detail_card(selected, selected_detail)
            if frozen not in html:
                raise RuntimeError("Step 9 could not find frozen Step-8 detail card.")
            html = html.replace(frozen, _detail_card(selected, selected_detail), 1)

    root = 'data-cfb-top-picks-visual="v5">'
    if root not in html:
        raise RuntimeError("Step 9 could not find frozen Top Picks visual root.")
    marker = (
        root
        + f'<div class="tp9-marker" data-testid="cfb-top-picks-research-v2-step9-marker">{PAGE_MARKER}</div>'
    )
    return html.replace(root, marker, 1)


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    with st.spinner("Building the verified College Football Top 10..."):
        picks, diag = engine.build_top_picks(limit=10)

    slate_day = str(diag.get("slate_date") or "Today")
    selected_event = base._query_value(base.TOP_PICK_DETAIL_QUERY)
    selected_row = next(
        (row for row in picks if str(row.get("event_id") or "").strip() == selected_event),
        None,
    )

    board = st.empty()
    initial = _loading_detail(selected_row) if selected_row is not None else None
    board.markdown(_page_html(picks, diag, slate_day, selected_event, initial), unsafe_allow_html=True)

    if selected_row is not None:
        with st.spinner("Loading verified matchup research..."):
            selected_detail = details.build_pick_detail(selected_row, slate_day)
        board.markdown(_page_html(picks, diag, slate_day, selected_event, selected_detail), unsafe_allow_html=True)

    if not picks:
        st.markdown(
            '<div class="tp3-empty">No verified Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Research V2 Step 9 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS", "FINAL_CERT_PROJECTION_INFLUENCE", "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION", "MODEL_VERSION", "PAGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_detail_card", "_loading_detail",
    "_page_html", "render_cfb_hub", "render_top_picks_page",
]
