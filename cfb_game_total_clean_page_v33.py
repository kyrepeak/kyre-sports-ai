"""CFB Game Total clean page V33 — dropdown category routing Step 3.

Additive successor to V32. Preserves the Step-2 dropdown presentation while
turning every frozen real category row into a same-app link. Category values
remain the exact Step-1 contract values.
"""
from __future__ import annotations

from html import escape
from urllib.parse import quote_plus

import streamlit as st

import cfb_game_total_clean_page_v28 as frozen_page
import cfb_game_total_clean_page_v29 as shell
import cfb_game_total_clean_page_v30 as functional
import cfb_game_total_clean_page_v31 as responsive
import cfb_game_total_clean_page_v32 as dropdown

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V33 • SPORT DROPDOWN STEP 3 FUNCTIONAL"
MARKET = frozen_page.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v32"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • SPORT DROPDOWN STEP 3 FUNCTIONAL ACTIVE"
SPORT_DROPDOWN_STEP3_MARKER = "CFB_GAME_TOTAL_SPORT_DROPDOWN_STEP3_FUNCTIONAL_ACTIVE"
SPORT_JUMP_QUERY_KEY = functional.SPORT_JUMP_QUERY_KEY
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
SPORT_CATEGORIES = dropdown.SPORT_CATEGORIES
SPORT_META = dropdown.SPORT_META

SPORT_DROPDOWN_STEP3_CSS = r"""
<style>
.gt233-category{
  text-decoration:none!important;
  color:#c6d8e3!important;
  cursor:pointer;
  transition:border-color .14s ease,background .14s ease,transform .14s ease;
}
.gt233-category:hover{
  transform:translateY(-1px);
  border-color:rgba(84,181,228,.44);
  background:rgba(10,41,61,.92);
}
.gt233-category:focus-visible{
  outline:2px solid rgba(69,240,173,.72);
  outline-offset:2px;
}
.gt232-sport.cfb .gt233-category{
  color:#d5f8ea!important;
}
.gt232-sport.cfb .gt233-category:hover{
  border-color:rgba(69,240,173,.46);
  background:rgba(15,70,50,.72);
}
.gt233-category:after{
  content:"›"!important;
  color:#7ea0b4!important;
  font-size:15px;
  font-weight:950;
}
.gt232-sport.cfb .gt233-category:after{
  color:#62efbd!important;
}
@media(max-width:560px){
  .gt233-category:hover{transform:none}
}
</style>
"""


def _sport_href(code: str) -> str:
    return functional._sport_href(code)


def _category_href(code: str, category: str) -> str:
    return (
        f"?{SPORT_JUMP_QUERY_KEY}={quote_plus(code)}"
        f"&{MARKET_JUMP_QUERY_KEY}={quote_plus(category)}"
    )


def _category_rows(code: str) -> str:
    return "".join(
        (
            f'<a class="gt232-category gt233-category" '
            f'data-category="{escape(category)}" '
            f'data-category-sport="{code}" '
            f'href="{_category_href(code, category)}" target="_self">'
            f'{escape(category)}</a>'
        )
        for category in SPORT_CATEGORIES[code]
    )


def _sport_panel(code: str) -> str:
    css_class, icon, subtitle = SPORT_META[code]
    selected = code == "CFB"
    selected_attrs = ' data-selected="true" aria-current="page"' if selected else ""
    active = '<span class="gt229-active">Current</span>' if selected else ""
    open_attr = " open" if selected else ""
    categories = SPORT_CATEGORIES[code]

    return f"""
<div class="gt232-sport {css_class}" data-dropdown-sport="{code}">
  <a class="gt229-card {css_class}" data-sport="{code}" href="{_sport_href(code)}"
     target="_self"{selected_attrs}>{active}
    <div class="gt229-icon">{icon}</div>
    <div class="gt229-bottom">
      <div class="gt229-copy"><strong>{code}</strong><small>{escape(subtitle)}</small></div>
      <span class="gt229-arrow">›</span>
    </div>
  </a>
  <details class="gt232-dropdown" data-dropdown="{code}"{open_attr}>
    <summary>
      <span>Categories</span>
      <span class="gt232-count">{len(categories)} existing pages</span>
    </summary>
    <div class="gt232-list">
      {_category_rows(code)}
    </div>
  </details>
</div>
"""


def _sport_dropdown_nav_html() -> str:
    panels = "".join(_sport_panel(code) for code in ("NFL", "CFB", "MLB", "WNBA"))
    return f"""
<div class="gt229-sportnav"
     data-testid="gt233-sport-dropdown-nav"
     data-step3-marker="{SPORT_DROPDOWN_STEP3_MARKER}">
  <div class="gt229-head">
    <div class="gt229-title">
      <b>Jump to a <em>Sport Page</em></b>
      <span>Pick a sport, then tap any existing Streamlit category.</span>
    </div>
    <div class="gt229-brand">
      <b>KYRE SPORTS AI</b>
      <span>REAL PAGES. ONE TAP AWAY.</span>
    </div>
  </div>
  <div class="gt232-grid" aria-label="Sport page navigation with functional category dropdowns">
    {panels}
  </div>
</div>
"""


def render_step6_cert_surface() -> None:
    return frozen_page.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(
        shell.SPORT_NAV_SHELL_CSS
        + functional.SPORT_NAV_STEP2_CSS
        + responsive.SPORT_NAV_STEP3_CSS
        + dropdown.SPORT_DROPDOWN_STEP2_CSS
        + SPORT_DROPDOWN_STEP3_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(_sport_dropdown_nav_html(), unsafe_allow_html=True)
    return frozen_page.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V33 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_CATEGORIES",
    "SPORT_DROPDOWN_STEP3_CSS",
    "SPORT_DROPDOWN_STEP3_MARKER",
    "SPORT_JUMP_QUERY_KEY",
    "_category_href",
    "_category_rows",
    "_sport_dropdown_nav_html",
    "_sport_href",
    "_sport_panel",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
