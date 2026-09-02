"""MLB Moneyline V16.5 — clean mobile presentation over the frozen V16.4 chain.

Presentation-only wrapper. The complete V16.4/V16.3/V16.2/V16.1/V16 model,
schedule, projection, simulation, probability, H2H adjustment, ranking, fair-odds,
API identity/freshness and selection behavior remains delegated byte-for-byte to
its existing modules.

V16.5 only:
- restores scoped card CSS that the memory-safe Streamlit router no longer gets
  from the historical monolithic app shell;
- collapses the existing live sportsbook slate board behind a closed expander;
- replaces repetitive implementation captions with one concise frozen-model note;
- keeps the existing H2H/recent-form details collapsed until requested.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_moneyline_hub_v164 as prior

MODEL_VERSION = "V16.5 • CLEAN MOBILE PRESENTATION • FROZEN V16.4 MODEL"
FROZEN_MODEL_CHAIN = (
    "mlb_moneyline_hub_v164",
    "mlb_moneyline_hub_v163",
    "moneyline_hub_v162",
    "moneyline_hub_v161",
    "moneyline_hub_v16",
)

_TECHNICAL_CAPTION_MARKERS = (
    "MLB Moneyline Step 7C",
    "Moneyline V16.3 isolation",
    "V16.2 adds a live sportsbook market layer",
)

_CSS = r"""
<style>
/* V16.5 scoped Moneyline card presentation. Model/data markup stays upstream. */
.ks-pick-card{
  display:grid;
  grid-template-columns:minmax(0,1fr) auto;
  grid-template-areas:"rank rank" "main right";
  gap:10px 14px;
  margin:12px 0;
  padding:14px;
  border:1px solid rgba(118,171,211,.28);
  border-radius:18px;
  background:linear-gradient(145deg,rgba(12,26,45,.98),rgba(7,17,31,.98));
  box-shadow:0 8px 24px rgba(0,0,0,.18);
  overflow:hidden;
}
.ks-pick-card.ks-first{
  border-color:rgba(255,207,84,.55);
  box-shadow:0 9px 28px rgba(0,0,0,.22),0 0 0 1px rgba(255,207,84,.08) inset;
}
.ks-rank{
  grid-area:rank;
  font-size:.86rem;
  font-weight:900;
  letter-spacing:.02em;
  color:#f3f7fb;
}
.ks-card-main{grid-area:main;min-width:0;}
.ks-player-row{display:flex;align-items:center;gap:11px;min-width:0;}
.ks-player-row img{width:48px!important;height:48px!important;max-width:48px!important;object-fit:contain;flex:0 0 48px;}
.ks-player-copy{min-width:0;}
.ks-player{
  font-size:1.06rem;
  line-height:1.15;
  font-weight:900;
  color:#f8fbff;
  margin-bottom:4px;
}
.ks-matchup{
  color:#a9bac9;
  font-size:.76rem;
  line-height:1.45;
}
.ks-meta-line{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  align-items:center;
  margin-top:10px;
}
.ks-mini,.ks-status,.ks-badge{
  display:inline-flex;
  align-items:center;
  min-height:27px;
  padding:4px 8px;
  border-radius:999px;
  font-size:.68rem;
  font-weight:800;
  line-height:1;
  white-space:nowrap;
}
.ks-mini{background:rgba(121,151,176,.11);border:1px solid rgba(121,151,176,.17);color:#c7d4df;}
.ks-status{background:rgba(101,199,151,.12);border:1px solid rgba(101,199,151,.24);color:#9ae4bd;}
.ks-badge{border:1px solid rgba(121,151,176,.22);}
.ks-high{background:rgba(72,199,142,.13);color:#8de0b5;}
.ks-medium{background:rgba(242,189,83,.12);color:#f2cf85;}
.ks-low{background:rgba(239,111,111,.12);color:#efaaaa;}
.ks-card-details{margin-top:10px;border-top:1px solid rgba(121,151,176,.14);padding-top:8px;}
.ks-card-details summary{cursor:pointer;color:#9cb2c4;font-size:.72rem;font-weight:800;list-style:none;}
.ks-card-details summary::-webkit-details-marker{display:none;}
.ks-detail-body{padding:9px 0 2px;color:#aebdca;font-size:.70rem;line-height:1.58;}
.ks-detail-body b{color:#edf5fb;}
.ks-right{
  grid-area:right;
  align-self:center;
  min-width:108px;
  text-align:right;
  padding-left:12px;
  border-left:1px solid rgba(121,151,176,.14);
}
.ks-prob{font-size:1.75rem;line-height:1;font-weight:950;letter-spacing:-.04em;color:#f9fcff;}
.ks-prob-label{margin-top:4px;color:#8fa4b5;font-size:.64rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;}
.ks-card-meta{display:flex;flex-direction:column;align-items:flex-end;gap:6px;margin-top:10px;}
.ks-card-meta .ks-mini{background:transparent;border-color:rgba(121,151,176,.20);}
.ks164-board{margin:10px 0 12px!important;border-radius:14px!important;}

@media(max-width:640px){
  .ks-pick-card{padding:12px;gap:10px 9px;grid-template-columns:minmax(0,1fr) 92px;}
  .ks-player-row{align-items:flex-start;}
  .ks-player-row img{width:42px!important;height:42px!important;max-width:42px!important;flex-basis:42px;}
  .ks-player{font-size:.98rem;}
  .ks-matchup{font-size:.70rem;}
  .ks-right{min-width:0;padding-left:8px;}
  .ks-prob{font-size:1.52rem;}
  .ks-mini,.ks-status,.ks-badge{font-size:.61rem;min-height:25px;padding:4px 7px;}
}
</style>
"""


def _compact_live_board(original):
    def wrapped(games_df, *args: Any, **kwargs: Any):
        with st.expander("📡 Live sportsbook board", expanded=False):
            return original(games_df, *args, **kwargs)
    return wrapped


def _filtered_caption(original):
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if any(marker in text for marker in _TECHNICAL_CAPTION_MARKERS):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render the frozen Moneyline stack with scoped clean/mobile presentation."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.caption(
        "🔒 Moneyline model frozen • probabilities, simulations, H2H adjustment, ranking and fair odds unchanged • live FanDuel context is display-only."
    )

    # v164.prior -> v163; v163.base -> v162. Patch only the presentation function
    # reference for the duration of this render, then restore it unconditionally.
    v162 = prior.prior.base
    original_live_board = v162.render_live_slate_board
    original_caption = st.caption
    v162.render_live_slate_board = _compact_live_board(original_live_board)
    st.caption = _filtered_caption(original_caption)
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption
        v162.render_live_slate_board = original_live_board


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "MODEL_VERSION",
    "render_moneyline_hub",
]
