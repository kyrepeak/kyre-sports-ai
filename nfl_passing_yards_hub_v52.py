"""NFL Passing Yards V52 — universal semantic tokens Step 2.

Presentation-only wrapper over frozen V51. This layer makes the complete
Passing Yards ownership surface consume centralized semantic design tokens.
It does not alter markup ownership, widget keys, data, identity, projections,
probabilities, market math, sportsbook transport, or stake behavior.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v51 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V52 • UNIVERSAL SEMANTIC TOKENS STEP 2"
FROZEN_PRIOR = "nfl_passing_yards_hub_v51"
VISUAL_UPGRADE_STEP = 2
DESIGN_TOKEN_VERSION = "v2"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_TOKEN_CSS = r"""
<style data-passing-yards-design-tokens="v52">
.st-key-kyre_passing_yards_universal_owner_v1{
  color:var(--kyre-sem-text-primary);
}
.st-key-kyre_passing_yards_universal_owner_v1::before{
  color:var(--kyre-sem-text-accent);
}
.st-key-kyre_passing_yards_universal_owner_v1 h1,
.st-key-kyre_passing_yards_universal_owner_v1 h2,
.st-key-kyre_passing_yards_universal_owner_v1 h3,
.st-key-kyre_passing_yards_universal_owner_v1 h4{
  color:var(--kyre-sem-text-primary)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 p,
.st-key-kyre_passing_yards_universal_owner_v1 label,
.st-key-kyre_passing_yards_universal_owner_v1 small{
  color:var(--kyre-sem-text-secondary);
}

.st-key-kyre_passing_yards_universal_owner_v1 .st-key-kyre_passing_yards_top_v46{
  border-color:var(--kyre-sem-border-strong)!important;
  border-radius:var(--kyre-sem-radius-card)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash),transparent),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 .st-key-kyre_passing_yards_top_v46 label{
  color:var(--kyre-sem-text-accent-soft)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1
  .st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
.st-key-kyre_passing_yards_universal_owner_v1
  .st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div{
  background:var(--kyre-sem-surface-control)!important;
  border-color:var(--kyre-sem-border-medium)!important;
  color:var(--kyre-sem-text-primary)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
}

.st-key-kyre_passing_yards_universal_owner_v1 .ks-py47-head,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-head{
  border-color:var(--kyre-sem-border-strong)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash),transparent),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py47-player,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-player{
  border-color:var(--kyre-sem-border-medium)!important;
  background:linear-gradient(150deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py47-tile,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-market,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-step,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-support details{
  border-color:var(--kyre-sem-border-soft)!important;
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt))!important;
  border-radius:var(--kyre-sem-radius-section)!important;
}

.st-key-kyre_passing_yards_universal_owner_v1
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
  border-color:var(--kyre-sem-border-strong)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  > [data-testid="stColumn"]{
  border-color:var(--kyre-sem-border-soft)!important;
  background:var(--kyre-sem-surface-column)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 [data-testid="stMetric"],
.st-key-kyre_passing_yards_universal_owner_v1 [data-testid="stExpander"]{
  border-color:var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt))!important;
}
</style>
"""

def build_passing_yards_token_css() -> str:
    return build_semantic_tokens_css() + _TOKEN_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_token_css(), unsafe_allow_html=True)
    st.markdown(
        '<span data-passing-yards-token-owner="v52" style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V52 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DESIGN_TOKEN_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_token_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
