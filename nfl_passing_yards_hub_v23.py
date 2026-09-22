"""NFL Passing Yards V23 — Step 10 market-card header polish.

Presentation-only wrapper over certified V22. This layer fixes the visual flex
interaction between the V21 team-logo slot and V22 quarterback-headshot slot so
the headshot stays a compact circular ID portrait instead of stretching across
the card. It also tightens alignment among logo, portrait, player text, and grade.

No identity, market, projection, probability, fair-odds, no-vig, EV, grading,
confidence, API, or sportsbook logic is changed. V22/V21/V20 remain frozen.
Sportsbook projection influence remains 0.0%. Stake sizing remains OFF.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v22 as prior

MODEL_VERSION = "NFL PASSING YARDS V23 • STEP 10 CARD HEADER POLISH • V22/V21/V20 FROZEN"
FROZEN_PRIOR = "nfl_passing_yards_hub_v22"

_POLISH_CSS = r"""
<style>
/* V23 is CSS-only. Important overrides intentionally beat the older V21/V22
   sibling-flex selectors without modifying their certified HTML or identity. */
.kpy10-card .kpy10-top{
  align-items:center!important;
  gap:8px!important;
  margin-bottom:10px!important;
}
.kpy10-card .kpy21-team-logo-slot{
  width:36px!important;
  height:36px!important;
  flex:0 0 36px!important;
  margin:0!important;
  padding:4px!important;
  border-radius:10px!important;
}
.kpy10-card .kpy22-player-headshot-slot,
.kpy10-card .kpy10-top>.kpy21-team-logo-slot+.kpy22-player-headshot-slot{
  width:48px!important;
  height:48px!important;
  flex:0 0 48px!important;
  min-width:48px!important;
  max-width:48px!important;
  margin:0!important;
  border-radius:50%!important;
}
.kpy10-card .kpy22-player-headshot{
  width:48px!important;
  height:48px!important;
  object-fit:cover!important;
  object-position:center top!important;
}
.kpy10-card .kpy10-top>.kpy22-player-headshot-slot+div{
  flex:1 1 auto!important;
  min-width:0!important;
}
.kpy10-card .kpy10-name{
  font-size:.98rem!important;
  line-height:1.15!important;
}
.kpy10-card .kpy10-sub{
  margin-top:4px!important;
  line-height:1.35!important;
}
.kpy10-card .kpy10-grade{
  flex:0 0 auto!important;
  margin-left:auto!important;
  align-self:center!important;
}
@media(max-width:820px){
  .kpy10-card .kpy10-top{gap:7px!important}
  .kpy10-card .kpy21-team-logo-slot{
    width:32px!important;height:32px!important;flex-basis:32px!important;
  }
  .kpy10-card .kpy22-player-headshot-slot,
  .kpy10-card .kpy10-top>.kpy21-team-logo-slot+.kpy22-player-headshot-slot{
    width:44px!important;height:44px!important;min-width:44px!important;
    max-width:44px!important;flex-basis:44px!important;
  }
  .kpy10-card .kpy22-player-headshot{width:44px!important;height:44px!important}
  .kpy10-card .kpy10-name{font-size:.92rem!important}
}
</style>
"""


def render_nfl_passing_yards_hub() -> None:
    # Load the higher-specificity CSS before V22. !important is used only on
    # presentation properties so the certified V22/V21 markup and logic stay intact.
    st.markdown(_POLISH_CSS, unsafe_allow_html=True)
    prior.render_nfl_passing_yards_hub()
    st.caption(
        f"{MODEL_VERSION} • compact logo/headshot alignment only • frozen market/model logic preserved • sportsbook projection influence = 0.0% • stake sizing OFF"
    )


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_POLISH_CSS",
    "render_nfl_passing_yards_hub",
]
