"""CFB Top Picks Step 5 — final visual parity and responsive polish.

Thin presentation-only layer over frozen Step 4. No ranking, projection,
market, history, or selection math is changed here.
"""
from __future__ import annotations

import streamlit as st

import cfb_top_picks_page_v4 as prior

MODEL_VERSION = "CFB TOP PICKS V5 • STEP 5 FINAL VISUAL PARITY"
PAGE_MARKER = "CFB_TOP_PICKS_STEP5_FINAL_VISUAL_ACTIVE"
LAYOUT_PREVIEW = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
HISTORY_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_RANKING = False
MAY_MODIFY_HISTORY = False

CSS = prior.CSS + r"""
<style>
[data-testid="cfb-top-picks-step5-root"]{
  width:100%;
  max-width:1500px;
  margin:0 auto;
  padding:4px 2px 20px;
  color:#f7fbff;
  overflow-x:clip;
  box-sizing:border-box;
}
[data-testid="cfb-top-picks-step5-root"] *{box-sizing:border-box}
[data-testid="cfb-top-picks-step5-root"] .tp1-hero{
  padding:10px 2px 14px;
}
[data-testid="cfb-top-picks-step5-root"] .tp3-live{
  min-height:38px;
  margin-bottom:9px;
  border-color:rgba(109,198,255,.18);
  background:linear-gradient(180deg,rgba(7,18,29,.92),rgba(5,14,23,.88));
}
[data-testid="cfb-top-picks-step5-root"] .tp2-board{gap:7px}
[data-testid="cfb-top-picks-step5-root"] .tp2-card{
  width:100%;
  min-width:0;
  min-height:74px;
  border-radius:14px;
  background:linear-gradient(180deg,rgba(9,22,35,.98),rgba(5,14,23,.98));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.022),0 5px 20px rgba(0,0,0,.10);
}
[data-testid="cfb-top-picks-step5-root"] .tp2-card:hover{
  transform:translateY(-1px);
}
[data-testid="cfb-top-picks-step5-root"] .tp2-teamline,
[data-testid="cfb-top-picks-step5-root"] .tp2-pick{
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
}
[data-testid="cfb-top-picks-step5-root"] .tp2-rank{
  flex:none;
}
[data-testid="cfb-top-picks-step5-root"] .tp4-card-link{
  width:100%;
  min-width:0;
}
[data-testid="cfb-top-picks-step5-root"] .tp4-panel{
  overflow:hidden;
}
.tp5-step-marker{
  position:absolute;
  width:1px;
  height:1px;
  overflow:hidden;
  opacity:.001;
  pointer-events:none;
}
@media(max-width:1100px){
  [data-testid="cfb-top-picks-step5-root"] .tp1-hero{
    gap:16px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-chip{
    min-width:96px;
    padding-left:12px;
    padding-right:12px;
  }
}
@media(max-width:900px){
  [data-testid="cfb-top-picks-step5-root"] .tp1-hero{
    grid-template-columns:1fr;
    gap:11px;
    padding-bottom:11px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-actions{
    width:100%;
    justify-content:space-between;
    gap:9px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-segmented{
    flex:1 1 auto;
    min-width:0;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-chip{
    flex:1 1 0;
    min-width:0;
    white-space:nowrap;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp3-live{
    align-items:flex-start;
    flex-direction:column;
    gap:4px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp4-panel{
    margin-left:2px;
    margin-right:2px;
  }
}
@media(max-width:820px){
  [data-testid="cfb-top-picks-step5-root"] .tp2-card{
    grid-template-columns:44px minmax(0,1fr) 72px 27px;
    min-height:88px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-cell{
    padding:8px 9px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-matchup{
    grid-template-columns:38px minmax(0,1fr);
    gap:8px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-logos{
    width:36px;
    height:40px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-logo{
    width:27px;
    height:27px;
    border-radius:8px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-pickline{
    justify-content:flex-start;
    gap:8px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-pick{
    max-width:100%;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp4-grid{
    grid-template-columns:1fr;
  }
}
@media(max-width:640px){
  [data-testid="cfb-top-picks-step5-root"]{
    padding-left:0;
    padding-right:0;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-title{
    font-size:clamp(2.1rem,11vw,3rem);
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-subtitle{
    margin-top:7px;
    font-size:.92rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-actions{
    display:grid;
    grid-template-columns:1fr;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-segmented{
    width:100%;
    overflow:hidden;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-chip{
    padding:9px 5px;
    font-size:.72rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp1-date{
    min-height:38px;
    padding:0 11px;
    font-size:.78rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp3-live{
    margin-left:0;
    margin-right:0;
    padding:7px 9px;
    font-size:.64rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-card{
    grid-template-columns:38px minmax(0,1fr) 62px 22px;
    min-height:82px;
    border-radius:11px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-rank{
    width:31px;
    height:31px;
    font-size:.78rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-cell{
    padding:7px 6px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-matchup{
    grid-template-columns:31px minmax(0,1fr);
    gap:6px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-logos{
    width:30px;
    height:35px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-logo{
    width:23px;
    height:23px;
    border-radius:7px;
    font-size:.48rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-logo.h{left:6px}
  [data-testid="cfb-top-picks-step5-root"] .tp2-teams{
    gap:2px;
    font-size:.75rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-vs{
    font-size:.62rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-bet{
    gap:5px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-market{
    padding:4px 6px;
    font-size:.50rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-pick{
    font-size:.76rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-odds{
    font-size:.60rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-prob{
    width:43px;
    height:43px;
    font-size:.68rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp2-chevron{
    font-size:1rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp4-panel{
    margin:0 1px 3px;
    padding:9px;
    border-radius:0 0 10px 10px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp4-box{
    padding:9px;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp4-box h4{
    font-size:.64rem;
  }
  [data-testid="cfb-top-picks-step5-root"] .tp4-box p,
  [data-testid="cfb-top-picks-step5-root"] .tp4-history-row,
  [data-testid="cfb-top-picks-step5-root"] .tp4-nohist,
  [data-testid="cfb-top-picks-step5-root"] .tp4-loading{
    font-size:.69rem;
  }
}
</style>
"""


def _page_html(
    picks: list[dict],
    diag: dict,
    slate_day: str,
    selected_event: str = "",
    selected_detail: dict | None = None,
) -> str:
    html = prior._page_html(picks, diag, slate_day, selected_event, selected_detail)
    old = '<section data-testid="cfb-top-picks-step4-root">'
    new = (
        '<section data-testid="cfb-top-picks-step5-root" '
        'data-cfb-top-picks-visual="v5">'
        f'<div class="tp5-step-marker" data-testid="cfb-top-picks-step5-marker">{PAGE_MARKER}</div>'
    )
    if old not in html:
        raise RuntimeError("Step 5 could not find the frozen Step-4 root.")
    return html.replace(old, new, 1)


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    with st.spinner("Building the verified College Football Top 10..."):
        picks, diag = prior.engine.build_top_picks(limit=10)

    slate_day = str(diag.get("slate_date") or "Today")
    selected_event = prior._query_value(prior.TOP_PICK_DETAIL_QUERY)
    selected_row = next(
        (row for row in picks if str(row.get("event_id") or "").strip() == selected_event),
        None,
    )

    board = st.empty()
    initial_detail = prior._loading_detail(selected_row) if selected_row is not None else None
    board.markdown(
        _page_html(picks, diag, slate_day, selected_event, initial_detail),
        unsafe_allow_html=True,
    )

    if selected_row is not None:
        with st.spinner("Loading verified matchup history..."):
            selected_detail = prior.details.build_pick_detail(selected_row, slate_day)
        board.markdown(
            _page_html(picks, diag, slate_day, selected_event, selected_detail),
            unsafe_allow_html=True,
        )

    if not picks:
        st.markdown(
            '<div class="tp3-empty">No verified Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Step 5 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS",
    "HISTORY_PROJECTION_INFLUENCE",
    "LAYOUT_PREVIEW",
    "MAY_MODIFY_HISTORY",
    "MAY_MODIFY_RANKING",
    "MODEL_VERSION",
    "PAGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_page_html",
    "render_cfb_hub",
    "render_top_picks_page",
]
