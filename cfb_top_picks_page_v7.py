"""CFB Top Picks Research V2 Step 7 — verified Benefits + Risks UI.

Thin additive layer over frozen Step 6. Existing ranking, research, history,
market reasoning, probability, and routing contracts remain frozen.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import cfb_top_picks_details_v3 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v4 as base
import cfb_top_picks_page_v6 as prior

MODEL_VERSION = "CFB TOP PICKS V7 • RESEARCH V2 STEP 7 BENEFITS RISKS"
PAGE_MARKER = "CFB_TOP_PICKS_RESEARCH_V2_STEP7_BENEFITS_RISKS_ACTIVE"
BENEFITS_RISKS_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False

CSS = prior.CSS + r"""
<style>
.tp7-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:0}
.tp7-box{border:1px solid rgba(76,201,240,.22);border-radius:10px;background:rgba(5,18,29,.66);padding:10px}
.tp7-box h4{margin:0 0 8px;color:#8edfff;font-size:.72rem;letter-spacing:.04em;text-transform:uppercase}
.tp7-item{padding:7px 8px;border-radius:7px;background:rgba(16,50,70,.24);margin-top:6px}
.tp7-item:first-of-type{margin-top:0}
.tp7-item p{margin:0;color:#d3e1ec;font-size:.70rem;line-height:1.42}
.tp7-meta{display:block;margin-top:4px;color:#7691a5;font-size:.55rem;line-height:1.25}
.tp7-empty{color:#9bb0c0;font-size:.68rem;line-height:1.4}
.tp7-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}
@media(max-width:640px){.tp7-grid{grid-template-columns:1fr}}
</style>
"""


def _evidence_items(items: list[dict], empty: str) -> str:
    if not items:
        return f'<div class="tp7-empty">{escape(empty)}</div>'
    rendered = []
    for item in items:
        text = escape(str(item.get("text") or "Verified evidence unavailable."))
        sources = [str(s) for s in (item.get("sources") or []) if str(s or "").strip()]
        source_text = escape(" • ".join(sources[:3]) or "Verified source metadata unavailable")
        observed = escape(str(item.get("observed_at") or ""))
        status = escape(str(item.get("status") or ""))
        rendered.append(
            '<div class="tp7-item">'
            f'<p>{text}</p>'
            f'<span class="tp7-meta">{status} • {source_text}'
            + (f' • observed {observed}' if observed else '')
            + '</span></div>'
        )
    return "".join(rendered)


def _benefits_risks_html(row: dict, detail: dict) -> str:
    result = detail.get("benefits_risks") or {}
    if detail.get("loading") is True or result.get("status") == "LOADING":
        return (
            '<div class="tp7-grid" data-testid="cfb-top-picks-benefits-risks-loading">'
            '<div class="tp7-box"><h4>Benefits</h4><div class="tp7-empty">Loading verified evidence…</div></div>'
            '<div class="tp7-box"><h4>Risks</h4><div class="tp7-empty">Loading verified counter-evidence…</div></div>'
            '</div>'
        )
    return (
        f'<div class="tp7-grid" data-testid="cfb-top-picks-benefits-risks-{int(row.get("rank") or 0)}" '
        f'data-benefits-risks-status="{escape(str(result.get("status") or "PARTIAL"))}">'
        '<div class="tp7-box"><h4>Benefits</h4>'
        + _evidence_items(list(result.get("benefits") or []), "No verified benefit is being claimed.")
        + '</div><div class="tp7-box"><h4>Risks</h4>'
        + _evidence_items(list(result.get("risks") or []), "No verified risk factor is being claimed.")
        + '</div></div>'
    )


def _detail_card(row: dict, detail: dict) -> str:
    html = prior._detail_card(row, detail)
    legacy_benefit = escape(str(detail.get("benefit") or "No verified historical benefit is claimed."))
    needle = (
        '          <div class="tp4-box">\n'
        '            <h4>Benefits</h4>\n'
        f'            <p>{legacy_benefit}</p>\n'
        '          </div>'
    )
    if needle not in html:
        raise RuntimeError("Step 7 could not find the frozen legacy Benefits box.")
    return html.replace(needle, _benefits_risks_html(row, detail), 1)


def _loading_detail(row: dict) -> dict:
    detail = dict(base._loading_detail(row))
    detail["market_reasoning"] = {
        "market": str(row.get("market") or "").upper(), "status": "LOADING",
        "required_signals": [], "signals": {}, "summary": "Loading verified market-specific research.",
        "projection_weight": 0.0,
    }
    detail["benefits_risks"] = {
        "market": str(row.get("market") or "").upper(), "status": "LOADING",
        "benefits": [], "risks": [], "projection_weight": 0.0,
    }
    return detail


def _page_html(picks, diag, slate_day, selected_event="", selected_detail=None) -> str:
    html = prior._page_html(picks, diag, slate_day, selected_event, selected_detail)
    if selected_event and selected_detail is not None:
        selected = next(
            (row for row in picks if str(row.get("event_id") or "").strip() == str(selected_event).strip()),
            None,
        )
        if selected is not None:
            frozen = prior._detail_card(selected, selected_detail)
            if frozen not in html:
                raise RuntimeError("Step 7 could not find the frozen Step-6 expanded detail card.")
            html = html.replace(frozen, _detail_card(selected, selected_detail), 1)
    root = 'data-cfb-top-picks-visual="v5">'
    if root not in html:
        raise RuntimeError("Step 7 could not find the frozen Top Picks visual root.")
    marker = root + f'<div class="tp7-marker" data-testid="cfb-top-picks-research-v2-step7-marker">{PAGE_MARKER}</div>'
    return html.replace(root, marker, 1)


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
        st.markdown(
            '<div class="tp3-empty">No verified Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Research V2 Step 7 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "BENEFITS_RISKS_PROJECTION_INFLUENCE", "CSS", "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION", "MODEL_VERSION", "PAGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_benefits_risks_html", "_detail_card",
    "_loading_detail", "_page_html", "render_cfb_hub", "render_top_picks_page",
]
