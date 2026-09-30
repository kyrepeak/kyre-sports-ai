"""CFB Top Picks Research V2 Step 6 — market-aware reasoning presentation.

Thin additive layer over frozen V5. Existing cards, research panels, history,
probability, ranking, and visual contracts remain owned by frozen predecessors.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import cfb_top_picks_details_v2 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v4 as base
import cfb_top_picks_page_v5 as prior

MODEL_VERSION = "CFB TOP PICKS V6 • RESEARCH V2 STEP 6 MARKET REASONING"
PAGE_MARKER = "CFB_TOP_PICKS_RESEARCH_V2_STEP6_MARKET_REASONING_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MARKET_REASONING_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False

CSS = prior.CSS + r"""
<style>
.tp6-reasoning{margin-top:10px;border:1px solid rgba(35,190,255,.25);border-radius:11px;background:linear-gradient(145deg,#071724,#09111c);padding:11px}
.tp6-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}
.tp6-head h4{margin:0;color:#70d8ff;font-size:.74rem;letter-spacing:.04em;text-transform:uppercase}
.tp6-head span{color:#7890a3;font-size:.61rem}
.tp6-summary{margin:0 0 8px;color:#d2e2ee;font-size:.73rem;line-height:1.45}
.tp6-signals{display:flex;flex-direction:column;gap:6px}
.tp6-signal{padding:7px 8px;border-left:3px solid #42cfff;border-radius:7px;background:rgba(19,79,108,.18)}
.tp6-signal b{display:block;color:#8edfff;font-size:.59rem;letter-spacing:.03em;text-transform:uppercase;margin-bottom:3px}
.tp6-signal p{margin:0;color:#c7d5e1;font-size:.70rem;line-height:1.38}
.tp6-status{display:inline-block;margin-left:6px;color:#9fb4c5;font-size:.53rem}
.tp6-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}
</style>
"""


def _label(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _market_reasoning_html(row: dict, detail: dict) -> str:
    rank = int(row.get("rank") or 0)
    reasoning = detail.get("market_reasoning") or {}
    if detail.get("loading") is True:
        return (
            '<div class="tp6-reasoning" data-testid="cfb-top-picks-market-reasoning-loading">'
            '<div class="tp6-head"><h4>Market-Aware Football Reasoning</h4>'
            '<span>Loading verified selected-game evidence…</span></div></div>'
        )
    if not reasoning or reasoning.get("status") == "IDENTITY_UNAVAILABLE":
        return (
            '<div class="tp6-reasoning" data-testid="cfb-top-picks-market-reasoning-unavailable">'
            '<div class="tp6-head"><h4>Market-Aware Football Reasoning</h4>'
            '<span>Verified reasoning evidence unavailable</span></div></div>'
        )

    signals = reasoning.get("signals") or {}
    required = list(reasoning.get("required_signals") or [])
    rows = []
    for key in required:
        item = signals.get(key) or {}
        text = escape(str(item.get("text") or "Verified evidence unavailable."))
        status = escape(str(item.get("status") or "UNAVAILABLE"))
        rows.append(
            f'<div class="tp6-signal" data-reasoning-key="{escape(str(key))}">'
            f'<b>{escape(_label(str(key)))} <span class="tp6-status">{status}</span></b>'
            f'<p>{text}</p></div>'
        )
    market = escape(str(reasoning.get("market") or row.get("market") or ""))
    status = escape(str(reasoning.get("status") or "PARTIAL"))
    summary = escape(str(reasoning.get("summary") or "No additional verified reasoning available."))
    return f"""
    <div class="tp6-reasoning" data-testid="cfb-top-picks-market-reasoning-{rank}" data-market="{market}" data-reasoning-status="{status}">
      <div class="tp6-head">
        <h4>Market-Aware Football Reasoning</h4>
        <span>{market} • read-only research • projection weight 0.0%</span>
      </div>
      <p class="tp6-summary">{summary}</p>
      <div class="tp6-signals">{"".join(rows)}</div>
    </div>
    """


def _detail_card(row: dict, detail: dict) -> str:
    html = base._detail_card(row, detail)
    needle = '        <div class="tp4-audit">'
    if needle not in html:
        raise RuntimeError("Step 6 could not find the frozen detail audit insertion point.")
    return html.replace(needle, _market_reasoning_html(row, detail) + "\n" + needle, 1)


def _loading_detail(row: dict) -> dict:
    detail = dict(base._loading_detail(row))
    detail["market_reasoning"] = {
        "market": str(row.get("market") or "").upper(),
        "status": "LOADING",
        "required_signals": [],
        "signals": {},
        "summary": "Loading verified market-specific research.",
        "projection_weight": 0.0,
    }
    return detail


def _page_html(
    picks: list[dict],
    diag: dict,
    slate_day: str,
    selected_event: str = "",
    selected_detail: dict | None = None,
) -> str:
    html = prior._page_html(picks, diag, slate_day, selected_event, selected_detail)
    if selected_event and selected_detail is not None:
        selected = next(
            (row for row in picks if str(row.get("event_id") or "").strip() == str(selected_event).strip()),
            None,
        )
        if selected is not None:
            frozen_card = base._detail_card(selected, selected_detail)
            if frozen_card not in html:
                raise RuntimeError("Step 6 could not find the frozen expanded detail card.")
            html = html.replace(frozen_card, _detail_card(selected, selected_detail), 1)

    root_token = 'data-cfb-top-picks-visual="v5">'
    marker = (
        root_token
        + f'<div class="tp6-marker" data-testid="cfb-top-picks-research-v2-step6-marker">{PAGE_MARKER}</div>'
    )
    if root_token not in html:
        raise RuntimeError("Step 6 could not find the frozen V5 visual root.")
    return html.replace(root_token, marker, 1)


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
    initial_detail = _loading_detail(selected_row) if selected_row is not None else None
    board.markdown(_page_html(picks, diag, slate_day, selected_event, initial_detail), unsafe_allow_html=True)

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
        raise RuntimeError("CFB Top Picks Research V2 Step 6 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS", "MARKET_REASONING_PROJECTION_INFLUENCE", "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION", "MODEL_VERSION", "PAGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_detail_card", "_loading_detail",
    "_market_reasoning_html", "_page_html", "render_cfb_hub", "render_top_picks_page",
]
