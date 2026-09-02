"""MLB Matchup Explorer V3.2 — mobile-clean presentation over frozen logic."""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_player_v22 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.2 UI"
FROZEN_MATCHUP_CHAIN = (
    "mlb_matchup_player_v21",
    "mlb_matchup_player_v20",
    "mlb_matchup_player_v19",
    "mlb_matchup_player_v18",
    "mlb_matchup_player_v15",
    "mlb_matchup_hub_v14",
    "mlb_matchup_hub_v13",
    "mlb_matchup_hub_v12",
)

_TECHNICAL_CAPTION_MARKERS = (
    "MLB Matchup Hub V",
    "MLB Player Intelligence V",
    "strict-budget deep micro-pass",
    "production projection engines unchanged",
    "frozen production engines remain read-only",
)

_CSS = r"""
<style>
/* Matchup Explorer V3.2 presentation-only overrides. */
.mh-hero{padding:15px 16px!important;border-radius:18px!important;margin:8px 0 12px!important}
.mh-title{font-size:clamp(1.45rem,6vw,2rem)!important;margin:5px 0!important}
.mh-sub{font-size:.74rem!important;line-height:1.45!important}
.mh-game{padding:13px 14px!important;border-radius:17px!important;margin:8px 0 12px!important}
.mh-teamrow{grid-template-columns:minmax(0,1fr) 30px minmax(0,1fr)!important;gap:7px!important}
.mh-team{font-size:clamp(.82rem,3.7vw,1.05rem)!important;min-width:0!important}
.mh-team img{height:44px!important;max-width:60px!important;margin-bottom:5px!important}
.mh-at{font-size:1rem!important}.mh-meta{font-size:.68rem!important;line-height:1.45!important}
.mh-player{padding:13px!important;border-radius:17px!important;margin:10px 0!important}
.mh-name{font-size:clamp(1.25rem,5vw,1.7rem)!important}.mh-small{font-size:.68rem!important}
.mh-season{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:5px!important}
.mh-stat{padding:7px 4px!important;border-radius:10px!important}.mh-stat b{font-size:.92rem!important}.mh-stat span{font-size:.43rem!important;letter-spacing:.05em!important}
.mx-proj{border-radius:16px!important;padding:12px!important;margin:9px 0 7px!important}
.mx-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}
.mx-cell{padding:8px!important;border-radius:10px!important;min-width:0!important}.mx-cell span{font-size:.46rem!important}.mx-cell b{font-size:.78rem!important;overflow-wrap:anywhere!important}
.mx-engine{font-size:.55rem!important}.mx-badge{font-size:.50rem!important}.mx-big{font-size:2rem!important}
.mx22-snapshot{border:1px solid #31516e;border-radius:18px;background:linear-gradient(145deg,#0b1b2d,#08131f);padding:14px 15px;margin:4px 0 10px}
.mx22-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.mx22-eyebrow{color:#5bdcff;font-size:.57rem;font-weight:950;letter-spacing:.12em}.mx22-title{font-size:1.16rem;font-weight:950;color:#f8fafc;line-height:1.18;margin-top:4px}.mx22-title span{display:block;color:#9fb0c7;font-size:.72rem;font-weight:750;margin-top:4px}.mx22-grade{border:1px solid #37536d;border-radius:999px;padding:5px 8px;color:#d8e7f3;font-size:.55rem;font-weight:950;white-space:nowrap}.mx22-main{display:grid;grid-template-columns:1.05fr 1fr;gap:10px;align-items:end;margin-top:12px}.mx22-prob b{display:block;color:#fff;font-size:2.35rem;line-height:.95}.mx22-prob span{display:block;color:#8ea2b9;font-size:.58rem;font-weight:900;text-transform:uppercase;margin-top:5px}.mx22-quick{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.mx22-quick div,.mx22-evidence div{border:1px solid #253e57;background:#081522;border-radius:10px;padding:7px}.mx22-quick span,.mx22-evidence span{display:block;color:#718aa3;font-size:.44rem;font-weight:900;text-transform:uppercase}.mx22-quick b,.mx22-evidence b{display:block;color:#f5f8fc;font-size:.72rem;margin-top:2px;overflow-wrap:anywhere}.mx22-foot{color:#7890a6;font-size:.52rem;margin-top:9px;line-height:1.4}.mx22-evidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
div[data-testid="stExpander"]{border-radius:13px!important}
@media(max-width:640px){
  .mh-season{grid-template-columns:repeat(3,minmax(0,1fr))!important}
  .mx22-main{grid-template-columns:1fr!important}.mx22-prob b{font-size:2.1rem}.mx22-quick{grid-template-columns:repeat(3,minmax(0,1fr))}
  .mx22-evidence{grid-template-columns:1fr!important}.mx-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
</style>
"""


def _filtered_caption(original):
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if any(marker in text for marker in _TECHNICAL_CAPTION_MARKERS):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.caption("🔒 Matchup Explorer model chain frozen • cleaner mobile presentation only.")

    original_caption = st.caption
    st.caption = _filtered_caption(original_caption)
    try:
        player_layer.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption

    with st.expander("🏅 Daily Top 5 — 1+ Hit rankings", expanded=False):
        rankings.render_daily_rankings(games_df)


__all__ = ["FROZEN_MATCHUP_CHAIN", "VERSION", "render_matchup_hub"]
