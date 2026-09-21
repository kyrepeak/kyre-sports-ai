"""NFL Passing Yards V50 — final responsive polish.

Presentation-only wrapper over frozen V49. Step 5 of the Passing Yards visual
upgrade. It coordinates the already-approved Step 1-4 presentation layers
across desktop, tablet, and mobile breakpoints without changing any widget
keys, route ownership, data, projection, probability, or market behavior.
"""
from __future__ import annotations

import streamlit as st
import nfl_passing_yards_hub_v49 as prior

MODEL_VERSION = "NFL PASSING YARDS V50 • FINAL RESPONSIVE POLISH"
FROZEN_PRIOR = "nfl_passing_yards_hub_v49"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

_RESPONSIVE_CSS = r"""
<style data-passing-yards-responsive-polish="v50">
/* Desktop breathing room */
[data-testid="stAppViewContainer"] .main .block-container{
  max-width:1440px!important;
}

/* Tablet: stop squeezing the two QB cards and the top control deck. */
@media(max-width:1120px){
  .ks-py48-grid{
    grid-template-columns:1fr!important;
  }
  .ks-py48-player{
    border-radius:16px!important;
  }
  .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]{
    flex-direction:column!important;
    align-items:stretch!important;
  }
  .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]
    > [data-testid="stColumn"]{
    width:100%!important;
    flex:1 1 auto!important;
  }
}

/* Tablet portrait / large phones */
@media(max-width:820px){
  [data-testid="stAppViewContainer"] .main .block-container{
    padding-left:.8rem!important;
    padding-right:.8rem!important;
  }
  .ks-py48-head{
    align-items:flex-start!important;
    flex-direction:column!important;
    padding:.76rem!important;
  }
  .ks-py48-evidence{
    grid-template-columns:1fr!important;
  }
  .ks-py48-support{
    grid-template-columns:1fr!important;
  }
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
    flex-direction:column!important;
    padding:.72rem!important;
    padding-top:2.55rem!important;
  }
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
    > [data-testid="stColumn"]{
    width:100%!important;
    flex:1 1 auto!important;
  }
}

/* Phones: touch targets, tighter cards, readable evidence. */
@media(max-width:620px){
  [data-testid="stAppViewContainer"] .main .block-container{
    padding:.62rem!important;
  }
  .st-key-kyre_passing_yards_top_v46{
    padding:.56rem!important;
    margin-bottom:.42rem!important;
  }
  .st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
  .st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div,
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
    [data-baseweb="input"]{
    min-height:48px!important;
  }
  .ks-py48{
    margin:.32rem 0 .9rem!important;
  }
  .ks-py48-head h2{
    font-size:1.18rem!important;
  }
  .ks-py48-head p{
    font-size:.66rem!important;
  }
  .ks-py48-player{
    border-radius:14px!important;
  }
  .ks-py48-playerhead,
  .ks-py48-body{
    padding:.64rem!important;
  }
  .ks-py48-step{
    padding:.58rem!important;
  }
  .ks-py48-stepnum{
    width:30px!important;
    height:30px!important;
  }
  .ks-py48-support details{
    padding:.6rem!important;
  }
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
    > [data-testid="stColumn"]{
    padding:.58rem!important;
  }
}

/* Small phones */
@media(max-width:430px){
  [data-testid="stAppViewContainer"] .main .block-container{
    padding-left:.48rem!important;
    padding-right:.48rem!important;
  }
  .ks-py48-head,
  .st-key-kyre_passing_yards_top_v46,
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
    border-radius:12px!important;
  }
  .ks-py48-board-title{
    align-items:flex-start!important;
    flex-direction:column!important;
  }
}
</style>
"""

def build_final_responsive_css() -> str:
    return _RESPONSIVE_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_final_responsive_css(), unsafe_allow_html=True)
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V50 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "build_final_responsive_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
