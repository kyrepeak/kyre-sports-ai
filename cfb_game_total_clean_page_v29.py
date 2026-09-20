"""CFB Game Total clean page V29 — sport navigation Step 1 shell.

Presentation-only successor to V28. Adds the visual "Jump to a Sport Page"
shell above GAME DAY. No navigation actions are wired in Step 1; routing,
data, model, market, and all frozen Game Total surfaces remain delegated.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v28 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V29 • SPORT NAV STEP 1 SHELL"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v28"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • SPORT NAV STEP 1 SHELL ACTIVE"
SPORT_NAV_STEP1_MARKER = "CFB_GAME_TOTAL_SPORT_NAV_STEP1_SHELL_ACTIVE"

SPORT_NAV_SHELL_CSS = r"""
<style>
.gt229-sportnav{
  position:relative;
  margin:0 0 18px;
  padding:18px;
  border:1px solid rgba(67,167,206,.24);
  border-radius:22px;
  overflow:hidden;
  color:#f8fbff;
  background:
    radial-gradient(circle at 8% 8%,rgba(23,215,255,.12),transparent 28%),
    radial-gradient(circle at 88% 10%,rgba(119,90,255,.12),transparent 30%),
    linear-gradient(145deg,#06131f 0%,#071827 48%,#081328 100%);
  box-shadow:0 16px 40px rgba(0,0,0,.18),0 0 26px rgba(39,216,208,.045);
}
.gt229-sportnav:before{
  content:"";
  position:absolute;
  inset:0;
  pointer-events:none;
  opacity:.35;
  background:
    linear-gradient(115deg,transparent 0 46%,rgba(255,255,255,.035) 47%,transparent 48%),
    linear-gradient(90deg,rgba(39,216,208,.08),transparent 22%,transparent 78%,rgba(169,104,255,.08));
}
.gt229-head{
  position:relative;
  z-index:1;
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:16px;
  margin-bottom:15px;
}
.gt229-title{
  min-width:0;
}
.gt229-title b{
  display:block;
  color:#f7fbff;
  font-size:25px;
  line-height:1.05;
  font-weight:1000;
  letter-spacing:-.025em;
}
.gt229-title b em{
  font-style:normal;
  color:#48efc1;
  text-shadow:0 0 16px rgba(72,239,193,.16);
}
.gt229-title span{
  display:block;
  margin-top:6px;
  color:#8da7b9;
  font-size:10px;
  font-weight:750;
}
.gt229-brand{
  flex:0 0 auto;
  text-align:right;
}
.gt229-brand b{
  display:block;
  color:#bfe8ff;
  font-size:12px;
  font-weight:850;
  letter-spacing:.22em;
}
.gt229-brand span{
  display:block;
  margin-top:5px;
  color:#45f0ad;
  font-size:7px;
  font-weight:950;
  letter-spacing:.18em;
}
.gt229-grid{
  position:relative;
  z-index:1;
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
}
.gt229-card{
  position:relative;
  min-height:112px;
  padding:13px;
  border:1px solid rgba(100,154,190,.26);
  border-radius:16px;
  overflow:hidden;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
  background:linear-gradient(145deg,#0a1a28,#0b1725);
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.01);
}
.gt229-card:after{
  content:"";
  position:absolute;
  inset:0;
  pointer-events:none;
  background:radial-gradient(circle at 75% 10%,rgba(255,255,255,.07),transparent 28%);
}
.gt229-card.nfl{
  border-color:rgba(255,156,58,.50);
  background:linear-gradient(145deg,#251710,#1e1112 70%,#18131a);
  box-shadow:0 0 20px rgba(255,139,45,.08),inset 0 0 24px rgba(255,139,45,.035);
}
.gt229-card.cfb{
  border-color:rgba(69,240,173,.74);
  background:linear-gradient(145deg,#08231b,#09231d 62%,#071b21);
  box-shadow:0 0 0 2px rgba(69,240,173,.12),0 0 24px rgba(69,240,173,.15);
}
.gt229-card.mlb{
  border-color:rgba(77,151,255,.62);
  background:linear-gradient(145deg,#08192b,#0b1730 70%,#0a1427);
  box-shadow:0 0 20px rgba(77,151,255,.08),inset 0 0 24px rgba(77,151,255,.03);
}
.gt229-card.wnba{
  border-color:rgba(255,121,64,.56);
  background:linear-gradient(145deg,#24130f,#211016 70%,#17121c);
  box-shadow:0 0 20px rgba(255,112,61,.07),inset 0 0 24px rgba(255,112,61,.03);
}
.gt229-icon{
  position:relative;
  z-index:1;
  width:39px;
  height:39px;
  display:grid;
  place-items:center;
  border-radius:12px;
  border:1px solid rgba(255,255,255,.08);
  background:rgba(255,255,255,.035);
  font-size:22px;
}
.gt229-card.cfb .gt229-icon{
  border-color:rgba(69,240,173,.30);
  background:rgba(69,240,173,.08);
}
.gt229-bottom{
  position:relative;
  z-index:1;
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:8px;
}
.gt229-copy strong{
  display:block;
  color:#fff;
  font-size:22px;
  line-height:1;
  font-weight:1000;
  letter-spacing:-.015em;
}
.gt229-copy small{
  display:block;
  margin-top:5px;
  color:#a0b2bf;
  font-size:7px;
  font-weight:950;
  letter-spacing:.09em;
  text-transform:uppercase;
}
.gt229-card.cfb .gt229-copy small{
  color:#59efbd;
}
.gt229-arrow{
  color:#e8f4fb;
  font-size:25px;
  font-weight:900;
  line-height:1;
}
.gt229-active{
  position:absolute;
  top:10px;
  right:10px;
  z-index:2;
  padding:4px 7px;
  border-radius:999px;
  border:1px solid rgba(69,240,173,.34);
  background:rgba(24,111,76,.18);
  color:#56f1bd;
  font-size:6px;
  font-weight:1000;
  letter-spacing:.10em;
  text-transform:uppercase;
}
@media(max-width:760px){
  .gt229-sportnav{padding:14px;border-radius:18px}
  .gt229-title b{font-size:21px}
  .gt229-grid{gap:8px}
  .gt229-card{min-height:100px;padding:11px;border-radius:14px}
  .gt229-copy strong{font-size:18px}
  .gt229-brand b{font-size:10px}
}
@media(max-width:560px){
  .gt229-head{display:block}
  .gt229-brand{display:none}
  .gt229-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
</style>
"""


def _sport_nav_shell_html() -> str:
    return f"""
<div class="gt229-sportnav"
     data-testid="gt229-sport-nav-shell"
     data-step1-marker="{SPORT_NAV_STEP1_MARKER}">
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
  <div class="gt229-grid" aria-label="Sport page navigation preview">
    <div class="gt229-card nfl" data-sport="NFL">
      <div class="gt229-icon">🏈</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>NFL</strong><small>Pro Football</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </div>
    <div class="gt229-card cfb" data-sport="CFB" data-selected="true">
      <span class="gt229-active">Current</span>
      <div class="gt229-icon">🏈</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>CFB</strong><small>College Football</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </div>
    <div class="gt229-card mlb" data-sport="MLB">
      <div class="gt229-icon">⚾</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>MLB</strong><small>Baseball</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </div>
    <div class="gt229-card wnba" data-sport="WNBA">
      <div class="gt229-icon">🏀</div>
      <div class="gt229-bottom">
        <div class="gt229-copy"><strong>WNBA</strong><small>Women's Basketball</small></div>
        <span class="gt229-arrow">›</span>
      </div>
    </div>
  </div>
</div>
"""


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(SPORT_NAV_SHELL_CSS, unsafe_allow_html=True)
    st.markdown(_sport_nav_shell_html(), unsafe_allow_html=True)
    return prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V29 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_NAV_SHELL_CSS",
    "SPORT_NAV_STEP1_MARKER",
    "_sport_nav_shell_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
