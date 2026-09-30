"""CFB Top Picks Research V2 Step 8 — Sources + Freshness UI."""
from __future__ import annotations

from html import escape

import streamlit as st

import cfb_top_picks_details_v4 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v4 as base
import cfb_top_picks_page_v7 as prior

MODEL_VERSION = "CFB TOP PICKS V8 • RESEARCH V2 STEP 8 SOURCE ROUTER"
PAGE_MARKER = "CFB_TOP_PICKS_RESEARCH_V2_STEP8_SOURCE_ROUTER_ACTIVE"
SOURCE_ROUTER_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False

CSS = prior.CSS + r"""
<style>
.tp8-sources{margin-top:10px;border:1px solid rgba(80,200,255,.22);border-radius:11px;background:rgba(4,16,26,.72);padding:10px}
.tp8-head{display:flex;justify-content:space-between;gap:10px;align-items:center}
.tp8-head h4{margin:0;color:#8edfff;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.tp8-head span{color:#7892a6;font-size:.56rem}
.tp8-stats{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.tp8-pill{border:1px solid rgba(99,207,255,.22);border-radius:999px;padding:4px 7px;color:#b7d6e8;font-size:.57rem}
.tp8-source{padding:6px 0;border-top:1px solid rgba(255,255,255,.06)}
.tp8-source b{display:block;color:#d5e8f4;font-size:.66rem}
.tp8-source span{display:block;color:#7e99aa;font-size:.55rem;margin-top:2px}
.tp8-ok{color:#7ce3ad}
.tp8-bad{color:#ff9d9d}
.tp8-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}
</style>
"""


def _sources_html(row: dict, detail: dict) -> str:
    audit = detail.get("source_freshness_audit") or {}
    status = str(audit.get("status") or "PENDING")
    sources = list(audit.get("sources") or [])
    rows = []
    for item in sources[:12]:
        source = escape(str(item.get("source") or "Unknown source"))
        count = int(item.get("material_fact_count") or 0)
        observed = escape(str(item.get("observed_at") or ""))
        rows.append(
            f'<div class="tp8-source"><b>{source}</b>'
            f'<span>{count} material fact{"s" if count != 1 else ""}'
            + (f' • latest observed {observed}' if observed else '')
            + '</span></div>'
        )
    if not rows:
        rows.append('<div class="tp8-source"><b>No material source rows yet.</b></div>')
    cls = "tp8-ok" if status == "READY" else "tp8-bad"
    return f"""
    <div class="tp8-sources" data-testid="cfb-top-picks-sources-freshness-{int(row.get("rank") or 0)}" data-source-router-status="{escape(status)}">
      <div class="tp8-head"><h4>Sources + Freshness</h4><span class="{cls}">{escape(status)} • DATA_FIELD routing</span></div>
      <div class="tp8-stats">
        <span class="tp8-pill">{int(audit.get("material_fact_count") or 0)} material facts</span>
        <span class="tp8-pill">{int(audit.get("fallback_used_count") or 0)} verified fallbacks used</span>
        <span class="tp8-pill">{int(audit.get("unavailable_field_count") or 0)} unavailable fields explained</span>
        <span class="tp8-pill">{int(audit.get("violation_count") or 0)} provenance violations</span>
      </div>
      {"".join(rows)}
    </div>
    """


def _detail_card(row: dict, detail: dict) -> str:
    html = prior._detail_card(row, detail)
    needle = '        <div class="tp4-audit">'
    if needle not in html:
        raise RuntimeError("Step 8 could not find frozen audit insertion point.")
    return html.replace(needle, _sources_html(row, detail) + "\n" + needle, 1)


def _loading_detail(row: dict) -> dict:
    detail = dict(prior._loading_detail(row))
    detail["source_freshness_audit"] = {
        "status": "LOADING", "sources": [], "material_fact_count": 0,
        "fallback_used_count": 0, "unavailable_field_count": 0,
        "violation_count": 0, "projection_weight": 0.0,
    }
    return detail


def _page_html(picks, diag, slate_day, selected_event="", selected_detail=None) -> str:
    html = prior._page_html(picks, diag, slate_day, selected_event, selected_detail)
    if selected_event and selected_detail is not None:
        selected = next((r for r in picks if str(r.get("event_id") or "").strip() == str(selected_event).strip()), None)
        if selected is not None:
            frozen = prior._detail_card(selected, selected_detail)
            if frozen not in html:
                raise RuntimeError("Step 8 could not find frozen Step-7 detail card.")
            html = html.replace(frozen, _detail_card(selected, selected_detail), 1)
    root = 'data-cfb-top-picks-visual="v5">'
    if root not in html:
        raise RuntimeError("Step 8 could not find frozen Top Picks visual root.")
    return html.replace(root, root + f'<div class="tp8-marker" data-testid="cfb-top-picks-research-v2-step8-marker">{PAGE_MARKER}</div>', 1)


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    with st.spinner("Building the verified College Football Top 10..."):
        picks, diag = engine.build_top_picks(limit=10)
    slate_day = str(diag.get("slate_date") or "Today")
    selected_event = base._query_value(base.TOP_PICK_DETAIL_QUERY)
    selected_row = next((r for r in picks if str(r.get("event_id") or "").strip() == selected_event), None)
    board = st.empty()
    initial = _loading_detail(selected_row) if selected_row is not None else None
    board.markdown(_page_html(picks, diag, slate_day, selected_event, initial), unsafe_allow_html=True)
    if selected_row is not None:
        with st.spinner("Loading verified matchup research..."):
            selected_detail = details.build_pick_detail(selected_row, slate_day)
        board.markdown(_page_html(picks, diag, slate_day, selected_event, selected_detail), unsafe_allow_html=True)
    if not picks:
        st.markdown('<div class="tp3-empty">No verified Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>', unsafe_allow_html=True)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Research V2 Step 8 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS", "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION",
    "MODEL_VERSION", "PAGE_MARKER", "SOURCE_ROUTER_PROJECTION_INFLUENCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_detail_card", "_loading_detail",
    "_page_html", "_sources_html", "render_cfb_hub", "render_top_picks_page",
]
