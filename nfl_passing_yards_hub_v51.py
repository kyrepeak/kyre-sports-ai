"""NFL Passing Yards V51 — universal theme ownership Step 1.

Presentation-only wrapper over frozen V50. This layer establishes one explicit
page-level universal theme owner around the current Passing Yards production
surface. It consumes the shared KYRE theme/component/responsive builders and
skins the existing frozen controls/cards in place. No routing outside Passing
Yards, data, identity, projection, probability, market, sportsbook, widget-key,
or stake behavior changes.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v50 as prior
from kyre_universal_components_v1 import build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V51 • UNIVERSAL THEME OWNER STEP 1"
FROZEN_PRIOR = "nfl_passing_yards_hub_v50"
VISUAL_UPGRADE_STEP = 1
UNIVERSAL_OWNER_VERSION = "v51"
OWNER_CONTAINER_KEY = "kyre_passing_yards_universal_owner_v1"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_OWNER_CSS = r"""
<style data-passing-yards-universal-owner="v51">
.st-key-kyre_passing_yards_universal_owner_v1{
  min-width:0;
  max-width:100%;
  color:var(--kyre-text-primary);
}
.st-key-kyre_passing_yards_universal_owner_v1::before{
  content:"NFL PASSING YARDS  •  UNIVERSAL THEME";
  display:block;
  margin:.05rem 0 .58rem;
  color:var(--kyre-glacier);
  font-size:.58rem;
  font-weight:950;
  letter-spacing:.12em;
  text-transform:uppercase;
}
.st-key-kyre_passing_yards_universal_owner_v1 h1,
.st-key-kyre_passing_yards_universal_owner_v1 h2,
.st-key-kyre_passing_yards_universal_owner_v1 h3,
.st-key-kyre_passing_yards_universal_owner_v1 h4{
  color:var(--kyre-text-primary)!important;
  letter-spacing:-.025em;
}
.st-key-kyre_passing_yards_universal_owner_v1 p,
.st-key-kyre_passing_yards_universal_owner_v1 label,
.st-key-kyre_passing_yards_universal_owner_v1 small{
  color:var(--kyre-text-secondary);
}

/* Step 1 top controls now inherit the shared black + glacier surface. */
.st-key-kyre_passing_yards_universal_owner_v1 .st-key-kyre_passing_yards_top_v46{
  border:1px solid rgba(88,201,255,.24)!important;
  border-radius:var(--kyre-radius-xl)!important;
  background:
    radial-gradient(circle at 92% 0%,rgba(88,201,255,.11),transparent 30%),
    linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface))!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 .st-key-kyre_passing_yards_top_v46 label{
  color:var(--kyre-glacier-soft)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1
  .st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
.st-key-kyre_passing_yards_universal_owner_v1
  .st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div{
  background:#08131d!important;
  border-color:rgba(88,201,255,.24)!important;
  color:var(--kyre-text-primary)!important;
  border-radius:var(--kyre-radius-md)!important;
}

/* Current frozen command/evidence cards: theme ownership, not recomposition. */
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py47-head,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-head{
  border-color:rgba(88,201,255,.24)!important;
  background:
    radial-gradient(circle at 92% 0%,rgba(88,201,255,.10),transparent 30%),
    linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface))!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py47-player,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-player{
  border-color:rgba(88,201,255,.20)!important;
  background:linear-gradient(150deg,var(--kyre-surface-raised),#07121c)!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py47-tile,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-market,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-step,
.st-key-kyre_passing_yards_universal_owner_v1 .ks-py48-support details{
  border-color:rgba(88,201,255,.16)!important;
  background:linear-gradient(145deg,#07121c,#091823)!important;
}

/* Frozen Step 10 native market controls inherit the same component language. */
.st-key-kyre_passing_yards_universal_owner_v1
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"]){
  border-color:rgba(88,201,255,.24)!important;
  background:
    radial-gradient(circle at 92% 0%,rgba(88,201,255,.09),transparent 28%),
    linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface))!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1
  [data-testid="stHorizontalBlock"]:has(input[aria-label="Sportsbook / source"])
  > [data-testid="stColumn"]{
  border-color:rgba(88,201,255,.15)!important;
  background:rgba(3,10,16,.50)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 [data-testid="stMetric"],
.st-key-kyre_passing_yards_universal_owner_v1 [data-testid="stExpander"]{
  border-color:rgba(88,201,255,.16)!important;
  border-radius:var(--kyre-radius-lg)!important;
  background:linear-gradient(145deg,var(--kyre-surface),#08111a)!important;
}
.st-key-kyre_passing_yards_universal_owner_v1 [data-testid="stDataFrame"],
.st-key-kyre_passing_yards_universal_owner_v1 [data-testid="stTable"]{
  border:1px solid rgba(88,201,255,.14);
  border-radius:var(--kyre-radius-lg);
  overflow:hidden;
  box-shadow:var(--kyre-shadow-card);
}
@media(max-width:720px){
  .st-key-kyre_passing_yards_universal_owner_v1::before{
    margin-bottom:.42rem;
    font-size:.52rem;
  }
}
</style>
"""


def build_passing_yards_universal_owner_css() -> str:
    """Compose the shared universal system plus Passing Yards ownership skin."""
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _OWNER_CSS
    )


def render_nfl_passing_yards_hub() -> None:
    st.markdown(build_passing_yards_universal_owner_css(), unsafe_allow_html=True)
    with st.container(key=OWNER_CONTAINER_KEY):
        st.markdown(
            '<span data-passing-yards-theme-owner="v51" '
            'style="display:none" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V51 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "OWNER_CONTAINER_KEY",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "UNIVERSAL_OWNER_VERSION",
    "VISUAL_UPGRADE_STEP",
    "build_passing_yards_universal_owner_css",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
