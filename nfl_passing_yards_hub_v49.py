"""NFL Passing Yards V49 — premium Step 10 market control panel.

Presentation-only wrapper over frozen V48. Step 4 of the Passing Yards visual
upgrade. It styles the existing native Streamlit Step 10 market widget block
in place using the frozen field labels. Widget keys, values, market math,
projection logic, and sportsbook influence remain unchanged.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v48 as prior

MODEL_VERSION = "NFL PASSING YARDS V49 • PREMIUM MARKET CONTROL PANEL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v48"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

MARKET_FIELD_LABELS = (
    "Sportsbook / source",
    "Passing yards line",
    "Over American odds",
    "Under American odds",
    "Price timestamp / note",
)

_MARKET_CSS = r"""
<style data-passing-yards-market-polish="v49">
/* The frozen Step 10 renderer creates one horizontal block containing the
   per-quarterback market-input columns. :has() scopes this skin to that exact
   block without changing widget construction, keys, or values. */
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
  position:relative;
  gap:.72rem!important;
  margin:.5rem 0 .9rem!important;
  padding:2.55rem .78rem .78rem!important;
  border:1px solid rgba(88,201,255,.24)!important;
  border-radius:17px!important;
  background:
    radial-gradient(circle at 92% 0%,rgba(88,201,255,.10),transparent 28%),
    linear-gradient(150deg,rgba(11,28,43,.98),rgba(6,16,25,.99))!important;
  box-shadow:0 16px 38px rgba(0,0,0,.20),0 0 26px rgba(46,168,255,.05)!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])::before{
  content:"STEP 10  •  LIVE MARKET CONTROL PANEL";
  position:absolute;left:.8rem;top:.72rem;
  color:#55c7ff;
  font-size:.62rem;font-weight:950;letter-spacing:.105em;
  text-transform:uppercase;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  > [data-testid="stColumn"]{
  min-width:0!important;
  padding:.68rem!important;
  border:1px solid rgba(88,201,255,.13)!important;
  border-radius:13px!important;
  background:rgba(4,14,23,.66)!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  [data-testid="stTextInput"]{
  margin:0 0 .28rem!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  [data-testid="stTextInput"] label{
  color:#bfeaff!important;
  font-size:.62rem!important;
  font-weight:850!important;
  letter-spacing:.018em!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  [data-baseweb="input"]{
  min-height:44px!important;
  background:#08141f!important;
  border:1px solid rgba(88,201,255,.16)!important;
  border-radius:11px!important;
  box-shadow:none!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  input{
  color:#f5faff!important;
  font-size:.76rem!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  input::placeholder{
  color:#617b91!important;
}
[data-testid="stHorizontalBlock"]:has(input[aria-label="Passing yards line"])
  [data-testid="stTextInput"]:has(input[aria-label="Passing yards line"]),
[data-testid="stHorizontalBlock"]:has(input[aria-label="Over American odds"])
  [data-testid="stTextInput"]:has(input[aria-label="Over American odds"]),
[data-testid="stHorizontalBlock"]:has(input[aria-label="Under American odds"])
  [data-testid="stTextInput"]:has(input[aria-label="Under American odds"]){
  border-left:2px solid rgba(88,201,255,.34);
  padding-left:.48rem;
}
@media(max-width:780px){
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
    padding:.72rem!important;
    padding-top:2.55rem!important;
    flex-direction:column!important;
  }
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
    > [data-testid="stColumn"]{
    width:100%!important;
    flex:1 1 auto!important;
  }
}
</style>
"""

def build_market_control_css() -> str:
    return _MARKET_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_market_control_css(), unsafe_allow_html=True)
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V49 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MARKET_FIELD_LABELS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "build_market_control_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
