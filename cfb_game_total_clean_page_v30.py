"""CFB Game Total clean page V30 — sport navigation Step 2 functional cards.

Additive successor to V29. Preserves the approved Step 1 visual shell while
making each sport card a real same-app navigation link. Game Day and all frozen
Game Total surfaces remain delegated to V28.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v29 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V30 • SPORT NAV STEP 2 FUNCTIONAL"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v29"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • SPORT NAV STEP 2 FUNCTIONAL ACTIVE"
SPORT_NAV_STEP2_MARKER = "CFB_GAME_TOTAL_SPORT_NAV_STEP2_FUNCTIONAL_ACTIVE"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"

SPORT_NAV_STEP2_CSS = r"""
<style>
.gt229-card{
  text-decoration:none!important;
  color:inherit!important;
  cursor:pointer;
  transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease,filter .16s ease;
}
.gt229-card:hover{
  transform:translateY(-2px);
  filter:brightness(1.06);
}
.gt229-card:focus-visible{
  outline:2px solid rgba(69,240,173,.75);
  outline-offset:3px;
}
.gt229-card.nfl:hover{box-shadow:0 0 28px rgba(255,139,45,.16),inset 0 0 24px rgba(255,139,45,.05)}
.gt229-card.cfb:hover{box-shadow:0 0 0 2px rgba(69,240,173,.16),0 0 30px rgba(69,240,173,.22)}
.gt229-card.mlb:hover{box-shadow:0 0 28px rgba(77,151,255,.16),inset 0 0 24px rgba(77,151,255,.05)}
.gt229-card.wnba:hover{box-shadow:0 0 28px rgba(255,112,61,.14),inset 0 0 24px rgba(255,112,61,.05)}
@media(max-width:560px){
  .gt229-card:hover{transform:none}
}
</style>
"""


def _sport_href(code: str) -> str:
    return f"?{SPORT_JUMP_QUERY_KEY}={code}"


def _sport_nav_html() -> str:
    return f"""
<div class="gt229-sportnav"
     data-testid="gt230-sport-nav"
     data-step2-marker="{SPORT_NAV_STEP2_MARKER}">
  <div class="gt229-head">
    <div class="gt229-title">
      <b>Jump to a <em>Sport Page</em></b>
      <span>Tap a sport to explore game totals, model projections, and more.</span>
    </div>
    <div class="gt229-brand">
      <b>KYRE SPORTS AI</b>
      <span>MORE DATA. BIGGER PLAYS.</span>
    </div>
  </div>
  <div class="gt229-grid" aria-label="Sport page navigation">
    <a class="gt229-card nfl" data-sport="NFL" href="{_sport_href("NFL")}" target="_self">
      <div class="gt229-icon">🏈</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>NFL</strong><small>Pro Football</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </a>
    <a class="gt229-card cfb" data-sport="CFB" data-selected="true"
       href="{_sport_href("CFB")}" target="_self" aria-current="page">
      <span class="gt229-active">Current</span>
      <div class="gt229-icon">🏈</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>CFB</strong><small>College Football</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </a>
    <a class="gt229-card mlb" data-sport="MLB" href="{_sport_href("MLB")}" target="_self">
      <div class="gt229-icon">⚾</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>MLB</strong><small>Baseball</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </a>
    <a class="gt229-card wnba" data-sport="WNBA" href="{_sport_href("WNBA")}" target="_self">
      <div class="gt229-icon">🏀</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>WNBA</strong><small>Women's Basketball</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </a>
  </div>
</div>
"""


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(prior.SPORT_NAV_SHELL_CSS + SPORT_NAV_STEP2_CSS, unsafe_allow_html=True)
    st.markdown(_sport_nav_html(), unsafe_allow_html=True)
    # Delegate directly to V28 so the non-interactive V29 shell is not duplicated.
    return prior.prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V30 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_NAV_STEP2_CSS",
    "SPORT_NAV_STEP2_MARKER",
    "_sport_href",
    "_sport_nav_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
