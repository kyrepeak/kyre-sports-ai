"""CFB Game Total clean page V32 — dropdown category UI Step 2.

Presentation-only successor to V31. Preserves the frozen sport-card links and
responsive polish while adding expandable category lists made only from the
Step-1 frozen existing Streamlit category contract. Category rows are visual
only in Step 2; category routing is intentionally deferred to Step 3.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import cfb_game_total_clean_page_v28 as frozen_page
import cfb_game_total_clean_page_v29 as shell
import cfb_game_total_clean_page_v30 as functional
import cfb_game_total_clean_page_v31 as responsive

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V32 • SPORT DROPDOWN STEP 2 UI"
MARKET = frozen_page.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v31"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • SPORT DROPDOWN STEP 2 UI ACTIVE"
SPORT_DROPDOWN_STEP2_MARKER = "CFB_GAME_TOTAL_SPORT_DROPDOWN_STEP2_UI_ACTIVE"
SPORT_JUMP_QUERY_KEY = functional.SPORT_JUMP_QUERY_KEY

SPORT_CATEGORIES = {
    "NFL": (
        "Slate",
        "Moneyline",
        "Spread",
        "Game Total",
        "Passing Yards",
        "Rushing Yards",
        "Receiving Yards",
        "Receptions",
        "Passing TDs",
        "Anytime TD",
        "Daily Picks",
    ),
    "CFB": (
        "Moneyline",
        "Over/Under",
        "Game Total",
    ),
    "MLB": (
        "Slate",
        "1+ Hit",
        "2+ Hits",
        "Home Run",
        "Hits + Runs + RBIs",
        "Pitcher Strikeouts",
        "Matchup Explorer",
        "Daily Game Picks",
        "Moneyline",
        "Run Line",
        "Game Total",
        "Live Game",
    ),
    "WNBA": (
        "Points",
        "Rebounds",
        "Assists",
        "Rebounds + Assists",
        "PRA",
        "Spread",
        "Moneyline",
        "Game Total",
        "Daily Picks",
    ),
}

SPORT_META = {
    "NFL": ("nfl", "🏈", "Pro Football"),
    "CFB": ("cfb", "🏈", "College Football"),
    "MLB": ("mlb", "⚾", "Baseball"),
    "WNBA": ("wnba", "🏀", "Women's Basketball"),
}

SPORT_DROPDOWN_STEP2_CSS = r"""
<style>
.gt232-grid{
  position:relative;
  z-index:1;
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
  align-items:start;
}
.gt232-sport{
  min-width:0;
  border-radius:16px;
}
.gt232-sport .gt229-card{
  min-height:112px;
}
.gt232-dropdown{
  margin-top:7px;
  border:1px solid rgba(90,151,188,.24);
  border-radius:13px;
  overflow:hidden;
  background:linear-gradient(145deg,rgba(7,23,36,.98),rgba(8,18,31,.98));
}
.gt232-dropdown[open]{
  box-shadow:0 10px 24px rgba(0,0,0,.18);
}
.gt232-sport.cfb .gt232-dropdown{
  border-color:rgba(69,240,173,.44);
  box-shadow:0 0 20px rgba(69,240,173,.08);
}
.gt232-dropdown summary{
  min-height:42px;
  padding:10px 11px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  cursor:pointer;
  list-style:none;
  color:#b9cfdd;
  font-size:8px;
  font-weight:950;
  letter-spacing:.08em;
  text-transform:uppercase;
  user-select:none;
}
.gt232-dropdown summary::-webkit-details-marker{display:none}
.gt232-dropdown summary:after{
  content:"⌄";
  color:#9cb5c5;
  font-size:16px;
  line-height:1;
  transform:rotate(0deg);
  transition:transform .16s ease;
}
.gt232-dropdown[open] summary:after{
  transform:rotate(180deg);
}
.gt232-sport.cfb .gt232-dropdown summary{
  color:#65efbd;
  background:rgba(29,126,85,.10);
}
.gt232-count{
  color:#708d9f;
  font-size:7px;
  letter-spacing:.04em;
}
.gt232-list{
  display:grid;
  gap:6px;
  padding:0 8px 9px;
}
.gt232-category{
  min-height:39px;
  padding:8px 9px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  border:1px solid rgba(77,137,172,.20);
  border-radius:10px;
  background:rgba(7,28,43,.80);
  color:#c6d8e3;
  font-size:8px;
  font-weight:850;
  line-height:1.25;
}
.gt232-category:after{
  content:"•";
  color:#55788d;
  flex:0 0 auto;
}
.gt232-sport.cfb .gt232-category{
  border-color:rgba(69,240,173,.22);
  background:rgba(15,56,43,.58);
  color:#d5f8ea;
}
.gt232-note{
  padding:0 9px 9px;
  color:#58778a;
  font-size:6.5px;
  font-weight:750;
  line-height:1.4;
}
@media(max-width:760px){
  .gt232-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:10px;
  }
}
@media(max-width:560px){
  .gt232-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:8px;
  }
  .gt232-dropdown summary{min-height:44px}
  .gt232-category{min-height:42px}
}
@media(max-width:360px){
  .gt232-grid{grid-template-columns:1fr}
}
</style>
"""


def _sport_href(code: str) -> str:
    return functional._sport_href(code)


def _category_rows(code: str) -> str:
    return "".join(
        f'<div class="gt232-category" data-category="{escape(category)}">{escape(category)}</div>'
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
     target="_self"{selected_attrs}>
    {active}
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
    <div class="gt232-note">Existing Streamlit categories • route wiring comes in Step 3</div>
  </details>
</div>
"""


def _sport_dropdown_nav_html() -> str:
    panels = "".join(_sport_panel(code) for code in ("NFL", "CFB", "MLB", "WNBA"))
    return f"""
<div class="gt229-sportnav"
     data-testid="gt232-sport-dropdown-nav"
     data-step2-marker="{SPORT_DROPDOWN_STEP2_MARKER}">
  <div class="gt229-head">
    <div class="gt229-title">
      <b>Jump to a <em>Sport Page</em></b>
      <span>Pick a sport, then open its existing Streamlit categories.</span>
    </div>
    <div class="gt229-brand">
      <b>KYRE SPORTS AI</b>
      <span>REAL PAGES. ONE TAP AWAY.</span>
    </div>
  </div>
  <div class="gt232-grid" aria-label="Sport page navigation with category dropdowns">
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
        + SPORT_DROPDOWN_STEP2_CSS,
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
        raise ValueError(f"Page V32 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_CATEGORIES",
    "SPORT_DROPDOWN_STEP2_CSS",
    "SPORT_DROPDOWN_STEP2_MARKER",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_META",
    "_category_rows",
    "_sport_dropdown_nav_html",
    "_sport_href",
    "_sport_panel",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
