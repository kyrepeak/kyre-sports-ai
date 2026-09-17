"""CFB Game Total Clean Page V10 — V160 exact Monster target surface.

Presentation-only successor to frozen V159. V160 reuses V9's entire Game Total
schedule, evidence, model, distribution, qualification, and Top-5 flow while
owning the visible Monster Sports Intelligence surface. No projection,
probability, qualification, ranking, API, or sportsbook-influence behavior is
changed.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v9 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V10 • V160 EXACT MONSTER TARGET"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v9"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE"
BRAND_MARKER = "MONSTER SPORTS INTELLIGENCE"
V160_REQUIRED_MARKERS = (
    ACTIVE_MARKER,
    BRAND_MARKER,
    "GAME TOTAL ANALYSIS",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)

# V159 remains the data/model owner. V160 is only the visual layer. The target
# is intentionally sized around the real 1067x1536 iPad capture supplied for
# acceptance, while retaining compact two-column evidence at smaller widths.
_V160_OVERRIDES = r"""
:root{--gt160-green:#45f0ad;--gt160-teal:#27d8d0;--gt160-blue:#56b7ff;--gt160-purple:#a968ff;--gt160-amber:#ffd24d;--gt160-red:#ff705b;--gt160-text:#f7fbff;--gt160-muted:#8fa7bd}
html,body,[data-testid="stAppViewContainer"],.stApp{background:#01070d!important}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 18% 0%,rgba(0,232,190,.045),transparent 29%),radial-gradient(circle at 88% 10%,rgba(141,64,255,.05),transparent 31%),#01070d!important}
[data-testid="stHeader"],[data-testid="stDecoration"],[data-testid="stToolbar"]{display:none!important}
.block-container{max-width:900px!important;padding:0 0 28px!important;margin:0 auto!important}

.gt160-masthead{max-width:900px;height:64px;box-sizing:border-box;margin:0 auto 10px;padding:10px 18px;display:flex;align-items:center;justify-content:space-between;gap:18px;border-bottom:1px solid rgba(70,145,183,.22);background:linear-gradient(90deg,#06182a,#071426 58%,#071123);box-shadow:0 12px 30px rgba(0,0,0,.32)}
.gt160-brand{display:flex;align-items:center;gap:11px;min-width:260px}.gt160-mark{width:42px;height:38px;display:grid;place-items:center;background:linear-gradient(145deg,#55f1b5,#19bcad);color:#03231f;font-size:0;font-weight:1000;clip-path:polygon(0 0,50% 36%,100% 0,100% 100%,0 100%)}.gt160-mark:before{content:"M";font-size:18px;color:#073d36}.gt160-brandcopy b{display:block;color:#f8fbff;font-size:20px;line-height:1;font-weight:1000;letter-spacing:.035em}.gt160-brandcopy span{display:block;margin-top:4px;color:#a6c5df;font-size:10px;font-weight:850;letter-spacing:.115em}
.gt160-nav{display:flex;align-items:center;justify-content:center;gap:27px;flex:1}.gt160-nav span{color:#a6b5c4;font-size:13px;font-weight:900;letter-spacing:.055em}.gt160-nav .active{color:var(--gt160-green);position:relative}.gt160-nav .active:after{content:"";position:absolute;left:-4px;right:-4px;bottom:-12px;height:2px;border-radius:999px;background:var(--gt160-green);box-shadow:0 0 9px rgba(69,240,173,.75)}.gt160-actions{display:flex;align-items:center;gap:10px;color:#f0f7fc;font-size:19px}.gt160-actions span{width:34px;height:34px;display:grid;place-items:center;border-left:1px solid rgba(113,161,191,.18)}
.gt160-identity{display:none!important}

.gt159-shell{max-width:900px!important;margin:0 auto!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
.gt159-top{border:1px solid rgba(50,205,220,.66)!important;border-left:3px solid var(--gt160-teal)!important;border-right:2px solid rgba(169,104,255,.82)!important;border-radius:15px!important;background:linear-gradient(112deg,#071d2b,#071824 58%,#0c1126)!important;box-shadow:0 0 24px rgba(39,216,208,.09)!important;overflow:hidden}
.gt159-topline{padding:11px 15px 4px!important;color:#a9bed0!important;font-size:12px!important;letter-spacing:.09em!important}.gt159-topline span:first-child{color:#a9c4d7!important}.gt159-topline span:last-child{color:#cb8fff!important;font-weight:950!important}
.gt159-matchup{grid-template-columns:1fr 56px 1fr!important;gap:12px!important;padding:13px 24px 18px!important}.gt159-team{gap:13px!important}.gt159-logo,.gt159-logo-fallback{width:72px!important;height:72px!important;flex-basis:72px!important}.gt159-logo{filter:drop-shadow(0 6px 14px rgba(0,0,0,.38))}.gt159-logo-fallback{border-radius:16px!important;background:#10293a!important;font-size:22px!important}.gt159-name{font-size:18px!important;letter-spacing:0!important}.gt159-record{font-size:13px!important;color:#a8b9c8!important;margin-top:3px!important}.gt159-conf{margin-top:6px!important;padding:3px 10px!important;font-size:10px!important;background:rgba(26,126,177,.16)!important;border-color:rgba(64,188,235,.34)!important;color:#71d4ff!important}.gt159-vs{width:48px!important;height:48px!important;background:#0b2233!important;border-color:rgba(86,151,187,.34)!important;box-shadow:0 0 0 5px rgba(5,17,26,.38)!important;font-size:11px!important}
.gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr))!important;background:rgba(4,14,22,.46)!important;border-top:1px solid rgba(60,149,193,.23)!important}.gt159-fact{position:relative;padding:11px 10px 10px 39px!important;min-height:52px;box-sizing:border-box}.gt159-fact:before{position:absolute;left:13px;top:13px;color:#a8d8f4;font-size:18px;line-height:1}.gt159-fact:nth-child(1):before{content:"▣"}.gt159-fact:nth-child(2):before{content:"☀";color:var(--gt160-amber)}.gt159-fact:nth-child(3):before{content:"≋";color:#9bd7ff}.gt159-fact:nth-child(4):before{content:"▦";color:#c6d9ea}.gt159-fact b{font-size:12px!important;line-height:1.2!important}.gt159-fact span{font-size:10px!important;margin-top:3px!important}

.gt159-total{margin-top:12px!important;padding:13px 14px 12px!important;border:1px solid rgba(69,240,173,.52)!important;border-left:3px solid var(--gt160-green)!important;border-right:2px solid rgba(169,104,255,.82)!important;border-radius:15px!important;background:linear-gradient(132deg,rgba(6,35,40,.98),rgba(6,18,31,.99) 61%,rgba(15,15,38,.99))!important;box-shadow:0 0 30px rgba(69,240,173,.07),0 10px 28px rgba(0,0,0,.18)!important}
.gt159-totalhead{color:#b2ead5!important;font-size:12px!important;letter-spacing:.10em!important}.gt159-cert{padding:5px 11px!important;background:rgba(18,117,78,.18)!important;border-color:rgba(69,240,173,.58)!important;color:var(--gt160-green)!important;font-size:10px!important}.gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr))!important;margin-top:11px!important}.gt159-totalmetric{position:relative;padding:8px 16px!important;min-height:84px!important;display:flex!important;flex-direction:column!important;justify-content:center!important}.gt159-totalmetric span{font-size:10px!important;letter-spacing:.055em!important}.gt159-totalmetric b{font-size:24px!important;margin-top:5px!important}.gt159-totalmetric.hero b{font-size:47px!important;line-height:.98!important}.gt159-totalmetric.lean b{font-size:18px!important;line-height:1.12!important;color:var(--gt160-green)!important}.gt159-totalmetric small{font-size:11px!important;line-height:1.25!important}.gt159-totalmetric:last-child{padding-right:76px!important}.gt159-totalmetric:last-child:after{content:"";position:absolute;right:17px;top:50%;transform:translateY(-50%);width:52px;height:52px;border-radius:50%;background:radial-gradient(circle at center,#071925 56%,transparent 58%),conic-gradient(var(--gt160-green) 0 73.3%,rgba(69,116,143,.23) 73.3% 100%);box-shadow:0 0 16px rgba(69,240,173,.28)}.gt159-grade{margin-top:6px!important;padding:3px 9px!important;font-size:10px!important}
.gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:9px!important;margin-top:10px!important}.gt159-badge{padding:10px 12px!important;border-radius:10px!important;background:rgba(8,29,43,.9)!important;border-color:rgba(81,165,210,.36)!important;font-size:11px!important;line-height:1.45!important}.gt159-badge strong{font-size:12px!important}.gt159-badge.green{background:rgba(18,103,72,.18)!important;border-color:rgba(69,240,173,.42)!important}.gt159-badge.purple{background:rgba(78,48,126,.19)!important;border-color:rgba(169,104,255,.44)!important}

.gt159-section{margin-top:12px!important;padding:12px!important;border:1px solid rgba(79,153,194,.34)!important;border-radius:14px!important;background:linear-gradient(180deg,rgba(6,23,35,.99),rgba(4,16,25,.99))!important}.gt159-sectionhead{margin-bottom:9px!important}.gt159-sectionhead b{font-size:13px!important;letter-spacing:.065em!important}.gt159-sectionhead span{font-size:10px!important;color:#8ea4b7!important}
.gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important}.gt159-teamcard{padding:11px!important;border:1px solid rgba(76,157,198,.34)!important;border-left:4px solid var(--gt160-red)!important;border-radius:11px!important;background:linear-gradient(145deg,#081d2a,#091925)!important;min-height:126px;box-sizing:border-box}.gt159-teamcard.home{border-left-color:var(--gt160-blue)!important}.gt160-teamcardtop{display:flex;align-items:center;justify-content:space-between;gap:10px}.gt160-teamid{display:flex;align-items:center;gap:10px;min-width:0}.gt160-evidence-logo,.gt160-evidence-logo-fallback{width:48px;height:48px;flex:0 0 48px;object-fit:contain}.gt160-evidence-logo-fallback{display:grid;place-items:center;border-radius:12px;background:#10293a;color:#9bd7ff;font-size:16px;font-weight:950}.gt160-teamcopy{min-width:0}.gt160-teamcopy b{display:block;color:#f3f8fc;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt160-teamcopy span{display:block;color:#98adbf;font-size:10px;margin-top:2px}.gt159-rec{padding:4px 9px!important;font-size:10px!important;background:rgba(101,64,196,.20)!important;border-color:rgba(169,104,255,.42)!important;color:#dac5ff!important}.gt159-statgrid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:7px!important;margin-top:10px!important}.gt159-stat{padding:8px 6px!important;border-radius:8px!important;background:#0b2a3a!important;border:1px solid rgba(100,168,202,.10)!important}.gt159-stat b{font-size:16px!important}.gt159-stat span{font-size:9px!important;margin-top:3px!important}

.gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important}.gt159-step{border:1px solid rgba(74,151,193,.35)!important;border-left:4px solid var(--gt160-green)!important;border-radius:10px!important;background:linear-gradient(145deg,#071b28,#081824)!important}.gt159-step.check,.gt159-step.gated{border-left-color:var(--gt160-amber)!important}.gt159-step summary{grid-template-columns:32px minmax(0,1fr) auto!important;gap:9px!important;padding:8px 9px!important;min-height:50px;box-sizing:border-box}.gt159-num{width:32px!important;height:32px!important;border-radius:9px!important;background:rgba(35,188,126,.18)!important;color:var(--gt160-green)!important;font-size:13px!important}.gt159-stepcopy b{font-size:12px!important}.gt159-stepcopy span{font-size:9px!important;line-height:1.35!important}.gt159-state{padding:4px 8px!important;font-size:9px!important;background:rgba(18,111,76,.16)!important;border-color:rgba(69,240,173,.40)!important;color:var(--gt160-green)!important}.gt159-state.check,.gt159-state.gated{background:rgba(112,81,16,.18)!important;border-color:rgba(255,210,77,.46)!important;color:var(--gt160-amber)!important}.gt159-stepbody{padding:0 9px 9px 50px!important;font-size:10px!important}.gt159-chip{font-size:9px!important}.gt159-limited{color:var(--gt160-amber)!important;font-weight:900!important}

.gt159-final{margin-top:12px!important;padding:12px!important;border:1px solid rgba(169,104,255,.50)!important;border-radius:14px!important;background:linear-gradient(140deg,#061a27,#091424 60%,#0c1126)!important}.gt159-finalhead b{color:#dfc9ff!important;font-size:13px!important}.gt159-finalhead span{font-size:10px!important;color:#97acbe!important}.gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:8px!important;margin-top:10px!important}.gt159-finalmetric{padding:12px 5px!important;border-radius:10px!important;background:#082238!important;border-color:rgba(79,155,199,.36)!important}.gt159-finalmetric b{font-size:24px!important}.gt159-finalmetric span{font-size:9px!important;margin-top:4px!important}.gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:9px!important;margin-top:10px!important}.gt159-note{padding:12px 15px!important;font-size:12px!important;line-height:1.52!important;background:linear-gradient(130deg,rgba(7,114,76,.36),rgba(5,35,31,.78))!important;border-color:rgba(69,240,173,.48)!important}.gt159-note.concern{background:linear-gradient(130deg,rgba(119,86,15,.34),rgba(35,31,16,.74))!important;border-color:rgba(255,210,77,.53)!important}.gt159-note b{font-size:12px!important;margin-bottom:5px!important}
.gt159-top5{margin-top:12px!important;padding:12px 15px!important;border:1px dashed rgba(169,104,255,.72)!important;border-radius:13px!important;background:linear-gradient(115deg,rgba(87,43,132,.23),rgba(5,19,31,.98) 72%)!important;min-height:72px;box-sizing:border-box}.gt159-top5 b{color:#d9bfff!important;font-size:14px!important}.gt159-top5 span{font-size:10px!important;margin-top:4px!important}.gt159-top5 strong{padding:8px 16px!important;border-color:rgba(169,104,255,.80)!important;color:#ead6ff!important;background:rgba(109,52,169,.22)!important;box-shadow:0 0 18px rgba(153,75,255,.19)!important;font-size:11px!important}

@media(max-width:760px){
  .block-container{max-width:100%!important;padding:0 8px 24px!important}
  .gt160-masthead{height:58px;padding:9px 11px;gap:9px}.gt160-brand{min-width:0}.gt160-mark{width:34px;height:31px}.gt160-brandcopy b{font-size:16px}.gt160-brandcopy span{font-size:8px}.gt160-nav{gap:13px}.gt160-nav span{font-size:10px}.gt160-actions{gap:4px;font-size:15px}.gt160-actions span{width:27px;height:27px}
  .gt159-matchup{grid-template-columns:1fr 42px 1fr!important;padding:10px 11px 14px!important;gap:6px!important}.gt159-logo,.gt159-logo-fallback{width:54px!important;height:54px!important;flex-basis:54px!important}.gt159-name{font-size:14px!important}.gt159-record{font-size:10px!important}.gt159-conf{font-size:8px!important}.gt159-vs{width:36px!important;height:36px!important;font-size:9px!important}
  .gt159-fact{padding:9px 5px 8px 29px!important}.gt159-fact:before{left:9px;top:11px;font-size:14px}.gt159-fact b{font-size:10px!important}.gt159-fact span{font-size:8px!important}
  .gt159-totalmetric{padding:7px 8px!important}.gt159-totalmetric.hero b{font-size:36px!important}.gt159-totalmetric b{font-size:18px!important}.gt159-totalmetric.lean b{font-size:14px!important}.gt159-totalmetric span,.gt159-totalmetric small{font-size:8px!important}.gt159-totalmetric:last-child{padding-right:52px!important}.gt159-totalmetric:last-child:after{right:8px;width:38px;height:38px}
  .gt159-badge{padding:8px!important;font-size:9px!important}.gt159-badge strong{font-size:10px!important}
  .gt160-evidence-logo,.gt160-evidence-logo-fallback{width:38px;height:38px;flex-basis:38px}.gt160-teamcopy b{font-size:11px}.gt160-teamcopy span{font-size:8px}.gt159-stat b{font-size:13px!important}.gt159-stat span{font-size:7px!important}
  .gt159-step summary{grid-template-columns:27px minmax(0,1fr) auto!important;gap:6px!important;padding:7px!important}.gt159-num{width:27px!important;height:27px!important;font-size:11px!important}.gt159-stepcopy b{font-size:10px!important}.gt159-stepcopy span{font-size:8px!important}.gt159-state{font-size:7px!important;padding:3px 5px!important}
  .gt159-finalmetric b{font-size:18px!important}.gt159-note{font-size:10px!important}.gt159-top5 b{font-size:12px!important}.gt159-top5 span,.gt159-top5 strong{font-size:9px!important}
}
@media(max-width:520px){
  .gt160-brandcopy span{display:none}.gt160-nav{gap:9px}.gt160-nav span:nth-child(3),.gt160-nav span:nth-child(4),.gt160-nav span:nth-child(5){display:none}
  .gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr))!important}.gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr))!important}.gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr))!important}.gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr))!important}.gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .gt159-sectionhead span{display:none}.gt159-totalmetric:last-child:after{display:none}.gt159-totalmetric:last-child{padding-right:4px!important}
}
"""

_V160_CSS = "<style>\n" + _V160_OVERRIDES + "\n</style>"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _pretty_date(display_game: Mapping[str, Any]) -> str:
    raw = ""
    for key in ("date", "game_date", "start_date", "start_time", "commence_time"):
        raw = _clean(display_game.get(key))
        if raw:
            break
    if not raw:
        return ""
    try:
        day = datetime.fromisoformat(raw[:10]).date()
        return f"{day.strftime('%a %b').upper()} {day.day}"
    except (TypeError, ValueError):
        return raw[:10]


def _target_matchup_header_html(
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
    kickoff = _clean(identity.get("kickoff")) or _clean(display_game.get("kickoff")) or "Kickoff unavailable"
    venue = _clean(identity.get("venue")) or _clean(display_game.get("venue")) or "Venue unavailable"
    venue_sub = _clean(display_game.get("venue_location") or display_game.get("location") or display_game.get("city")) or "Venue"
    weather = _clean(display_game.get("weather") or display_game.get("forecast")) or "Weather unavailable"
    temp = _clean(display_game.get("temperature"))
    wind = _clean(display_game.get("wind") or display_game.get("wind_mph")) or "Wind unavailable"
    date_text = _pretty_date(display_game)
    topline = " • ".join(part for part in ("NCAAF", date_text, kickoff) if part)
    kickoff_sub = date_text or "Kickoff"
    return f"""
<div class="gt159-top" data-testid="gt159-matchup-header">
  <div class="gt159-topline"><span>{escape(topline)}</span><span>GAME TOTAL ANALYSIS</span></div>
  <div class="gt159-matchup">
    <div class="gt159-team">{prior._logo(away_id)}<div class="gt159-teamcopy"><div class="gt159-name">{escape(away_name)}</div><div class="gt159-record">{escape(_clean(away.get('record')) or '—')} ({escape(away_conf)})</div><span class="gt159-conf">{escape(away_conf)}</span></div></div>
    <div class="gt159-vs">VS</div>
    <div class="gt159-team home"><div class="gt159-teamcopy"><div class="gt159-name">{escape(home_name)}</div><div class="gt159-record">{escape(_clean(home.get('record')) or '—')} ({escape(home_conf)})</div><span class="gt159-conf">{escape(home_conf)}</span></div>{prior._logo(home_id)}</div>
  </div>
  <div class="gt159-gamefacts">
    <div class="gt159-fact"><b>{escape(venue)}</b><span>{escape(venue_sub)}</span></div>
    <div class="gt159-fact"><b>{escape((temp + '°') if temp else '—')}</b><span>{escape(weather)}</span></div>
    <div class="gt159-fact"><b>{escape(wind)}</b><span>Wind</span></div>
    <div class="gt159-fact"><b>{escape(kickoff)}</b><span>{escape(kickoff_sub)}</span></div>
  </div>
</div>"""


def _team_logo(identity: Mapping[str, Any]) -> str:
    name = _clean(identity.get("team")) or "CFB"
    url = _clean(identity.get("logo"))
    if url:
        return f'<img class="gt160-evidence-logo" src="{escape(url)}" alt="{escape(name)} logo">'
    initials = "".join(part[:1] for part in name.split() if part)[:2].upper() or "CF"
    return f'<div class="gt160-evidence-logo-fallback">{escape(initials)}</div>'


def _target_team_evidence_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    def card(team_id: Mapping[str, Any], stats: Mapping[str, Any], home_side: bool = False) -> str:
        name = _clean(team_id.get("team")) or _clean(stats.get("team")) or "Team"
        record = _clean(stats.get("record")) or "—"
        conf = _clean(team_id.get("conference")) or "NCAAF"
        return f"""
<div class="gt159-teamcard {'home' if home_side else ''}">
  <div class="gt160-teamcardtop">
    <div class="gt160-teamid">{_team_logo(team_id)}<div class="gt160-teamcopy"><b>{escape(name)}</b><span>{escape(record)} ({escape(conf)})</span></div></div>
    <span class="gt159-rec">{escape(record)}</span>
  </div>
  <div class="gt159-statgrid">
    <div class="gt159-stat"><b>{prior._num(stats.get('ppg'))}</b><span>PPG</span></div>
    <div class="gt159-stat"><b>{prior._num(stats.get('allowed_pg'))}</b><span>Allowed</span></div>
    <div class="gt159-stat"><b>{prior._num(stats.get('point_diff_pg'))}</b><span>Point Diff</span></div>
    <div class="gt159-stat"><b>{escape(_clean(stats.get('recent_form')) or '—')}</b><span>Recent Form</span></div>
  </div>
</div>"""

    away_id, home_id = identity.get("away") or {}, identity.get("home") or {}
    return (
        '<div class="gt159-section" data-testid="gt160-team-evidence">'
        '<div class="gt159-sectionhead"><b>🏈 TEAM EVIDENCE</b><span>Key team metrics at a glance</span></div>'
        f'<div class="gt159-teamgrid">{card(away_id, away)}{card(home_id, home, True)}</div></div>'
    )


def _render_v160_masthead() -> None:
    st.markdown(
        f'''
<div class="gt160-masthead" data-testid="cfb-game-total-monster-masthead" aria-label="{BRAND_MARKER}">
  <div class="gt160-brand"><div class="gt160-mark"></div><div class="gt160-brandcopy"><b>MONSTER</b><span>SPORTS INTELLIGENCE</span></div></div>
  <div class="gt160-nav" aria-label="Sports navigation"><span>NFL</span><span class="active">CFB</span><span>MLB</span><span>NBA</span><span>NHL</span></div>
  <div class="gt160-actions" aria-hidden="true"><span>⌕</span><span>☰</span></div>
</div>''',
        unsafe_allow_html=True,
    )


def _render_v160_identity() -> None:
    st.markdown(
        '<div class="gt160-identity" data-testid="cfb-game-total-v160-active">'
        f'<b>{ACTIVE_MARKER}</b><span>V159 math frozen • sportsbook 0.0%</span></div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    # Main surface = target dashboard. Interactive date/matchup controls and deep
    # evidence stay available in the collapsed sidebar instead of sitting above
    # the dashboard. The frozen V159 analysis/model functions are untouched.
    st.markdown(_V160_CSS, unsafe_allow_html=True)
    _render_v160_masthead()
    _render_v160_identity()

    captured: dict[str, Mapping[str, Any]] = {}
    original_date_input = prior.st.date_input
    original_selectbox = prior.st.selectbox
    original_expander = prior.st.expander
    original_matchup = prior._matchup_header_html
    original_team_evidence = prior._team_evidence_html
    diagnostic_owner = prior.frozen_page.frozen_v2.frozen_v1.identity_ui
    original_diagnostics = diagnostic_owner._diagnostic_badges

    def matchup_wrapper(identity, away, home, display_game):
        captured["identity"] = identity
        return _target_matchup_header_html(identity, away, home, display_game)

    def team_evidence_wrapper(away, home):
        return _target_team_evidence_html(captured.get("identity", {}), away, home)

    prior.st.date_input = st.sidebar.date_input
    prior.st.selectbox = st.sidebar.selectbox
    prior.st.expander = st.sidebar.expander
    prior._matchup_header_html = matchup_wrapper
    prior._team_evidence_html = team_evidence_wrapper
    diagnostic_owner._diagnostic_badges = lambda _diag: ""
    try:
        result = prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        prior.st.date_input = original_date_input
        prior.st.selectbox = original_selectbox
        prior.st.expander = original_expander
        prior._matchup_header_html = original_matchup
        prior._team_evidence_html = original_team_evidence
        diagnostic_owner._diagnostic_badges = original_diagnostics

    # V9 emits its own frozen stylesheet during render. Re-emit V160 last so the
    # target presentation wins the cascade without mutating V159.
    st.markdown(_V160_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V160 Game Total V10 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "BRAND_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "V160_REQUIRED_MARKERS",
    "_V160_CSS",
    "render_cfb_hub",
    "render_game_total_hub",
]
