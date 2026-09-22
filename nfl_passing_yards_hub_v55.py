"""NFL Passing Yards V55 — universal analysis sections Step 5.

Presentation-only wrapper over frozen V54. This layer unifies the already-
certified analytical readouts (baseline projection, bounded context,
distribution/probability, and market evaluation) under the universal semantic
token system. It does not change data, projection, probability, market, widget,
routing, sportsbook influence, or stake behavior.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v54 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V55 • UNIVERSAL ANALYSIS SECTIONS STEP 5"
FROZEN_PRIOR = "nfl_passing_yards_hub_v54"
VISUAL_UPGRADE_STEP = 5
ANALYSIS_SYSTEM_VERSION = "v55"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_ANALYSIS_CSS = r"""
<style data-passing-yards-analysis-system="v55">
.st-key-kyre_passing_yards_shell_v1 .kpy-proj,
.st-key-kyre_passing_yards_shell_v1 .kpy8-card,
.st-key-kyre_passing_yards_shell_v1 .kpy9-card,
.st-key-kyre_passing_yards_shell_v1 .kpy10-card{
  position:relative!important;
  min-width:0;
  overflow:hidden;
  padding:var(--kyre-space-4)!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projtop,
.st-key-kyre_passing_yards_shell_v1 .kpy8-top,
.st-key-kyre_passing_yards_shell_v1 .kpy9-top,
.st-key-kyre_passing_yards_shell_v1 .kpy10-top{
  align-items:center!important;
  gap:var(--kyre-space-3)!important;
  margin-bottom:var(--kyre-space-3)!important;
  padding-bottom:var(--kyre-space-3)!important;
  border-bottom:1px solid var(--kyre-sem-border-soft)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projname,
.st-key-kyre_passing_yards_shell_v1 .kpy8-name,
.st-key-kyre_passing_yards_shell_v1 .kpy9-name,
.st-key-kyre_passing_yards_shell_v1 .kpy10-name{
  color:var(--kyre-sem-text-primary)!important;
  font-weight:950!important;
  line-height:1.2!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projsub,
.st-key-kyre_passing_yards_shell_v1 .kpy8-sub,
.st-key-kyre_passing_yards_shell_v1 .kpy9-sub,
.st-key-kyre_passing_yards_shell_v1 .kpy10-sub{
  color:var(--kyre-sem-text-muted)!important;
  line-height:1.5!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projgrade,
.st-key-kyre_passing_yards_shell_v1 .kpy8-grade,
.st-key-kyre_passing_yards_shell_v1 .kpy9-grade,
.st-key-kyre_passing_yards_shell_v1 .kpy10-grade{
  flex:0 0 auto;
  border-color:var(--kyre-sem-border-strong)!important;
  background:var(--kyre-sem-accent-wash-soft)!important;
  color:var(--kyre-sem-text-accent-soft)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero,
.st-key-kyre_passing_yards_shell_v1 .kpy-projmeta,
.st-key-kyre_passing_yards_shell_v1 .kpy8-meta,
.st-key-kyre_passing_yards_shell_v1 .kpy9-q,
.st-key-kyre_passing_yards_shell_v1 .kpy10-metrics{
  gap:var(--kyre-space-2)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero>div,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero>div,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero>div,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero>div,
.st-key-kyre_passing_yards_shell_v1 .kpy-projmeta>div,
.st-key-kyre_passing_yards_shell_v1 .kpy8-meta>div,
.st-key-kyre_passing_yards_shell_v1 .kpy9-q>div,
.st-key-kyre_passing_yards_shell_v1 .kpy10-metrics>div{
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-surface-column)!important;
  color:var(--kyre-sem-text-secondary)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero b,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero b,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero b,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero b,
.st-key-kyre_passing_yards_shell_v1 .kpy-projmeta b,
.st-key-kyre_passing_yards_shell_v1 .kpy8-meta b,
.st-key-kyre_passing_yards_shell_v1 .kpy9-q b,
.st-key-kyre_passing_yards_shell_v1 .kpy10-metrics b{
  color:var(--kyre-sem-text-primary)!important;
  font-weight:900!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero span,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero span,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero span,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero span,
.st-key-kyre_passing_yards_shell_v1 .kpy9-q span{
  color:var(--kyre-sem-text-muted)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projctx,
.st-key-kyre_passing_yards_shell_v1 .kpy8-note,
.st-key-kyre_passing_yards_shell_v1 .kpy9-note,
.st-key-kyre_passing_yards_shell_v1 .kpy10-note{
  margin-top:var(--kyre-space-3)!important;
  padding-top:var(--kyre-space-3)!important;
  border-top:1px solid var(--kyre-sem-border-soft)!important;
  color:var(--kyre-sem-text-secondary)!important;
  line-height:1.6!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projctx b,
.st-key-kyre_passing_yards_shell_v1 .kpy8-note b,
.st-key-kyre_passing_yards_shell_v1 .kpy9-note b,
.st-key-kyre_passing_yards_shell_v1 .kpy10-note b{
  color:var(--kyre-sem-text-accent-soft)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy8-active,
.st-key-kyre_passing_yards_shell_v1 .kpy9-active,
.st-key-kyre_passing_yards_shell_v1 .kpy10-active{
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy8-active b,
.st-key-kyre_passing_yards_shell_v1 .kpy9-active b,
.st-key-kyre_passing_yards_shell_v1 .kpy10-active b{
  color:var(--kyre-sem-text-accent)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy8-active span,
.st-key-kyre_passing_yards_shell_v1 .kpy9-active span,
.st-key-kyre_passing_yards_shell_v1 .kpy10-active span{
  color:var(--kyre-sem-text-secondary)!important;
}
@media(max-width:820px){
  .st-key-kyre_passing_yards_shell_v1 .kpy-projgrid,
  .st-key-kyre_passing_yards_shell_v1 .kpy8-grid,
  .st-key-kyre_passing_yards_shell_v1 .kpy9-grid,
  .st-key-kyre_passing_yards_shell_v1 .kpy10-grid{
    grid-template-columns:1fr!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .kpy-projhero,
  .st-key-kyre_passing_yards_shell_v1 .kpy8-hero,
  .st-key-kyre_passing_yards_shell_v1 .kpy9-hero,
  .st-key-kyre_passing_yards_shell_v1 .kpy10-hero{
    grid-template-columns:1fr 1fr!important;
  }
}
@media(max-width:620px){
  .st-key-kyre_passing_yards_shell_v1 .kpy-proj,
  .st-key-kyre_passing_yards_shell_v1 .kpy8-card,
  .st-key-kyre_passing_yards_shell_v1 .kpy9-card,
  .st-key-kyre_passing_yards_shell_v1 .kpy10-card{
    padding:var(--kyre-space-3)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .kpy9-q{
    grid-template-columns:repeat(2,minmax(0,1fr))!important;
  }
}
</style>
"""

def build_passing_yards_analysis_css() -> str:
    return build_semantic_tokens_css() + _ANALYSIS_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_analysis_css(), unsafe_allow_html=True)
    st.markdown(
        '<span data-passing-yards-analysis-owner="v55" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V55 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "ANALYSIS_SYSTEM_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_analysis_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
