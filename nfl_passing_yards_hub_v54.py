"""NFL Passing Yards V54 — universal game/player cards Step 4.

Presentation-only wrapper over frozen V53. This layer unifies the existing
Passing Yards matchup/QB card surfaces under the current universal semantic
token system. It changes visual hierarchy only; all frozen identity, data,
projection, probability, market, sportsbook, widget, and stake behavior
continues to come from V53 -> V52 and the certified legacy pipeline.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v53 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V54 • UNIVERSAL GAME PLAYER CARDS STEP 4"
FROZEN_PRIOR = "nfl_passing_yards_hub_v53"
VISUAL_UPGRADE_STEP = 4
CARD_SYSTEM_VERSION = "v54"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_CARD_CSS = r"""
<style data-passing-yards-card-system="v54">
.st-key-kyre_passing_yards_shell_v1 .ks-py47-head,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-head{
  margin-bottom:var(--kyre-space-4)!important;
  padding:var(--kyre-space-4) var(--kyre-space-5)!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-card)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-grid,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-grid{
  gap:var(--kyre-space-4)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-player,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-player{
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
.st-key-kyre_passing_yards_shell_v1 .ks-py47-accent,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-accent{
  height:4px!important;
  background:linear-gradient(90deg,var(--kyre-sem-text-accent),var(--kyre-sem-accent-wash),transparent)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-playerhead,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-playerhead{
  min-height:54px;
  padding:var(--kyre-space-3) var(--kyre-space-4)!important;
  border-bottom:1px solid var(--kyre-sem-border-soft)!important;
  background:linear-gradient(90deg,var(--kyre-sem-accent-wash-soft),transparent)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-playerhead b,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-playerhead b{
  color:var(--kyre-sem-text-accent-soft)!important;
  font-weight:950!important;
  letter-spacing:.09em!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-body,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-body{
  padding:var(--kyre-space-4)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-identity,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-identity{
  margin:0 0 var(--kyre-space-3)!important;
  padding:var(--kyre-space-3)!important;
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:var(--kyre-sem-radius-section);
  background:var(--kyre-sem-surface-column);
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-primary{
  gap:var(--kyre-space-3)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-tile,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-market{
  padding:var(--kyre-space-4)!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt))!important;
  box-shadow:var(--kyre-sem-shadow-card)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-tile strong,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-market strong{
  color:var(--kyre-sem-text-accent-soft)!important;
  letter-spacing:.08em!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-evidence,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-evidence,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support{
  gap:var(--kyre-space-3)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-detail,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support details{
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:var(--kyre-sem-radius-section)!important;
  background:
    linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt))!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-detail,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step{
  padding:var(--kyre-space-3)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-step[data-step="7"]{
  border-color:var(--kyre-sem-border-strong)!important;
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py48-stepnum{
  background:var(--kyre-sem-accent-wash)!important;
  color:var(--kyre-sem-text-accent)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47-detail summary,
.st-key-kyre_passing_yards_shell_v1 .ks-py48-support summary{
  color:var(--kyre-sem-text-accent)!important;
}
@media(max-width:900px){
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-grid,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-grid{
    grid-template-columns:1fr!important;
  }
}
@media(max-width:620px){
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-head,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-head,
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-body,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-body{
    padding:var(--kyre-space-3)!important;
  }
  .st-key-kyre_passing_yards_shell_v1 .ks-py47-player,
  .st-key-kyre_passing_yards_shell_v1 .ks-py48-player{
    border-radius:var(--kyre-sem-radius-section)!important;
  }
}
</style>
"""

def build_passing_yards_card_css() -> str:
    return build_semantic_tokens_css() + _CARD_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_card_css(), unsafe_allow_html=True)
    st.markdown(
        '<span data-passing-yards-card-owner="v54" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V54 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "CARD_SYSTEM_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_card_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
