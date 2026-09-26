"""NFL Prop Analytics V1 — Step 1 route + ownership foundation.

This module owns only NFL -> Prop Analytics. The Step 1 route foundation stays
intact while Step 2 adds an independent, fail-closed Schedule Truth Layer for
Page 1. Player-prop analytics remain out of scope.

Passing Yards and every existing NFL market remain owned by their frozen
routers/modules.
"""
from __future__ import annotations

import streamlit as st

from nfl_prop_analytics_schedule_v1 import render_schedule_truth_layer
from nfl_prop_analytics_game_select_v1 import render_game_selection_handoff
from nfl_prop_analytics_roster_truth_v1 import render_verified_roster_truth
from nfl_prop_analytics_matchup_shell_v1 import (
    is_matchup_page,
    render_matchup_open_control,
    render_matchup_shell,
)

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 1 ROUTE OWNERSHIP"
PROP_ANALYTICS_VERSION = "v1"
MARKET = "Prop Analytics"
STEP = 1
PAGE = 1
ROUTE_ONLY = True
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def render_prop_analytics_page() -> None:
    st.markdown(
        """
<section class="ks-prop-analytics-v1"
         data-nfl-prop-analytics-route="v1"
         data-prop-analytics-owner="nfl_prop_analytics_hub_v1"
         data-prop-analytics-step="1"
         data-prop-analytics-page="1">
  <div class="ks-pa1-eyebrow">NFL • PROP ANALYTICS</div>
  <h1 class="ks-pa1-title">Prop Analytics</h1>
  <p class="ks-pa1-copy">
    Game hub route ready. The verified Sunday-to-Thursday schedule board is the
    next build step.
  </p>
  <div class="ks-pa1-state" role="status">
    <span>Page 1</span>
    <span>Route + ownership certified foundation</span>
  </div>
</section>
<style data-nfl-prop-analytics-step1-css="v1">
.ks-prop-analytics-v1{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow-x:clip;
  margin:8px 0 18px;
  padding:clamp(18px,3vw,30px);
  border:1px solid rgba(125,211,252,.22);
  border-radius:18px;
  background:
    radial-gradient(circle at 92% 8%,rgba(14,165,233,.12),transparent 18rem),
    linear-gradient(145deg,rgba(7,14,24,.98),rgba(10,22,38,.96));
}
.ks-pa1-eyebrow{
  color:#7dd3fc;
  font-size:.72rem;
  font-weight:900;
  letter-spacing:.16em;
}
.ks-pa1-title{
  margin:.35rem 0 .45rem;
  color:#f8fafc;
  font-size:clamp(1.8rem,5vw,3rem);
  line-height:1;
  letter-spacing:-.04em;
}
.ks-pa1-copy{
  max-width:720px;
  margin:0;
  color:#a9bad0;
  font-size:.92rem;
  line-height:1.55;
}
.ks-pa1-state{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  margin-top:18px;
}
.ks-pa1-state span{
  min-height:40px;
  display:inline-flex;
  align-items:center;
  padding:8px 12px;
  border:1px solid rgba(125,211,252,.18);
  border-radius:999px;
  color:#dbeafe;
  background:rgba(14,165,233,.06);
  font-size:.74rem;
  font-weight:800;
}
@media(max-width:520px){
  .ks-prop-analytics-v1{padding:16px 14px;border-radius:15px}
  .ks-pa1-state{display:grid;grid-template-columns:1fr}
  .ks-pa1-state span{width:100%}
}
</style>
""",
        unsafe_allow_html=True,
    )
    if is_matchup_page():
        handoff = render_matchup_shell()
        if handoff:
            render_verified_roster_truth(handoff)
        return

    render_schedule_truth_layer()
    handoff = render_game_selection_handoff()
    render_matchup_open_control(handoff)


def render_nfl_hub(market: str = MARKET) -> None:
    if str(market or "").strip() != MARKET:
        raise ValueError("NFL Prop Analytics V1 only renders Prop Analytics.")
    return render_prop_analytics_page()


__all__ = [
    "MARKET",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PROP_ANALYTICS_VERSION",
    "ROUTE_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "render_nfl_hub",
    "render_game_selection_handoff",
    "render_matchup_open_control",
    "render_matchup_shell",
    "render_verified_roster_truth",
    "render_schedule_truth_layer",
    "render_prop_analytics_page",
]
