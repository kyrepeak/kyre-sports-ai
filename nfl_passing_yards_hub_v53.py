"""NFL Passing Yards V53 — universal page shell Step 3.

Presentation-only wrapper over frozen V52. This layer owns the visible Passing
Yards page frame: hero, page width, shell surface, and top-level spacing. It
consumes the frozen semantic token layer and leaves all Passing Yards data,
identity, projection, probability, market, sportsbook, widget, and stake logic
unchanged.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v52 as prior
from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css

MODEL_VERSION = "NFL PASSING YARDS V53 • UNIVERSAL PAGE SHELL STEP 3"
FROZEN_PRIOR = "nfl_passing_yards_hub_v52"
VISUAL_UPGRADE_STEP = 3
SHELL_VERSION = "v53"
SHELL_CONTAINER_KEY = "kyre_passing_yards_shell_v1"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_SHELL_CSS = r"""
<style data-passing-yards-page-shell="v53">
.st-key-kyre_passing_yards_shell_v1{
  box-sizing:border-box;
  width:100%;
  max-width:1400px;
  margin:0 auto var(--kyre-space-6);
  padding:var(--kyre-space-5);
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:var(--kyre-radius-2xl);
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash),transparent 34%),
    linear-gradient(180deg,var(--kyre-sem-surface-panel-alt),var(--kyre-bg-0));
  box-shadow:var(--kyre-shadow-float),var(--kyre-sem-shadow-glow);
  color:var(--kyre-sem-text-primary);
  overflow:hidden;
}
.st-key-kyre_passing_yards_shell_v1 > [data-testid="stVerticalBlock"]{
  gap:var(--kyre-space-4);
}
.ks-py53-hero{
  box-sizing:border-box;
  position:relative;
  overflow:hidden;
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:var(--kyre-space-5);
  width:100%;
  margin:0 0 var(--kyre-space-2);
  padding:var(--kyre-space-6);
  border:1px solid var(--kyre-sem-border-strong);
  border-radius:var(--kyre-radius-xl);
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash),transparent 36%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow);
}
.ks-py53-hero-copy{min-width:0;max-width:860px}
.ks-py53-kicker{
  margin:0 0 var(--kyre-space-2);
  color:var(--kyre-sem-text-accent);
  font-size:var(--kyre-font-xs);
  font-weight:950;
  letter-spacing:.14em;
  text-transform:uppercase;
}
.ks-py53-title{
  margin:0;
  color:var(--kyre-sem-text-primary);
  font-size:var(--kyre-font-display);
  line-height:.98;
  font-weight:950;
  letter-spacing:-.045em;
}
.ks-py53-sub{
  max-width:760px;
  margin:var(--kyre-space-3) 0 0;
  color:var(--kyre-sem-text-secondary);
  font-size:var(--kyre-font-sm);
  line-height:1.55;
}
.ks-py53-status{
  flex:0 0 auto;
  display:flex;
  align-items:center;
  gap:var(--kyre-space-2);
  flex-wrap:wrap;
  justify-content:flex-end;
}
.ks-py53-chip{
  display:inline-flex;
  align-items:center;
  min-height:34px;
  padding:0 var(--kyre-space-3);
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-radius-pill);
  background:var(--kyre-sem-surface-control);
  color:var(--kyre-sem-text-accent-soft);
  font-size:var(--kyre-font-xs);
  font-weight:850;
  white-space:nowrap;
}
.ks-py53-chip.live{
  color:var(--kyre-success);
  border-color:var(--kyre-success);
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_universal_owner_v1{
  width:100%;
  max-width:none;
  margin:0;
}
.st-key-kyre_passing_yards_shell_v1 .st-key-kyre_passing_yards_top_v46{
  margin-top:var(--kyre-space-2)!important;
  margin-bottom:var(--kyre-space-3)!important;
}
.st-key-kyre_passing_yards_shell_v1 .ks-py47,
.st-key-kyre_passing_yards_shell_v1 .ks-py48{
  margin-top:var(--kyre-space-3)!important;
  margin-bottom:var(--kyre-space-4)!important;
}
.st-key-kyre_passing_yards_shell_v1 [data-testid="stExpander"],
.st-key-kyre_passing_yards_shell_v1 [data-testid="stDataFrame"],
.st-key-kyre_passing_yards_shell_v1 [data-testid="stTable"]{
  margin-top:var(--kyre-space-2);
  margin-bottom:var(--kyre-space-2);
}
@media(max-width:900px){
  .st-key-kyre_passing_yards_shell_v1{
    padding:var(--kyre-space-4);
    border-radius:var(--kyre-radius-xl);
  }
  .ks-py53-hero{
    flex-direction:column;
    padding:var(--kyre-space-5);
  }
  .ks-py53-status{justify-content:flex-start}
}
@media(max-width:620px){
  .st-key-kyre_passing_yards_shell_v1{
    padding:var(--kyre-space-3);
    border-radius:var(--kyre-radius-lg);
  }
  .ks-py53-hero{
    padding:var(--kyre-space-4);
    border-radius:var(--kyre-radius-lg);
  }
  .ks-py53-title{font-size:2rem}
  .ks-py53-status{width:100%}
  .ks-py53-chip{min-height:32px}
}
</style>
"""

_HERO_HTML = """
<section class="ks-py53-hero" data-passing-yards-shell-hero="v53">
  <div class="ks-py53-hero-copy">
    <div class="ks-py53-kicker">NFL PLAYER PROPS • PASSING YARDS</div>
    <h1 class="ks-py53-title">Passing Yards</h1>
    <p class="ks-py53-sub">
      Quarterback projections, matchup context, evidence, and market intelligence
      inside one clean universal analysis workspace.
    </p>
  </div>
  <div class="ks-py53-status" aria-label="Passing Yards page status">
    <span class="ks-py53-chip live">● LIVE DATA</span>
    <span class="ks-py53-chip">MODEL FROZEN</span>
    <span class="ks-py53-chip">UNIVERSAL SHELL</span>
  </div>
</section>
"""

def build_passing_yards_shell_css() -> str:
    return build_semantic_tokens_css() + _SHELL_CSS

def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_shell_css(), unsafe_allow_html=True)
    with st.container(key=SHELL_CONTAINER_KEY):
        st.markdown(
            '<span data-passing-yards-shell-owner="v53" '
            'style="display:none" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        st.markdown(_HERO_HTML, unsafe_allow_html=True)
        return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V53 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SHELL_CONTAINER_KEY",
    "SHELL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_shell_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
