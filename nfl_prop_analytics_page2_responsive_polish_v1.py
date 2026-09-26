"""NFL Prop Analytics Page 2 Polish Step 5 — responsive presentation polish.

Presentation-only responsive layer for the frozen Page 2 stack. It changes no
schedule, roster, availability, eligibility, filtering, player handoff, prop
page, router, or Passing Yards truth.
"""
from __future__ import annotations

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 2 POLISH STEP 5 • RESPONSIVE PRODUCTION POLISH"
STEP = 5
PAGE = 2
PRESENTATION_ONLY = True
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False
RESPONSIVE_TARGETS = (390, 768, 1440)


def render_page2_responsive_polish() -> None:
    """Inject final Page 2 responsive CSS without changing frozen data contracts."""
    st.markdown(
        """
<div data-prop-page2-responsive-polish="v1"
     data-prop-page2-responsive-targets="390,768,1440"
     data-prop-page2-responsive-overflow="protected"></div>
<style data-prop-page2-responsive-polish-css="v1">
/* Final Page 2 composition guardrails. */
[data-nfl-prop-analytics-step4-page2="v1"],
[data-prop-page2-premium-header="v1"],
[data-nfl-prop-analytics-page2-unified-roster="v1"],
[data-prop-page2-tap-player="v1"]{
  width:100%;
  max-width:100%;
  min-width:0;
  box-sizing:border-box;
  overflow-x:clip;
}

/* Keep the Page 2 Streamlit controls compact and touch friendly. */
div[data-testid="stSegmentedControl"]{
  max-width:100%;
  overflow-x:auto;
  scrollbar-width:none;
}
div[data-testid="stSegmentedControl"]::-webkit-scrollbar{display:none}
div[data-testid="stButton"] button,
button[data-testid^="stBaseButton"]{
  min-height:44px !important;
  border-radius:12px;
  white-space:normal;
  line-height:1.2;
  text-align:left;
}

/* iPad / compact desktop: keep both teams side-by-side, simplify inner cards. */
@media (max-width:900px){
  .ks-pa-u-list{grid-template-columns:1fr !important}
  .ks-pa-u-player{padding:10px !important}
  .ks-pa-u-name strong{font-size:.72rem !important}
  .ks-pa-u-name span,.ks-pa-u-depth{font-size:.57rem !important}
  .ks-pa-u-bottom{gap:5px !important}
}

/* Phone / compact Streamlit frame: stack tap controls reliably. */
@media (max-width:760px){
  div[data-testid="stHorizontalBlock"]{
    flex-direction:column !important;
    gap:.45rem !important;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    width:100% !important;
    min-width:100% !important;
    flex:1 1 100% !important;
  }
  div[data-testid="stButton"] button,
  button[data-testid^="stBaseButton"],
  body div[data-testid="stHorizontalBlock"] button{
    min-height:48px !important;
    width:100% !important;
    padding:.65rem .8rem !important;
  }
}

/* Phone: one team column and tighter chrome. */
@media (max-width:640px){
  [data-testid="stMainBlockContainer"]{
    padding-left:.72rem !important;
    padding-right:.72rem !important;
  }
  .ks-pa-u-board{
    margin-top:9px !important;
    padding:12px 10px !important;
    border-radius:15px !important;
  }
  .ks-pa-u-grid{grid-template-columns:1fr !important}
  .ks-pa-u-top{
    align-items:flex-start !important;
    flex-direction:column !important;
    gap:7px !important;
  }
  .ks-pa-u-proof{
    align-items:flex-start !important;
    text-align:left !important;
    max-width:none !important;
  }
  .ks-pa-u-team{padding:10px !important}
  .ks-pa-u-list{grid-template-columns:1fr !important}
  .ks-pa-u-main{gap:5px !important}
  .ks-pa-u-bottom{align-items:flex-start !important;flex-direction:column !important}
  .ks-pa-u-state{text-align:left !important}

  body div[data-testid="stHorizontalBlock"]{
    display:grid !important;
    grid-template-columns:minmax(0,1fr) !important;
    gap:.45rem !important;
  }
  body div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]{
    width:100% !important;
    min-width:100% !important;
    flex:1 1 100% !important;
  }
  div[data-testid="stButton"] button{
    min-height:48px;
    width:100%;
    padding:.65rem .8rem;
  }
  .ks-pa4-tap{padding:10px 11px !important}
}

/* Very narrow phone hard-stop against accidental overflow. */
@media (max-width:420px){
  [data-testid="stMainBlockContainer"]{
    padding-left:.55rem !important;
    padding-right:.55rem !important;
  }
  .ks-pa-u-team-head{
    align-items:flex-start !important;
    flex-direction:column !important;
    gap:2px !important;
  }
  .ks-pa-u-verified{white-space:normal !important}
}
</style>
""",
        unsafe_allow_html=True,
    )


__all__ = [
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PRESENTATION_ONLY",
    "RESPONSIVE_TARGETS",
    "STEP",
    "render_page2_responsive_polish",
]
