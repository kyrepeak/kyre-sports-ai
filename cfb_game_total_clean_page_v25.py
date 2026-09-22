"""CFB Game Total clean page V25 — visual redesign Step 2 matchup hero.

Presentation-only successor to V24. The certified data/model/runtime contracts
remain frozen. V25 replaces only the matchup hero renderer while delegating all
data reconciliation, Game Total analysis, Team Evidence, and Steps 1-12 to V24.
"""
from __future__ import annotations

from html import escape
from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v10 as presentation_owner
import cfb_game_total_clean_page_v24 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V25 • VISUAL REDESIGN STEP 2 MATCHUP HERO"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v24"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • VISUAL REDESIGN STEP 2 MATCHUP HERO ACTIVE"
STEP2_MATCHUP_HERO_MARKER = "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP2_MATCHUP_HERO_ACTIVE"

_PRESENTATION_LOCK = RLock()


STEP2_MATCHUP_HERO_CSS = r"""
<style>
.gt225-hero{
  position:relative;
  margin:0 auto 14px;
  border:1px solid rgba(42,226,221,.72);
  border-left:3px solid #27d8d0;
  border-right:2px solid rgba(169,104,255,.92);
  border-radius:22px;
  overflow:hidden;
  color:#f7fbff;
  background:
    radial-gradient(circle at 50% 20%,rgba(35,142,190,.15),transparent 30%),
    radial-gradient(circle at 8% 0%,rgba(39,216,208,.10),transparent 34%),
    radial-gradient(circle at 96% 0%,rgba(169,104,255,.11),transparent 34%),
    linear-gradient(115deg,#061c2a 0%,#071824 54%,#0b1227 100%);
  box-shadow:
    0 0 34px rgba(39,216,208,.10),
    0 18px 42px rgba(0,0,0,.24);
}
.gt225-hero:before{
  content:"";
  position:absolute;
  inset:0;
  pointer-events:none;
  opacity:.28;
  background:
    linear-gradient(90deg,transparent 49.7%,rgba(87,193,224,.16) 50%,transparent 50.3%),
    repeating-linear-gradient(90deg,transparent 0 11%,rgba(75,165,198,.055) 11.1% 11.25%);
  mask-image:linear-gradient(to bottom,transparent 0,black 18%,black 72%,transparent 88%);
}
.gt225-topline{
  position:relative;
  z-index:1;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  padding:15px 20px 7px;
  color:#a8c3d8;
  font-size:11px;
  font-weight:900;
  letter-spacing:.09em;
  text-transform:uppercase;
}
.gt225-topline .analysis{
  color:#dda0ff;
  text-shadow:0 0 14px rgba(169,104,255,.30);
}
.gt225-stage{
  position:relative;
  z-index:1;
  display:grid;
  grid-template-columns:minmax(0,1fr) 76px minmax(0,1fr);
  align-items:center;
  gap:14px;
  padding:10px 34px 22px;
  min-height:124px;
}
.gt225-team{
  display:flex;
  align-items:center;
  gap:18px;
  min-width:0;
}
.gt225-team.home{
  justify-content:flex-end;
  text-align:right;
}
.gt225-team-logo{
  width:88px;
  height:88px;
  flex:0 0 88px;
  display:grid;
  place-items:center;
  border-radius:24px;
  background:radial-gradient(circle at center,rgba(255,255,255,.055),transparent 67%);
}
.gt225-team-logo img,
.gt225-team-logo .gt159-logo,
.gt225-team-logo .gt159-logo-fallback{
  width:82px!important;
  height:82px!important;
  max-width:82px!important;
  object-fit:contain;
  filter:drop-shadow(0 10px 18px rgba(0,0,0,.38));
}
.gt225-team-logo .gt159-logo-fallback{
  display:grid;
  place-items:center;
  border:1px solid rgba(102,184,224,.24);
  border-radius:18px;
  background:#10293a;
  color:#9bd7ff;
  font-size:22px;
  font-weight:950;
}
.gt225-teamcopy{min-width:0}
.gt225-name{
  color:#fbfdff;
  font-size:24px;
  line-height:1.02;
  font-weight:1000;
  letter-spacing:-.02em;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.gt225-record{
  margin-top:7px;
  color:#9eb5c8;
  font-size:13px;
  font-weight:760;
}
.gt225-conf{
  display:inline-flex;
  align-items:center;
  margin-top:8px;
  padding:4px 11px;
  border:1px solid rgba(66,189,237,.38);
  border-radius:999px;
  background:rgba(17,111,160,.17);
  color:#70d4ff;
  font-size:10px;
  font-weight:900;
  letter-spacing:.04em;
  text-transform:lowercase;
}
.gt225-vs{
  width:56px;
  height:56px;
  margin:auto;
  display:grid;
  place-items:center;
  border:1px solid rgba(83,176,216,.38);
  border-radius:50%;
  background:
    radial-gradient(circle at 50% 35%,rgba(80,184,223,.11),transparent 55%),
    #092333;
  color:#b8cede;
  font-size:11px;
  font-weight:1000;
  letter-spacing:.08em;
  box-shadow:
    0 0 0 7px rgba(5,18,28,.38),
    0 0 22px rgba(54,177,218,.11);
}
.gt225-facts{
  position:relative;
  z-index:1;
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  border-top:1px solid rgba(75,157,195,.25);
  background:rgba(3,13,22,.45);
}
.gt225-fact{
  min-width:0;
  min-height:66px;
  display:grid;
  grid-template-columns:27px minmax(0,1fr);
  grid-template-rows:auto auto;
  column-gap:9px;
  align-content:center;
  padding:11px 16px;
  box-sizing:border-box;
  border-right:1px solid rgba(76,146,179,.17);
}
.gt225-fact:last-child{border-right:0}
.gt225-fact .icon{
  grid-row:1 / span 2;
  align-self:center;
  display:grid;
  place-items:center;
  width:24px;
  height:24px;
  color:#a9d9ef;
  font-size:17px;
  font-weight:900;
}
.gt225-fact.weather .icon{color:#ffd24d}
.gt225-fact.wind .icon{color:#56b7ff}
.gt225-fact.time .icon{color:#c9d9e7}
.gt225-fact b{
  min-width:0;
  color:#f3f8fc;
  font-size:12px;
  line-height:1.2;
  font-weight:900;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.gt225-fact span:not(.icon){
  min-width:0;
  margin-top:4px;
  color:#7f99ad;
  font-size:10px;
  line-height:1.25;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
@media (max-width:760px){
  .gt225-hero{border-radius:18px}
  .gt225-topline{padding:12px 13px 5px;font-size:9px}
  .gt225-stage{grid-template-columns:minmax(0,1fr) 48px minmax(0,1fr);gap:7px;padding:8px 12px 16px;min-height:104px}
  .gt225-team{gap:9px}.gt225-team-logo{width:58px;height:58px;flex-basis:58px;border-radius:17px}
  .gt225-team-logo img,.gt225-team-logo .gt159-logo,.gt225-team-logo .gt159-logo-fallback{width:54px!important;height:54px!important;max-width:54px!important}
  .gt225-name{font-size:17px}.gt225-record{margin-top:4px;font-size:10px}.gt225-conf{margin-top:5px;padding:3px 8px;font-size:8px}
  .gt225-vs{width:39px;height:39px;font-size:8px;box-shadow:0 0 0 4px rgba(5,18,28,.34)}
  .gt225-fact{min-height:58px;grid-template-columns:21px minmax(0,1fr);column-gap:6px;padding:9px 7px}
  .gt225-fact .icon{width:19px;height:19px;font-size:13px}.gt225-fact b{font-size:9px}.gt225-fact span:not(.icon){font-size:8px}
}
@media (max-width:520px){
  .gt225-stage{grid-template-columns:1fr 34px 1fr;padding-left:7px;padding-right:7px}
  .gt225-team{gap:6px}.gt225-team-logo{width:43px;height:43px;flex-basis:43px}
  .gt225-team-logo img,.gt225-team-logo .gt159-logo,.gt225-team-logo .gt159-logo-fallback{width:40px!important;height:40px!important;max-width:40px!important}
  .gt225-name{font-size:14px}.gt225-record{font-size:8px}.gt225-conf{font-size:7px;padding:2px 6px}
  .gt225-vs{width:31px;height:31px}
  .gt225-facts{grid-template-columns:repeat(2,minmax(0,1fr))}
  .gt225-fact:nth-child(2){border-right:0}.gt225-fact:nth-child(-n+2){border-bottom:1px solid rgba(76,146,179,.17)}
}
</style>
"""


def _clean(value: Any) -> str:
    return presentation_owner._clean(value)


def _logo(identity: Mapping[str, Any]) -> str:
    return presentation_owner.prior._logo(identity)


def _matchup_header_html_v25(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
) -> str:
    away_id, home_id = identity.get("away") or {}, identity.get("home") or {}
    away_name = _clean(away_id.get("team")) or _clean(away.get("team")) or "Away"
    home_name = _clean(home_id.get("team")) or _clean(home.get("team")) or "Home"
    away_conf = _clean(away_id.get("conference")) or "NCAAF"
    home_conf = _clean(home_id.get("conference")) or "NCAAF"
    away_record = _clean(away.get("record")) or "—"
    home_record = _clean(home.get("record")) or "—"
    kickoff = _clean(identity.get("kickoff")) or _clean(display_game.get("kickoff")) or "Kickoff unavailable"
    venue = _clean(identity.get("venue")) or _clean(display_game.get("venue")) or "Venue unavailable"
    venue_sub = _clean(
        display_game.get("venue_location")
        or display_game.get("location")
        or display_game.get("city")
    ) or "Venue"
    weather = _clean(display_game.get("weather") or display_game.get("forecast")) or "Weather unavailable"
    temp = _clean(display_game.get("temperature"))
    wind = _clean(display_game.get("wind") or display_game.get("wind_mph")) or "Wind unavailable"
    date_text = presentation_owner._pretty_date(display_game)
    topline = " • ".join(part for part in ("NCAAF", date_text, kickoff) if part)
    kickoff_sub = date_text or "Kickoff"
    temp_display = (temp + "°") if temp else "—"

    return f"""
<div class="gt225-hero" data-testid="gt225-matchup-hero"
     data-step2-presentation="{STEP2_MATCHUP_HERO_MARKER}">
  <div class="gt225-topline">
    <span>{escape(topline)}</span>
    <span class="analysis">GAME TOTAL ANALYSIS</span>
  </div>
  <div class="gt225-stage">
    <div class="gt225-team away">
      <div class="gt225-team-logo">{_logo(away_id)}</div>
      <div class="gt225-teamcopy">
        <div class="gt225-name">{escape(away_name)}</div>
        <div class="gt225-record">{escape(away_record)} ({escape(away_conf)})</div>
        <span class="gt225-conf">{escape(away_conf)}</span>
      </div>
    </div>
    <div class="gt225-vs">VS</div>
    <div class="gt225-team home">
      <div class="gt225-teamcopy">
        <div class="gt225-name">{escape(home_name)}</div>
        <div class="gt225-record">{escape(home_record)} ({escape(home_conf)})</div>
        <span class="gt225-conf">{escape(home_conf)}</span>
      </div>
      <div class="gt225-team-logo">{_logo(home_id)}</div>
    </div>
  </div>
  <div class="gt225-facts">
    <div class="gt225-fact venue"><span class="icon">▣</span><b>{escape(venue)}</b><span>{escape(venue_sub)}</span></div>
    <div class="gt225-fact weather"><span class="icon">☀</span><b>{escape(temp_display)}</b><span>{escape(weather)}</span></div>
    <div class="gt225-fact wind"><span class="icon">≋</span><b>{escape(wind)}</b><span>Wind</span></div>
    <div class="gt225-fact time"><span class="icon">▦</span><b>{escape(kickoff)}</b><span>{escape(kickoff_sub)}</span></div>
  </div>
</div>"""


def _render_with_step2_matchup_hero(callback, *args, **kwargs):
    with _PRESENTATION_LOCK:
        original = presentation_owner._target_matchup_header_html
        presentation_owner._target_matchup_header_html = _matchup_header_html_v25
        try:
            return callback(*args, **kwargs)
        finally:
            presentation_owner._target_matchup_header_html = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP2_MATCHUP_HERO_CSS, unsafe_allow_html=True)
    result = _render_with_step2_matchup_hero(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP2_MATCHUP_HERO_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V25 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_MATCHUP_HERO_CSS",
    "STEP2_MATCHUP_HERO_MARKER",
    "_matchup_header_html_v25",
    "_render_with_step2_matchup_hero",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
