"""NFL Passing Yards V55 — universal analysis sections Step 5.

Presentation-only wrapper over frozen V54. This layer improves the readable
hierarchy of the existing Passing Yards analytical evidence surfaces: baseline
projection, context/uncertainty, distribution/probability, market evaluation,
and support evidence. It does not recompute or reinterpret any analytical
payload and leaves the certified V54 card system plus V53/V52/V51 layers frozen.
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
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_ANALYSIS_CSS = r"""
<style data-passing-yards-analysis-system="v55">
.st-key-kyre_passing_yards_shell_v1 .ks-py48-board-title{
  margin:var(--kyre-space-4) 0 var(--kyre-space-3)!important;
  padding:0 0 var(--kyre-space-3)!important;
  border-bottom:1px solid var(--kyre-sem-border-medium)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-board-title b{
  color:var(--kyre-sem-text-primary)!important;
  font-size:.78rem!important;
  font-weight:950!important;
  letter-spacing:.02em!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-board-title span{
  color:var(--kyre-sem-text-muted)!important;
  font-size:.56rem!important;
  font-weight:750!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step{
  position:relative!important;
  overflow:hidden!important;
  min-width:0!important;
  padding:var(--kyre-space-4)!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step[data-step="7"],
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step[data-step="8"],
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step[data-step="9"]{
  border-color:var(--kyre-sem-border-strong)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-stepnum{
  width:30px!important;
  height:30px!important;
  margin-bottom:var(--kyre-space-3)!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-accent-wash)!important;
  color:var(--kyre-sem-text-accent)!important;
  font-size:.62rem!important;
  font-weight:950!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step > strong{
  margin-bottom:var(--kyre-space-3)!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-size:.62rem!important;
  line-height:1.35!important;
  letter-spacing:.065em!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy-proj,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy8-card,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy9-card,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-market .kpy10-card{
  margin:0!important;
  padding:var(--kyre-space-3)!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-control),var(--kyre-sem-surface-panel))!important;
  box-shadow:none!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projtop,
.st-key-kyre_passing_yards_shell_v1 .kpy8-top,
.st-key-kyre_passing_yards_shell_v1 .kpy9-top,
.st-key-kyre_passing_yards_shell_v1 .kpy10-top{
  align-items:flex-start!important;
  gap:var(--kyre-space-2)!important;
  margin-bottom:var(--kyre-space-3)!important;
  padding-bottom:var(--kyre-space-2)!important;
  border-bottom:1px solid var(--kyre-sem-border-soft)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projname,
.st-key-kyre_passing_yards_shell_v1 .kpy8-name,
.st-key-kyre_passing_yards_shell_v1 .kpy9-name,
.st-key-kyre_passing_yards_shell_v1 .kpy10-name{
  color:var(--kyre-sem-text-primary)!important;
  font-size:.72rem!important;
  line-height:1.25!important;
  font-weight:950!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projsub,
.st-key-kyre_passing_yards_shell_v1 .kpy8-sub,
.st-key-kyre_passing_yards_shell_v1 .kpy9-sub,
.st-key-kyre_passing_yards_shell_v1 .kpy10-sub{
  margin-top:var(--kyre-space-1)!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.48rem!important;
  line-height:1.45!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projgrade,
.st-key-kyre_passing_yards_shell_v1 .kpy8-grade,
.st-key-kyre_passing_yards_shell_v1 .kpy9-grade,
.st-key-kyre_passing_yards_shell_v1 .kpy10-grade{
  flex:0 0 auto!important;
  padding:4px 7px!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-radius-pill)!important;
  background:var(--kyre-sem-accent-wash-soft)!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-size:.43rem!important;
  font-weight:950!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy-projhero,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy8-hero,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy9-hero{
  display:grid!important;
  grid-template-columns:1fr!important;
  gap:var(--kyre-space-2)!important;
  margin-bottom:var(--kyre-space-2)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-market .kpy10-hero{
  gap:var(--kyre-space-2)!important;
  margin-bottom:var(--kyre-space-2)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero > div,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero > div,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero > div,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero > div{
  padding:var(--kyre-space-3)!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-surface-column)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero b,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero b,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero b,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero b{
  color:var(--kyre-sem-text-primary)!important;
  font-size:.96rem!important;
  font-weight:950!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projhero span,
.st-key-kyre_passing_yards_shell_v1 .kpy8-hero span,
.st-key-kyre_passing_yards_shell_v1 .kpy9-hero span,
.st-key-kyre_passing_yards_shell_v1 .kpy10-hero span{
  color:var(--kyre-sem-text-muted)!important;
  font-size:.44rem!important;
  font-weight:850!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy-projmeta,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy8-meta{
  display:grid!important;
  grid-template-columns:1fr!important;
  gap:var(--kyre-space-2)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy9-q{
  display:grid!important;
  grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:var(--kyre-space-2)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-market .kpy10-metrics{
  gap:var(--kyre-space-2)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projmeta > div,
.st-key-kyre_passing_yards_shell_v1 .kpy8-meta > div,
.st-key-kyre_passing_yards_shell_v1 .kpy9-q > div,
.st-key-kyre_passing_yards_shell_v1 .kpy10-metrics > div{
  padding:var(--kyre-space-2)!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:var(--kyre-sem-surface-column)!important;
  color:var(--kyre-sem-text-secondary)!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projmeta b,
.st-key-kyre_passing_yards_shell_v1 .kpy8-meta b,
.st-key-kyre_passing_yards_shell_v1 .kpy9-q b,
.st-key-kyre_passing_yards_shell_v1 .kpy10-metrics b{
  color:var(--kyre-sem-text-primary)!important;
  font-weight:900!important;
}
.st-key-kyre_passing_yards_shell_v1 .kpy-projctx,
.st-key-kyre_passing_yards_shell_v1 .kpy8-note,
.st-key-kyre_passing_yards_shell_v1 .kpy9-note,
.st-key-kyre_passing_yards_shell_v1 .kpy10-note{
  margin-top:var(--kyre-space-3)!important;
  padding-top:var(--kyre-space-3)!important;
  border-top:1px solid var(--kyre-sem-border-soft)!important;
  color:var(--kyre-sem-text-secondary)!important;
  font-size:.48rem!important;
  line-height:1.55!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support details{
  padding:var(--kyre-space-3)!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-control)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-control),var(--kyre-sem-surface-panel))!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support summary{
  color:var(--kyre-sem-text-accent)!important;
  font-size:.62rem!important;
  font-weight:900!important;
}
@media(max-width:680px){
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-step{
    padding:var(--kyre-space-3)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-step .kpy9-q,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-market .kpy10-metrics,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-market .kpy10-hero{
    grid-template-columns:1fr!important;
  }
}
</style>
"""

def build_passing_yards_analysis_css() -> str:
    return build_semantic_tokens_css() + _ANALYSIS_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_analysis_css(), unsafe_allow_html=True)
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
