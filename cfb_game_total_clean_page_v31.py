"""CFB Game Total clean page V31 — sport navigation Step 3 responsive polish.

CSS-only successor to V30. Keeps all Step 2 navigation behavior frozen while
improving the sport navigation shell across desktop, tablet, and small mobile
widths. GAME DAY and every downstream Game Total surface remain delegated.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v30 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V31 • SPORT NAV STEP 3 RESPONSIVE POLISH"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v30"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • SPORT NAV STEP 3 RESPONSIVE POLISH ACTIVE"
SPORT_NAV_STEP3_MARKER = "CFB_GAME_TOTAL_SPORT_NAV_STEP3_RESPONSIVE_POLISH_ACTIVE"

SPORT_NAV_STEP3_CSS = r"""
<style>
/* Wide desktop/tablet target: preserve the approved four-card strip. */
.gt229-sportnav{
  width:100%;
  box-sizing:border-box;
}
.gt229-grid{
  align-items:stretch;
}
.gt229-card{
  min-width:0;
  min-height:116px;
  box-sizing:border-box;
  touch-action:manipulation;
  -webkit-tap-highlight-color:transparent;
}
.gt229-copy{
  min-width:0;
}
.gt229-copy strong,
.gt229-copy small{
  overflow-wrap:anywhere;
}
.gt229-copy small{
  line-height:1.25;
}
.gt229-icon{
  flex:0 0 auto;
}
.gt229-arrow{
  flex:0 0 auto;
}

/* Small tablets / large phones: roomy 2x2 instead of cramped 4-across. */
@media(max-width:760px){
  .gt229-sportnav{
    padding:14px!important;
  }
  .gt229-head{
    margin-bottom:13px!important;
  }
  .gt229-grid{
    grid-template-columns:repeat(2,minmax(0,1fr))!important;
    gap:10px!important;
  }
  .gt229-card{
    min-height:112px!important;
    padding:13px!important;
  }
  .gt229-title b{
    font-size:21px!important;
  }
  .gt229-title span{
    max-width:520px;
    font-size:9px!important;
    line-height:1.45;
  }
  .gt229-copy strong{
    font-size:20px!important;
  }
  .gt229-copy small{
    font-size:7px!important;
    letter-spacing:.075em!important;
  }
  .gt229-icon{
    width:38px!important;
    height:38px!important;
    font-size:21px!important;
  }
}

/* Phone portrait: keep 2 columns, increase tap comfort and readability. */
@media(max-width:560px){
  .gt229-sportnav{
    margin-bottom:14px!important;
    padding:12px!important;
  }
  .gt229-head{
    display:block!important;
  }
  .gt229-brand{
    display:none!important;
  }
  .gt229-grid{
    grid-template-columns:repeat(2,minmax(0,1fr))!important;
    gap:8px!important;
  }
  .gt229-card{
    min-height:104px!important;
    padding:11px!important;
    border-radius:14px!important;
  }
  .gt229-title b{
    font-size:19px!important;
  }
  .gt229-title span{
    margin-top:5px!important;
    font-size:8px!important;
  }
  .gt229-copy strong{
    font-size:18px!important;
  }
  .gt229-copy small{
    font-size:6.5px!important;
  }
  .gt229-icon{
    width:34px!important;
    height:34px!important;
    font-size:19px!important;
  }
  .gt229-arrow{
    font-size:22px!important;
  }
  .gt229-active{
    top:8px!important;
    right:8px!important;
  }
}

/* Very narrow devices: stack to prevent clipped labels and tiny tap targets. */
@media(max-width:360px){
  .gt229-grid{
    grid-template-columns:1fr!important;
  }
  .gt229-card{
    min-height:92px!important;
  }
  .gt229-bottom{
    align-items:center!important;
  }
}
</style>
"""


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Re-emit after the frozen V30 page so these overrides own the final cascade.
    result = prior.render_game_total_hub(section_header, status_info, team_logo, h)
    st.markdown(SPORT_NAV_STEP3_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V31 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_NAV_STEP3_CSS",
    "SPORT_NAV_STEP3_MARKER",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
