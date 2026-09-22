"""NFL Passing Yards V61 — QB drill-down premium card system Step 4.

Additive presentation-only wrapper over frozen V60. Step 4 unifies the existing
V58 quarterback picker cards and V59 dedicated-QB analysis card under one
premium semantic card language. It changes only visual hierarchy and responsive
presentation. Frozen navigation, identity, data, projection, probability,
market math, sportsbook influence, widget keys, and Step 1–3 behavior remain
unchanged.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v60 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V61 • QB DRILL-DOWN STEP 4 PREMIUM CARDS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v60"
DRILLDOWN_STEP = 4
CARD_SYSTEM_VERSION = "v61"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_CARD_CSS = r"""
<style data-passing-yards-step4-card-system="v61">
.ks-py58-head,
.ks-py59-head{
  position:relative;
  overflow:hidden;
  border-color:var(--kyre-sem-border-medium)!important;
  background:
    radial-gradient(circle at 100% 0%,var(--kyre-sem-accent-wash),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.ks-py58-head:before,
.ks-py59-head:before{
  content:"";
  position:absolute;
  left:0;right:0;top:0;height:3px;
  background:linear-gradient(90deg,var(--kyre-sem-text-accent),var(--kyre-sem-accent-wash),transparent);
  pointer-events:none;
}
.ks-py58-grid{gap:var(--kyre-space-4)!important}
.ks-py58-card,
.ks-py59-player{
  position:relative;
  min-width:0;
  overflow:hidden;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-card)!important;
  background:
    radial-gradient(circle at 100% 0%,var(--kyre-sem-accent-wash-soft),transparent 30%),
    linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.ks-py58-card:before,
.ks-py59-player:before{
  content:"";
  position:absolute;
  left:0;right:0;top:0;height:4px;
  background:linear-gradient(90deg,var(--kyre-sem-text-accent),rgba(88,201,255,.32),transparent);
  pointer-events:none;
}
.ks-py58-slot,
.ks-py59-kicker{
  color:var(--kyre-sem-text-accent-soft)!important;
  letter-spacing:.10em!important;
}
.ks-py58-identity,
.ks-py59-identity{
  min-width:0;
  padding:var(--kyre-space-3)!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:var(--kyre-sem-surface-column)!important;
}
.ks-py58-identity{margin-bottom:0!important}
.ks-py59-identity{margin-bottom:var(--kyre-space-4)!important}
.ks-py58-cta,
.ks-py59-back{
  border-color:var(--kyre-sem-border-strong)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-accent-wash),var(--kyre-sem-accent-wash-soft))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035)!important;
}
.ks-py58-cardlink:focus-visible{
  outline:2px solid var(--kyre-sem-text-accent);
  outline-offset:3px;
  border-radius:var(--kyre-sem-radius-card);
}
.ks-py59-section,
.ks-py59-support details{
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.018)!important;
}
.ks-py59-section[data-qb-analysis-section="market"]{
  border-color:var(--kyre-sem-border-medium)!important;
  background:
    radial-gradient(circle at 100% 0%,var(--kyre-sem-accent-wash-soft),transparent 40%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
}
.ks-py59-section>strong,
.ks-py59-support summary{
  color:var(--kyre-sem-text-accent-soft)!important;
}
@media(max-width:900px){
  .ks-py58-grid,
  .ks-py59-evidence,
  .ks-py59-support{grid-template-columns:1fr!important}
}
@media(max-width:680px){
  .ks-py58-card,
  .ks-py59-player{
    border-radius:var(--kyre-sem-radius-section)!important;
    padding:var(--kyre-space-3)!important;
  }
  .ks-py58-identity,
  .ks-py59-identity,
  .ks-py59-section,
  .ks-py59-support details{
    padding:var(--kyre-space-3)!important;
  }
}
</style>
"""

def build_passing_yards_step4_card_css() -> str:
    return build_semantic_tokens_css() + _CARD_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_step4_card_css(), unsafe_allow_html=True)
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V61 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "CARD_SYSTEM_VERSION",
    "DISPLAY_ONLY",
    "DRILLDOWN_STEP",
    "FROZEN_PRIOR",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "build_passing_yards_step4_card_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
