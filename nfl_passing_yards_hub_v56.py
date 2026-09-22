"""NFL Passing Yards V56 — universal controls + navigation Step 6.

Presentation-only wrapper over frozen V55. This layer unifies the existing
Passing Yards control deck, matchup navigation, disclosure surfaces, and native
market-control inputs under the universal semantic token system. Widget keys,
selection behavior, routing, data, analytics, projection, probability, market
math, sportsbook influence, and stake behavior remain frozen.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v55 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V56 • UNIVERSAL CONTROLS NAVIGATION STEP 6"
FROZEN_PRIOR = "nfl_passing_yards_hub_v55"
VISUAL_UPGRADE_STEP = 6
CONTROL_SYSTEM_VERSION = "v56"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_ROUTING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_CONTROL_CSS = r"""
<style data-passing-yards-control-system="v56">
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46{
  margin:var(--kyre-space-2) 0 var(--kyre-space-4)!important;
  padding:var(--kyre-space-4)!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-card)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stCaptionContainer"]{
  margin:0 0 var(--kyre-space-2)!important;
  color:var(--kyre-sem-text-accent)!important;
  font-weight:950!important;
  letter-spacing:.08em!important;
  text-transform:uppercase!important;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]{
  align-items:end!important;
  gap:var(--kyre-space-3)!important;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 label{
  color:var(--kyre-sem-text-accent-soft)!important;
  font-weight:900!important;
  letter-spacing:.02em!important;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div{
  min-height:48px!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-surface-control)!important;
  box-shadow:none!important;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stDateInput"]:focus-within [data-baseweb="input"],
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stSelectbox"]:focus-within [data-baseweb="select"]>div{
  border-color:var(--kyre-sem-border-strong)!important;
  box-shadow:var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 input{
  color:var(--kyre-sem-text-primary)!important;
  font-weight:800!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stExpander"]{
  overflow:hidden!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-control),var(--kyre-sem-surface-panel))!important;
  box-shadow:none!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stExpander"] summary{
  min-height:44px!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-weight:900!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stExpander"]:focus-within,
.st-key-kyre_passing_yards_shell_v1 [data-testid="stExpander"]:hover{
  border-color:var(--kyre-sem-border-medium)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-detail,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support details{
  overflow:hidden!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-control),var(--kyre-sem-surface-panel))!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-detail summary,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support summary{
  min-height:40px!important;
  color:var(--kyre-sem-text-accent)!important;
  font-weight:900!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stButton"] button{
  min-height:44px!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-surface-control)!important;
  color:var(--kyre-sem-text-primary)!important;
  box-shadow:none!important;
  font-weight:900!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stButton"] button:hover,
.st-key-kyre_passing_yards_shell_v1 [data-testid="stButton"] button:focus-visible{
  border-color:var(--kyre-sem-border-strong)!important;
  background:var(--kyre-sem-surface-panel-alt)!important;
  box-shadow:var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
  border-color:var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-card)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent 30%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card)!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  [data-baseweb="input"]{
  min-height:46px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-surface-control)!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  input{
  color:var(--kyre-sem-text-primary)!important;
}
@media(max-width:900px){
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]{
    flex-direction:column!important;
    align-items:stretch!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]
    > [data-testid="stColumn"]{
    width:100%!important;
    flex:1 1 auto!important;
  }
}
@media(max-width:620px){
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46{
    padding:var(--kyre-space-3)!important;
    border-radius:var(--kyre-sem-radius-section)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div,
  .st-key-kyre_passing_yards_shell_v1 [data-testid="stButton"] button{
    min-height:48px!important;
  }
}
</style>
"""

def build_passing_yards_control_css() -> str:
    return build_semantic_tokens_css() + _CONTROL_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_control_css(), unsafe_allow_html=True)
    st.markdown(
        '<span data-passing-yards-control-owner="v56" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V56 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "CONTROL_SYSTEM_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_ROUTING",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_control_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
