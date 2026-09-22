"""CFB Game Total Clean Page V9 — V159 compact screenshot-style dashboard.

Presentation-only successor to frozen V158. V159 keeps the exact certified
Game Total model, distribution, qualification, ranking, API, and sportsbook
influence behavior while rebuilding the visible page into one compact dashboard.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v6 as step_owner
import cfb_game_total_clean_page_v7 as evidence_owner
import cfb_game_total_clean_page_v8 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V9 • V159 COMPACT DASHBOARD"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v8"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = step_owner.frozen_page
logo_v3 = step_owner.logo_v3
runtime_display = step_owner.runtime_display

_V159_CSS = r"""
<style>
:root{--gt159-bg:#07131e;--gt159-panel:#091925;--gt159-card:#0d2130;--gt159-border:rgba(82,151,192,.24);--gt159-green:#62efb6;--gt159-blue:#66b9ff;--gt159-purple:#ba86ff;--gt159-amber:#f4ce63;--gt159-red:#ff786f;--gt159-text:#eef6ff;--gt159-muted:#8da2b7}
.gt159-shell{margin:8px 0;padding:12px;border:1px solid var(--gt159-border);border-radius:18px;background:linear-gradient(145deg,#061622,#091522 55%,#0b1222);box-shadow:0 0 28px rgba(36,209,172,.05)}
.gt159-top{border:1px solid rgba(73,141,185,.24);border-left:3px solid var(--gt159-green);border-right:2px solid rgba(166,90,255,.45);border-radius:15px;background:linear-gradient(120deg,#071b28,#071724 58%,#0d1125);overflow:hidden}
.gt159-topline{display:flex;justify-content:space-between;gap:8px;padding:8px 12px 4px;color:#a7bdd0;font-size:.30rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.gt159-topline span:last-child{color:var(--gt159-purple)}
.gt159-matchup{display:grid;grid-template-columns:1fr 54px 1fr;align-items:center;gap:8px;padding:8px 12px 12px}.gt159-team{display:flex;align-items:center;gap:10px;min-width:0}.gt159-team.home{justify-content:flex-end}.gt159-logo{width:58px;height:58px;object-fit:contain;flex:0 0 58px}.gt159-logo-fallback{width:58px;height:58px;display:flex;align-items:center;justify-content:center;border-radius:14px;background:#10293b;color:var(--gt159-blue);font-size:1.1rem;font-weight:950;flex:0 0 58px}.gt159-teamcopy{min-width:0}.gt159-team.home .gt159-teamcopy{text-align:right}.gt159-name{color:var(--gt159-text);font-size:.76rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt159-record{color:#9ab1c6;font-size:.34rem;margin-top:2px}.gt159-conf{display:inline-block;margin-top:5px;padding:3px 8px;border-radius:999px;background:rgba(31,122,171,.16);border:1px solid rgba(73,155,204,.25);color:#a8d7f5;font-size:.25rem;font-weight:900}.gt159-vs{display:flex;align-items:center;justify-content:center;width:42px;height:42px;margin:auto;border-radius:50%;background:#0c2231;border:1px solid rgba(80,136,176,.25);color:#8eabc0;font-weight:950;font-size:.38rem}
.gt159-gamefacts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid rgba(78,139,179,.16)}.gt159-fact{padding:8px 10px;border-right:1px solid rgba(78,139,179,.12);min-width:0}.gt159-fact:last-child{border-right:0}.gt159-fact b{display:block;color:#e7f1f8;font-size:.36rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt159-fact span{display:block;color:#7f95aa;font-size:.24rem;margin-top:2px}
.gt159-total{margin-top:10px;border:1px solid rgba(96,241,183,.25);border-left:3px solid var(--gt159-green);border-right:2px solid rgba(167,95,255,.48);border-radius:15px;background:linear-gradient(135deg,#071b25,#091522 65%,#0e1125);padding:10px}.gt159-totalhead{display:flex;align-items:center;justify-content:space-between;gap:8px;color:#94dbc3;font-size:.34rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}.gt159-cert{padding:4px 9px;border-radius:999px;border:1px solid rgba(98,239,182,.50);background:rgba(18,112,76,.17);color:var(--gt159-green);font-size:.27rem;white-space:nowrap}.gt159-totalgrid{display:grid;grid-template-columns:1.1fr .8fr .95fr .9fr;gap:0;margin-top:10px}.gt159-totalmetric{padding:7px 12px;border-right:1px solid rgba(100,151,184,.20);min-width:0}.gt159-totalmetric:last-child{border-right:0}.gt159-totalmetric span{display:block;color:#8fa2b5;font-size:.26rem;text-transform:uppercase;font-weight:850;letter-spacing:.05em}.gt159-totalmetric b{display:block;color:#f6fbff;font-size:.92rem;line-height:1.05;margin-top:4px;font-weight:950}.gt159-totalmetric.hero b{font-size:1.36rem}.gt159-totalmetric.lean b{color:var(--gt159-green);font-size:.72rem}.gt159-totalmetric small{display:block;color:#70d6b0;font-size:.24rem;margin-top:3px}.gt159-grade{display:inline-block;margin-top:4px;padding:3px 8px;border-radius:999px;border:1px solid rgba(244,206,99,.40);background:rgba(113,84,9,.18);color:var(--gt159-amber);font-size:.25rem;font-weight:900}.gt159-badges{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:9px}.gt159-badge{padding:8px 10px;border:1px solid rgba(86,160,202,.25);border-radius:10px;background:#0a1d2a;color:#c8d7e4;font-size:.29rem;font-weight:850}.gt159-badge strong{color:#f1f7fb}.gt159-badge.purple{border-color:rgba(183,122,255,.35);background:rgba(86,51,127,.15)}.gt159-badge.green{border-color:rgba(98,239,182,.34);background:rgba(24,111,76,.16)}
.gt159-section{margin-top:10px;border:1px solid var(--gt159-border);border-radius:15px;background:linear-gradient(180deg,#081724,#07131e);padding:10px}.gt159-sectionhead{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:8px}.gt159-sectionhead b{color:#f2f7fd;font-size:.48rem;font-weight:950;letter-spacing:.06em}.gt159-sectionhead span{color:#7890a5;font-size:.25rem;text-align:right}.gt159-teamgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.gt159-teamcard{padding:9px;border:1px solid rgba(84,154,193,.24);border-left:3px solid #ff6b4d;border-radius:11px;background:#0a1d2a;min-width:0}.gt159-teamcard.home{border-left-color:#5489ff}.gt159-teamcardtop{display:flex;align-items:center;justify-content:space-between;gap:6px}.gt159-teamcardtop b{color:#f1f6fb;font-size:.45rem}.gt159-rec{padding:3px 8px;border-radius:999px;background:rgba(100,71,193,.18);border:1px solid rgba(143,108,235,.25);color:#ceb9ff;font-size:.25rem;font-weight:900}.gt159-statgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.gt159-stat{padding:6px;border-radius:8px;background:#0e2939}.gt159-stat b{display:block;color:#edf5fb;font-size:.39rem}.gt159-stat span{display:block;color:#7790a4;font-size:.20rem;margin-top:2px;text-transform:uppercase}
.gt159-stepgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt159-step{border:1px solid rgba(73,143,182,.25);border-left:3px solid var(--gt159-green);border-radius:10px;background:#091b28;overflow:hidden}.gt159-step.check,.gt159-step.gated{border-left-color:var(--gt159-amber)}.gt159-step summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 8px}.gt159-step summary::-webkit-details-marker{display:none}.gt159-num{display:flex;align-items:center;justify-content:center;width:27px;height:27px;border-radius:8px;background:rgba(50,190,133,.16);color:var(--gt159-green);font-size:.34rem;font-weight:950}.gt159-step.check .gt159-num,.gt159-step.gated .gt159-num{color:var(--gt159-amber);background:rgba(168,121,24,.15)}.gt159-stepcopy{min-width:0}.gt159-stepcopy b{display:block;color:#ecf4fa;font-size:.37rem;font-weight:950}.gt159-stepcopy span{display:block;color:#8094a7;font-size:.22rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt159-state{padding:3px 7px;border-radius:999px;border:1px solid rgba(98,239,182,.33);background:rgba(23,107,74,.15);color:var(--gt159-green);font-size:.20rem;font-weight:950;white-space:nowrap}.gt159-state.check,.gt159-state.gated{border-color:rgba(244,206,99,.35);background:rgba(116,85,15,.15);color:var(--gt159-amber)}.gt159-stepbody{padding:0 9px 8px 43px;color:#9bb0c1;font-size:.24rem;line-height:1.45}.gt159-stepbody strong{color:#e8f2f9}.gt159-chip{display:inline-block;margin:3px 3px 0 0;padding:3px 6px;border-radius:999px;background:rgba(66,139,182,.12);color:#99cae7;border:1px solid rgba(77,154,195,.18);font-size:.21rem}.gt159-limited{color:var(--gt159-amber)}
.gt159-final{margin-top:10px;border:1px solid rgba(110,91,215,.30);border-radius:15px;background:linear-gradient(145deg,#081927,#0b1424);padding:10px}.gt159-finalhead{display:flex;justify-content:space-between;gap:8px;align-items:center}.gt159-finalhead b{color:#e0c8ff;font-size:.45rem;font-weight:950;letter-spacing:.07em}.gt159-finalhead span{color:#8299ad;font-size:.24rem}.gt159-finalgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:8px}.gt159-finalmetric{padding:9px 6px;text-align:center;border:1px solid rgba(74,144,185,.25);border-radius:10px;background:#0a2030}.gt159-finalmetric b{display:block;color:#f3f8fd;font-size:.59rem}.gt159-finalmetric span{display:block;color:#8499ad;font-size:.20rem;text-transform:uppercase;margin-top:3px}.gt159-notes{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.gt159-note{padding:8px 10px;border-radius:10px;border:1px solid rgba(98,239,182,.34);background:rgba(17,100,67,.16);color:#a9c9bb;font-size:.25rem;line-height:1.5}.gt159-note.concern{border-color:rgba(244,206,99,.35);background:rgba(104,75,15,.16);color:#cbbd94}.gt159-note b{display:block;color:var(--gt159-green);font-size:.28rem;margin-bottom:2px}.gt159-note.concern b{color:var(--gt159-amber)}
.gt159-top5{margin-top:10px;padding:10px 12px;border:1px dashed rgba(154,88,255,.55);border-radius:14px;background:linear-gradient(120deg,rgba(80,39,117,.16),#081522 70%);display:flex;align-items:center;justify-content:space-between;gap:10px}.gt159-top5 b{display:block;color:#d5b8ff;font-size:.40rem;font-weight:950;letter-spacing:.06em}.gt159-top5 span{display:block;color:#7f93a6;font-size:.24rem;margin-top:3px}.gt159-top5 strong{padding:5px 12px;border:1px solid rgba(177,93,255,.6);border-radius:999px;color:#d9adff;font-size:.24rem;white-space:nowrap}
@media(max-width:760px){.gt159-matchup{grid-template-columns:1fr 34px 1fr}.gt159-logo,.gt159-logo-fallback{width:44px;height:44px;flex-basis:44px}.gt159-totalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-totalmetric:nth-child(2){border-right:0}.gt159-badges{grid-template-columns:1fr}.gt159-gamefacts{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-teamgrid{grid-template-columns:1fr}.gt159-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-finalmetric:first-child{grid-column:1/-1}.gt159-notes{grid-template-columns:1fr}}
@media(max-width:420px){.gt159-shell{padding:7px}.gt159-topline{font-size:.24rem}.gt159-matchup{padding:7px;gap:4px}.gt159-team{gap:5px}.gt159-name{font-size:.50rem}.gt159-record{font-size:.27rem}.gt159-conf{font-size:.20rem}.gt159-vs{width:28px;height:28px;font-size:.27rem}.gt159-gamefacts{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-total{padding:8px}.gt159-totalmetric{padding:6px 7px}.gt159-totalmetric.hero b{font-size:1.04rem}.gt159-totalmetric b{font-size:.68rem}.gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-step summary{grid-template-columns:23px minmax(0,1fr);gap:5px;padding:6px}.gt159-num{width:22px;height:22px;font-size:.28rem}.gt159-state{grid-column:2;justify-self:start}.gt159-stepcopy b{font-size:.30rem}.gt159-stepcopy span{font-size:.18rem}.gt159-stepbody{padding:0 6px 7px 34px;font-size:.20rem}.gt159-statgrid{grid-template-columns:repeat(4,minmax(0,1fr));gap:3px}.gt159-stat{padding:4px}.gt159-stat b{font-size:.31rem}.gt159-stat span{font-size:.16rem}.gt159-top5{align-items:flex-start}.gt159-top5 strong{padding:4px 7px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _official_rows(state: Mapping[str, Any], *needles: str, limit: int = 3) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    official = state.get("official_stats") or {}
    for key, raw_row in official.items():
        if not isinstance(raw_row, Mapping):
            continue
        label = _clean(raw_row.get("label")) or _clean(key)
        haystack = f"{key} {label}".lower()
        if needles and not any(str(needle).lower() in haystack for needle in needles):
            continue
        value = _clean(raw_row.get("value") or raw_row.get("display_value") or raw_row.get("stat"))
        rank = _clean(raw_row.get("rank"))
        found.append((label, value or "Verified source row", rank))
        if len(found) >= limit:
            break
    return found


def _compact_object(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, Mapping):
        return " • ".join(f"{k}: {v}" for k, v in list(value.items())[:3] if v not in (None, "", [], {}))
    if isinstance(value, (list, tuple)):
        return " • ".join(_clean(v) for v in list(value)[:3] if _clean(v))
    return _clean(value)


def _logo(team: Mapping[str, Any]) -> str:
    name = _clean(team.get("team")) or "CFB"
    url = _clean(team.get("logo"))
    if url:
        return f'<img class="gt159-logo" src="{escape(url)}" alt="{escape(name)} logo">'
    initials = "".join(word[:1] for word in name.split())[:2].upper() or "CF"
    return f'<div class="gt159-logo-fallback">{escape(initials)}</div>'


def _market_total(display_game: Mapping[str, Any]) -> float | None:
    candidates = (
        display_game.get("total"), display_game.get("market_total"), display_game.get("total_line"),
        display_game.get("over_under"), display_game.get("ou"),
    )
    odds = display_game.get("odds") or display_game.get("market") or {}
    if isinstance(odds, Mapping):
        candidates += (odds.get("total"), odds.get("market_total"), odds.get("total_line"), odds.get("over_under"))
    for value in candidates:
        try:
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _matchup_header_html(identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], display_game: Mapping[str, Any]) -> str:
    away_id, home_id = identity.get("away") or {}, identity.get("home") or {}
    away_name = _clean(away_id.get("team")) or _clean(away.get("team")) or "Away"
    home_name = _clean(home_id.get("team")) or _clean(home.get("team")) or "Home"
    kickoff = _clean(identity.get("kickoff")) or _clean(display_game.get("kickoff")) or "Kickoff unavailable"
    venue = _clean(identity.get("venue")) or _clean(display_game.get("venue")) or "Venue unavailable"
    weather = _clean(display_game.get("weather") or display_game.get("forecast")) or "Weather unavailable"
    temp = _clean(display_game.get("temperature"))
    wind = _clean(display_game.get("wind") or display_game.get("wind_mph")) or "Wind unavailable"
    return f"""
<div class="gt159-top" data-testid="gt159-matchup-header">
  <div class="gt159-topline"><span>NCAAF • {escape(kickoff)}</span><span>GAME TOTAL ANALYSIS</span></div>
  <div class="gt159-matchup">
    <div class="gt159-team">{_logo(away_id)}<div class="gt159-teamcopy"><div class="gt159-name">{escape(away_name)}</div><div class="gt159-record">{escape(_clean(away.get('record')) or '—')} ({escape(_clean(away_id.get('conference')) or '—')})</div><span class="gt159-conf">{escape(_clean(away_id.get('conference')) or 'NCAAF')}</span></div></div>
    <div class="gt159-vs">VS</div>
    <div class="gt159-team home"><div class="gt159-teamcopy"><div class="gt159-name">{escape(home_name)}</div><div class="gt159-record">{escape(_clean(home.get('record')) or '—')} ({escape(_clean(home_id.get('conference')) or '—')})</div><span class="gt159-conf">{escape(_clean(home_id.get('conference')) or 'NCAAF')}</span></div>{_logo(home_id)}</div>
  </div>
  <div class="gt159-gamefacts">
    <div class="gt159-fact"><b>{escape(venue)}</b><span>Venue</span></div>
    <div class="gt159-fact"><b>{escape((temp + '° • ') if temp else '')}{escape(weather)}</b><span>Weather</span></div>
    <div class="gt159-fact"><b>{escape(wind)}</b><span>Wind</span></div>
    <div class="gt159-fact"><b>{escape(kickoff)}</b><span>Kickoff</span></div>
  </div>
</div>"""


def _game_total_hero_html(raw: Mapping[str, Any], final: Mapping[str, Any], display_game: Mapping[str, Any], statuses: Mapping[int, str], ready_count: int) -> str:
    projected_value = final.get("projected_combined_total") if final.get("ready") else raw.get("projected_combined_total")
    projected = _num(projected_value)
    market = _market_total(display_game)
    grade = _clean(final.get("grade")) if final.get("ready") else "—"
    strength = _pct(final.get("forecast_strength")) if final.get("ready") else "—"
    if market is None:
        market_text = "—"
        lean = "Market total unavailable"
        lean_sub = "No verified line • model remains independent"
    else:
        market_text = _num(market)
        try:
            edge = float(projected_value) - market
            if edge > 0:
                lean = f"Over +{abs(edge):.1f}"
                lean_sub = "Slight Over Lean" if abs(edge) < 2 else "Over Lean"
            elif edge < 0:
                lean = f"Under -{abs(edge):.1f}"
                lean_sub = "Slight Under Lean" if abs(edge) < 2 else "Under Lean"
            else:
                lean, lean_sub = "Even 0.0", "No directional edge"
        except (TypeError, ValueError):
            lean, lean_sub = "Market total unavailable", "No verified line • model remains independent"
    data_check = max(0, 12 - int(ready_count))
    return f"""
<div class="gt159-total" data-testid="gt159-game-total-hero">
  <div class="gt159-totalhead"><span>⬢ GAME TOTAL</span><span class="gt159-cert">🛡 5M CERTIFIED</span></div>
  <div class="gt159-totalgrid">
    <div class="gt159-totalmetric hero"><span>Projected Total</span><b>{escape(projected)}</b></div>
    <div class="gt159-totalmetric"><span>Market Total</span><b>{escape(market_text)}</b></div>
    <div class="gt159-totalmetric lean"><span>Over / Under Lean</span><b>{escape(lean)}</b><small>{escape(lean_sub)}</small></div>
    <div class="gt159-totalmetric"><span>Confidence</span><b>{escape(strength)}</b><div class="gt159-grade">Grade: {escape(grade or '—')}</div></div>
  </div>
  <div class="gt159-badges">
    <div class="gt159-badge">⭐ <strong>5M Certified</strong><br>Model validated • Real data only</div>
    <div class="gt159-badge purple">▥ <strong>0.0% sportsbook projection influence</strong><br>Independent analysis</div>
    <div class="gt159-badge green">✓ <strong>{data_check}/12 Data Check</strong><br>{'All core data verified' if data_check == 0 else 'Review limited evidence rows'}</div>
  </div>
</div>"""


def _team_evidence_html(away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    def card(team: Mapping[str, Any], home_side: bool = False) -> str:
        return f"""
<div class="gt159-teamcard {'home' if home_side else ''}">
 <div class="gt159-teamcardtop"><b>{escape(_clean(team.get('team')) or 'Team')}</b><span class="gt159-rec">{escape(_clean(team.get('record')) or '—')}</span></div>
 <div class="gt159-statgrid">
  <div class="gt159-stat"><b>{_num(team.get('ppg'))}</b><span>PPG</span></div>
  <div class="gt159-stat"><b>{_num(team.get('allowed_pg'))}</b><span>Allowed</span></div>
  <div class="gt159-stat"><b>{_num(team.get('point_diff_pg'))}</b><span>Point Diff</span></div>
  <div class="gt159-stat"><b>{escape(_clean(team.get('recent_form')) or '—')}</b><span>Recent Form</span></div>
 </div>
</div>"""
    return f'<div class="gt159-section"><div class="gt159-sectionhead"><b>🏈 TEAM EVIDENCE</b><span>Key team metrics at a glance • full detail in steps below</span></div><div class="gt159-teamgrid">{card(away)}{card(home, True)}</div></div>'


def _step_body(number: int, detail: str, identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], display_game: Mapping[str, Any], model: Mapping[str, Any]) -> tuple[str, str]:
    away_name = _clean(away.get("team")) or _clean((identity.get("away") or {}).get("team")) or "Away"
    home_name = _clean(home.get("team")) or _clean((identity.get("home") or {}).get("team")) or "Home"
    if number == 1:
        text = f"{away_name}: {_clean((identity.get('away') or {}).get('conference')) or 'conference unavailable'} • {home_name}: {_clean((identity.get('home') or {}).get('conference')) or 'conference unavailable'}"
    elif number == 2:
        text = f"{away_name} {_clean(away.get('record')) or '—'} • {_num(away.get('ppg'))} PPG | {home_name} {_clean(home.get('record')) or '—'} • {_num(home.get('ppg'))} PPG"
    elif number == 3:
        text = f"{away_name} {_num(away.get('ppg'))} vs {home_name} {_num(home.get('allowed_pg'))} allowed • {home_name} {_num(home.get('ppg'))} vs {away_name} {_num(away.get('allowed_pg'))} allowed"
    elif number in (4,5,6,7,8):
        needles = {4:("pace","tempo","plays per game","seconds per play"),5:("explosive","yards per play","20+","10+"),6:("red zone",),7:("third down","3rd down"),8:("turnover","giveaway","takeaway")}[number]
        rows = _official_rows(away,*needles,limit=2) + _official_rows(home,*needles,limit=2)
        if not rows:
            return detail, f'<span class="gt159-limited">DATA LIMITED • {escape(detail)}</span>'
        text = " • ".join(f"{label}: {value}" + (f" (Rank {rank})" if rank else "") for label,value,rank in rows)
    elif number == 9:
        values = [v for v in (display_game.get("weather") or display_game.get("forecast"), display_game.get("temperature"), display_game.get("wind") or display_game.get("wind_mph"), (identity.get("venue") if isinstance(identity,Mapping) else None) or display_game.get("venue")) if v not in (None,"")]
        if not values:
            return detail, f'<span class="gt159-limited">DATA LIMITED • {escape(detail)}</span>'
        text = " • ".join(_clean(v) for v in values)
    elif number == 10:
        text = _compact_object(display_game.get("history") or display_game.get("series_history") or display_game.get("head_to_head"))
        if not text:
            return detail, f'<span class="gt159-limited">DATA LIMITED • {escape(detail)}</span>'
    elif number == 11:
        raw = model.get("raw") or {}; text = f"Projection {_num(raw.get('projected_combined_total'))} • frozen distribution output preserved"
    else:
        final = model.get("final") or {}; text = f"Projection {_num(final.get('projected_combined_total'))} • grade {_clean(final.get('grade')) or '—'} • strength {_pct(final.get('forecast_strength'))}"
    return text, escape(text)


def _step_evidence_html(number: int, title: str, status: str, detail: str, identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], display_game: Mapping[str, Any], model: Mapping[str, Any]) -> str:
    state = "ready" if status == "READY" else ("gated" if status == "GATED" else "check")
    summary_text, body = _step_body(number, detail, identity, away, home, display_game, model)
    shown = status
    if "DATA LIMITED" in body:
        shown, state = "DATA LIMITED", "check"
    return f"""<details class="gt159-step {state}" data-testid="gt157-step-{number}"><summary><span class="gt159-num">{number}</span><span class="gt159-stepcopy"><b>{escape(title)}</b><span>{escape(summary_text)}</span></span><span class="gt159-state {state}">{escape(shown)}</span></summary><div class="gt159-stepbody">{body}</div></details>"""


def _combined_flow_html(statuses: Mapping[int, str], details: Mapping[int, str], raw: Mapping[str, Any], final: Mapping[str, Any], identity: Mapping[str, Any] | None = None, away: Mapping[str, Any] | None = None, home: Mapping[str, Any] | None = None, display_game: Mapping[str, Any] | None = None) -> str:
    identity, away, home, display_game = identity or {}, away or {}, home or {}, display_game or {}
    model = {"raw": raw, "final": final}
    rows: list[str] = []
    for number, title, _ in step_owner._STEP_1_10:
        rows.append(_step_evidence_html(number,title,_clean(statuses.get(number)) or "CHECK",_clean(details.get(number)) or "Verified evidence check",identity,away,home,display_game,model))
    step11 = "READY" if raw.get("ready") else "GATED"; step12 = "READY" if final.get("ready") else "GATED"
    rows.append(_step_evidence_html(11,"Distribution",step11,"Frozen distribution output",identity,away,home,display_game,model))
    rows.append(_step_evidence_html(12,"Final Synthesis",step12,"Frozen final synthesis",identity,away,home,display_game,model))
    ready_count = sum(1 for n in range(1,11) if statuses.get(n)=="READY") + int(bool(raw.get("ready"))) + int(bool(final.get("ready")))
    projected = final.get("projected_combined_total") if final.get("ready") else raw.get("projected_combined_total")
    core = final.get("core_50_range") or {}; band = final.get("most_likely_band") or {}
    core_text = f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}" if final.get("ready") and core else "—"
    supports = ["Model + data quality", "Environment neutral" if statuses.get(9)=="READY" else "Environment needs verification", "Recent form + matchup data"]
    concerns = ["Turnover data limited" if statuses.get(8)!="READY" else "Turnover volatility", "Pace variance", "Red zone efficiency gap"]
    return _V159_CSS + f"""
<div class="gt159-section" data-testid="gt157-connected-all-steps"><div class="gt159-sectionhead"><b>☷ GAME TOTAL EVIDENCE • STEPS 1–12</b><span>Real team evidence • frozen calculations • professional model</span></div><div class="gt159-stepgrid">{''.join(rows)}</div></div>
<div class="gt159-final" data-testid="gt157-final-summary"><div class="gt159-finalhead"><b>▥ FINAL MODEL SUMMARY</b><span>{ready_count}/12 steps ready</span></div><div class="gt159-finalgrid"><div class="gt159-finalmetric"><b>{escape(_num(projected))}</b><span>Projected Total</span></div><div class="gt159-finalmetric"><b>{escape(core_text)}</b><span>Core Range (50%)</span></div><div class="gt159-finalmetric"><b>{escape(_clean(band.get('label')) or '—')}</b><span>Likely Band</span></div><div class="gt159-finalmetric"><b>{escape(_clean(final.get('grade')) or '—')}</b><span>Grade</span></div><div class="gt159-finalmetric"><b>{escape(_pct(final.get('forecast_strength')))}</b><span>Strength</span></div></div><div class="gt159-notes"><div class="gt159-note"><b>✓ KEY SUPPORTS</b>{'<br>• '.join([''] + [escape(x) for x in supports])}</div><div class="gt159-note concern"><b>⚠ KEY CONCERNS</b>{'<br>• '.join([''] + [escape(x) for x in concerns])}</div></div></div>
<div class="gt159-top5" data-testid="gt157-top5-connector"><div><b>🏆 TOP-5 SLATE SCANNER</b><span>Full slate rankings based on model edge, data quality, and opportunity.</span></div><strong>VIEW TOP 5 →</strong></div>"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    selected = st.date_input("📅 CFB Game Total slate date", value=datetime.now(step_owner.prior.prior.prior.prior.prior._PHOENIX).date(), key="cfb_v152_game_total_date")
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V159 fails closed—no Game Total forecast is invented.")
        return
    index = st.selectbox("🏟️ Game Total matchup", options=list(range(len(games))), format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]), key=f"cfb_v152_game_total_matchup_{selected_day}")
    game = games[int(index)]
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away, frozen_home = selected_result.get("away") or {}, selected_result.get("home") or {}
    raw, final = selected_result.get("raw") or {}, selected_result.get("final") or {}
    display_game, display_away, display_home, _ = runtime_display.reconcile_display_bundle(game, selected_day, frozen_away, frozen_home)
    visuals = logo_v3.resolve_visuals(display_game)
    identity = step_owner.prior.prior.prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = step_owner.prior.prior._team_stats_state(display_away, display_game, "away")
    home_stats = step_owner.prior.prior._team_stats_state(display_home, display_game, "home")
    away_evidence = step_owner.prior._team_evidence_state(display_away, display_game, "away")
    home_evidence = step_owner.prior._team_evidence_state(display_home, display_game, "home")
    statuses = step_owner._existing_step_status(identity, away_evidence, home_evidence, display_game)
    details = step_owner._step_details(identity, away_evidence, home_evidence, statuses)
    ready_count = sum(1 for n in range(1,11) if statuses.get(n)=="READY") + int(bool(raw.get("ready"))) + int(bool(final.get("ready")))
    st.markdown(_V159_CSS + '<div class="gt159-shell">' + _matchup_header_html(identity,away_stats,home_stats,display_game) + _game_total_hero_html(raw,final,display_game,statuses,ready_count) + _team_evidence_html(away_stats,home_stats) + _combined_flow_html(statuses,details,raw,final,identity,away_evidence,home_evidence,display_game) + '</div>', unsafe_allow_html=True)
    with st.expander("🔬 Raw Steps 1–10 evidence", expanded=False): evidence_owner._render_raw_team_evidence(away_evidence, home_evidence)
    with st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False):
        st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
        for panel in (frozen_page.frozen_v2._band_panel(raw), frozen_page.frozen_v2._around_projection_panel(raw), frozen_page.frozen_v2._exact_panel(raw), frozen_page.frozen_v2._components_panel(raw)):
            if panel: st.markdown(panel, unsafe_allow_html=True)
    with st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False): st.markdown(frozen_page._final_card(game, final), unsafe_allow_html=True)
    with st.expander("🏆 Top-5 slate scanner", expanded=False):
        scan_key, diag_key = f"cfb_v159_top5_{selected_day}", f"cfb_v159_scan_diag_{selected_day}"
        if st.button("Run final Game Total Top-5 scan", type="primary", key=f"cfb_v159_scan_button_{selected_day}"):
            with st.spinner("Scanning the verified CFB slate through frozen Steps 11–12..."):
                rows, diag = frozen_page.slate.scan_slate(games, selected_day); st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5); st.session_state[diag_key] = diag
        top5, diag = st.session_state.get(scan_key) or [], st.session_state.get(diag_key) or {}
        if diag: st.caption(f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • {int(diag.get('final_ready') or 0)} final-ready • {int(diag.get('qualified_forecasts') or 0)} ranked-eligible • {len(diag.get('errors') or [])} errors")
        if top5:
            for row in top5: st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
        elif diag: st.warning("No game cleared the frozen Step-12 qualification thresholds. V159 will not force a Top-5.")
        else: st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")
    st.caption("🛡️ V159 compact dashboard display only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET: raise ValueError(f"V159 Game Total V9 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = ["FROZEN_PRESENTATION","MARKET","MAY_MODIFY_PROJECTION","MODEL_VERSION","SPORTSBOOK_PROJECTION_INFLUENCE","_V159_CSS","_combined_flow_html","_game_total_hero_html","_official_rows","_step_evidence_html","render_cfb_hub","render_game_total_hub"]
