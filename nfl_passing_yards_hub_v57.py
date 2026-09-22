"""NFL Passing Yards V57 — responsive tablet/mobile Step 7.

Presentation-only wrapper over frozen V56. This layer coordinates the certified
Passing Yards shell, cards, analysis sections, controls, disclosure surfaces,
and market inputs across desktop, tablet, and phone widths. It changes layout
and sizing only; all widget keys, navigation behavior, data, analytics,
projection, probability, market math, sportsbook influence, and stake behavior
remain frozen.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v56 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V57 • RESPONSIVE TABLET MOBILE STEP 7"
FROZEN_PRIOR = "nfl_passing_yards_hub_v56"
VISUAL_UPGRADE_STEP = 7
RESPONSIVE_SYSTEM_VERSION = "v57"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_ROUTING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_RESPONSIVE_CSS = r"""
<style data-passing-yards-responsive-system="v57">
.st-key-kyre_passing_yards_shell_v1,
.st-key-kyre_passing_yards_shell_v1 .ks-py53-hero,
.st-key-kyre_passing_yards_shell_v1 .ks-py47,
.st-key-kyre_passing_yards_shell_v1 .ks-py48,
.st-key-kyre_passing_yards_shell_v1 .ks-py47-grid,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-grid,
.st-key-kyre_passing_yards_shell_v1 .ks-py47-player,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-player,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-evidence,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support{
  min-width:0!important;
  max-width:100%!important;
}
.st-key-kyre_passing_yards_shell_v1 img,
.st-key-kyre_passing_yards_shell_v1 svg,
.st-key-kyre_passing_yards_shell_v1 canvas,
.st-key-kyre_passing_yards_shell_v1 table{
  max-width:100%!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stDataFrame"],
.st-key-kyre_passing_yards_shell_v1 [data-testid="stTable"]{
  max-width:100%!important;
  overflow-x:auto!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-body,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-body,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-market,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support details{
  min-width:0!important;
  overflow-wrap:anywhere!important;
}
@media(max-width:1120px){
  .st-key-kyre_passing_yards_shell_v1{
    width:100%!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-hero{
    gap:var(--kyre-space-4)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-grid,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-grid{
    grid-template-columns:1fr!important;
  }
}
@media(max-width:900px){
  .st-key-kyre_passing_yards_shell_v1{
    padding:var(--kyre-space-4)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-hero{
    flex-direction:column!important;
    align-items:stretch!important;
    padding:var(--kyre-space-5)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-status{
    width:100%!important;
    justify-content:flex-start!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"],
  .st-key-kyre_passing_yards_shell_v1 [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
    flex-direction:column!important;
    align-items:stretch!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-kyre_passing_yards_shell_v1 [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]) > [data-testid="stColumn"]{
    width:100%!important;
    min-width:0!important;
    flex:1 1 auto!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-primary,
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-evidence,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-evidence,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-support{
    grid-template-columns:1fr!important;
  }
}
@media(max-width:680px){
  .st-key-kyre_passing_yards_shell_v1{
    margin-bottom:var(--kyre-space-4)!important;
    padding:var(--kyre-space-3)!important;
    border-radius:var(--kyre-sem-radius-section)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-hero{
    padding:var(--kyre-space-4)!important;
    border-radius:var(--kyre-sem-radius-section)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-title{
    font-size:clamp(1.75rem,10vw,2.35rem)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-status{
    gap:var(--kyre-space-2)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-chip{
    max-width:100%!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-head,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-head{
    flex-direction:column!important;
    align-items:flex-start!important;
    padding:var(--kyre-space-3)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-player,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-player{
    border-radius:var(--kyre-sem-radius-section)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-playerhead,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-playerhead,
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-body,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-body{
    padding:var(--kyre-space-3)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .kpy-projhero,
  .st-key-kyre_passing_yards_shell_v1 .kpy8-hero,
  .st-key-kyre_passing_yards_shell_v1 .kpy9-hero,
  .st-key-kyre_passing_yards_shell_v1 .kpy10-hero,
  .st-key-kyre_passing_yards_shell_v1 .kpy-projmeta,
  .st-key-kyre_passing_yards_shell_v1 .kpy8-meta,
  .st-key-kyre_passing_yards_shell_v1 .kpy9-q,
  .st-key-kyre_passing_yards_shell_v1 .kpy10-metrics{
    grid-template-columns:1fr!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stDateInput"] input,
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stDateInput"] [role="textbox"],
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stDateInput"] button,
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stSelectbox"] [role="combobox"],
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stSelectbox"] input,
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-testid="stSelectbox"] button,
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div,
  .st-key-kyre_passing_yards_shell_v1 [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]) [data-baseweb="input"],
  .st-key-kyre_passing_yards_shell_v1 [data-testid="stButton"] button,
  .st-key-kyre_passing_yards_shell_v1 [data-testid="stExpander"] summary{
    min-height:48px!important;
    box-sizing:border-box!important;
  }
}
@media(max-width:430px){
  .st-key-kyre_passing_yards_shell_v1{
    padding:var(--kyre-space-2)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-hero,
  .st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46{
    padding:var(--kyre-space-3)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py53-chip{
    width:100%!important;
    justify-content:center!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-board-title{
    flex-direction:column!important;
    align-items:flex-start!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-step{
    padding:var(--kyre-space-3)!important;
  }
}
</style>
"""

def build_passing_yards_responsive_css() -> str:
    return build_semantic_tokens_css() + _RESPONSIVE_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_responsive_css(), unsafe_allow_html=True)
    st.markdown(
        '<span data-passing-yards-responsive-owner="v57" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V57 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_ROUTING",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "RESPONSIVE_SYSTEM_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_responsive_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
