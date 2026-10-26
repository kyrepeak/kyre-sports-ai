"""NFL Moneyline Page 2 — selected-matchup War Room presentation."""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st
import nfl_moneyline_hub_v9 as presentation

MODEL_VERSION = "NFL MONEYLINE PAGE2 WAR ROOM V1"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_CSS = r"""
<style data-nfl-moneyline-page2-war-room-css="true">
.kwr,.kwr *{box-sizing:border-box}.kwr{max-width:1120px;margin:0 auto;color:#eaf4fb;font-family:Inter,system-ui,sans-serif}
.kwr a{text-decoration:none}.kwr-nav{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:.2rem 0 .55rem}.kwr-back{display:inline-flex;padding:8px 11px;border:1px solid #244d69;border-radius:9px;color:#a8dfff;background:#07131d;font-size:.64rem;font-weight:900}.kwr-tabs{display:flex;gap:5px;padding:4px;border:1px solid #18364b;border-radius:999px;background:#07131d}.kwr-tabs span{padding:6px 12px;border-radius:999px;color:#7892a7;font-size:.53rem;font-weight:850}.kwr-tabs .active{color:#dff5ff;background:#0a2b42;border-bottom:2px solid #35b8ff}
.kwr-hero{border:1px solid rgba(67,194,255,.28);border-radius:17px;padding:.82rem;background:radial-gradient(circle at 50% 0%,rgba(48,129,199,.16),transparent 46%),linear-gradient(150deg,#071521,#061019);box-shadow:0 16px 42px rgba(0,0,0,.16)}
.kwr-kicker{color:#59caff;font-size:.52rem;font-weight:950;letter-spacing:.11em}.kwr-match{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:.7rem;margin:.48rem 0}.kwr-team{display:flex;gap:9px;align-items:center;min-width:0}.kwr-team.right{justify-content:flex-end;text-align:right}.kwr-team img{width:58px!important;height:58px!important;object-fit:contain}.kwr-team b{display:block;font-size:1rem;color:#f2f7fb}.kwr-team span{display:block;color:#7f98ad;font-size:.56rem}.kwr-time{text-align:center}.kwr-time b{display:block;color:#f4f8fb;font-size:.86rem}.kwr-time span{display:block;color:#7590a5;font-size:.49rem;margin-top:2px}
.kwr-hero-grid{display:grid;grid-template-columns:1fr 1.65fr 1fr;gap:.5rem}.kwr-price,.kwr-pick{border:1px solid rgba(72,188,244,.18);border-radius:11px;padding:.62rem;background:#06121d}.kwr-price span,.kwr-metric span{display:block;color:#6f8aa0;font-size:.42rem;font-weight:900;letter-spacing:.06em}.kwr-price b{display:block;margin-top:4px;font-size:1rem}.kwr-pick{display:grid;grid-template-columns:1fr auto;align-items:center;border-color:#28d7a1}.kwr-pick small{display:block;color:#53e2b6;font-weight:950;font-size:.46rem}.kwr-pick b{display:block;font-size:1.1rem}.kwr-pick .prob{color:#43e3bd;font-size:1.36rem;font-weight:950}.kwr-grade{display:inline-flex;margin-top:4px;padding:4px 7px;border-radius:999px;background:#123b31;color:#83f3d0;font-size:.44rem;font-weight:950}
.kwr-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.45rem;margin:.5rem 0}.kwr-metric{padding:.58rem;border:1px solid rgba(72,188,244,.14);border-radius:10px;background:#07131e}.kwr-metric b{display:block;margin-top:4px;font-size:.84rem;color:#eef7fc}.kwr-metric.good b{color:#42e0b5}
.kwr-grid2{display:grid;grid-template-columns:1.2fr .9fr;gap:.55rem;margin-top:.55rem}.kwr-panel{min-width:0;border:1px solid rgba(72,188,244,.15);border-radius:13px;background:linear-gradient(145deg,#07131e,#061019);padding:.7rem}.kwr-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:.5rem}.kwr-title b{font-size:.66rem;letter-spacing:.04em;color:#f0f7fb}.kwr-title span{color:#68849b;font-size:.43rem}.kwr-list{display:grid;gap:.38rem}.kwr-reason{display:grid;grid-template-columns:24px 1fr;gap:7px;align-items:start;color:#c8d7e2;font-size:.53rem;line-height:1.45}.kwr-num{width:22px;height:22px;border:1px solid #2f9ddb;border-radius:50%;display:grid;place-items:center;color:#89d9ff;font-size:.48rem;font-weight:950}.kwr-callouts{display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin-top:.55rem}.kwr-callout{padding:.5rem;border:1px solid rgba(45,217,160,.26);border-radius:9px;background:#071a19}.kwr-callout.risk{border-color:rgba(255,91,99,.28);background:#191013}.kwr-callout b{display:block;color:#61ebc0;font-size:.45rem}.kwr-callout.risk b{color:#ff727a}.kwr-callout p{margin:.26rem 0 0;color:#a9bccb;font-size:.47rem;line-height:1.4}
.kwr-factors{display:grid;gap:.35rem}.kwr-factor{display:grid;grid-template-columns:58px 1fr 96px 1fr 58px;gap:7px;align-items:center;padding:.45rem;border-top:1px solid rgba(72,188,244,.07);font-size:.48rem}.kwr-factor:first-child{border-top:0}.kwr-factor .label{text-align:center;color:#a8bbc9}.kwr-factor .val{font-weight:900;color:#e4edf4}.kwr-factor .home{text-align:right}.kwr-bar{height:7px;border-radius:999px;background:#102a3d;overflow:hidden}.kwr-bar i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#2999ff,#45c1ff)}.kwr-bar.home i{background:linear-gradient(90deg,#23bf98,#52e0b6)}
.kwr-history{margin-top:.55rem}.kwr-history-wrap{display:grid;grid-template-columns:1.45fr .7fr;gap:.5rem}.kwr-table{width:100%;border-collapse:collapse;font-size:.47rem}.kwr-table th{color:#63839b;text-align:left;font-size:.38rem;letter-spacing:.06em;padding:.35rem}.kwr-table td{padding:.43rem .35rem;border-top:1px solid rgba(72,188,244,.08);color:#bfd0dc}.kwr-history-summary{display:grid;gap:.35rem}.kwr-summary{padding:.48rem;border:1px solid rgba(72,188,244,.1);border-radius:9px;background:#06111b}.kwr-summary span{display:block;color:#6d879b;font-size:.38rem}.kwr-summary b{display:block;margin-top:3px;font-size:.61rem}.kwr details{margin-top:.45rem;border:1px solid rgba(72,188,244,.12);border-radius:9px;background:#06111b;padding:.45rem}.kwr summary{cursor:pointer;color:#73cfff;font-size:.46rem;font-weight:950;list-style:none}.kwr-empty{color:#8096a8;font-size:.5rem;line-height:1.45;padding:.45rem 0}
.kwr-paths{display:grid;grid-template-columns:1fr 1fr;gap:.45rem}.kwr-path{padding:.55rem;border:1px solid rgba(44,210,159,.2);border-radius:9px;background:#071915}.kwr-path.upset{border-color:rgba(73,168,255,.2);background:#07151f}.kwr-path b{display:block;color:#61e8bf;font-size:.47rem}.kwr-path.upset b{color:#79c8ff}.kwr-path p{margin:.3rem 0 0;color:#a8bbc9;font-size:.46rem;line-height:1.45}
.kwr-avail,.kwr-form,.kwr-market{display:grid;grid-template-columns:1fr 1fr;gap:.45rem}.kwr-team-box{padding:.55rem;border:1px solid rgba(72,188,244,.11);border-radius:9px;background:#06111b}.kwr-team-box h4{margin:0 0 .35rem;color:#dfeaf2;font-size:.53rem}.kwr-player{display:flex;justify-content:space-between;gap:8px;padding:.35rem 0;border-top:1px solid rgba(72,188,244,.06);font-size:.45rem}.kwr-player:first-of-type{border-top:0}.kwr-player span{color:#aec1ce}.kwr-player b{color:#dceaf3}.kwr-status{color:#f2cd6f!important}.kwr-form-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.3rem}.kwr-form-stat{padding:.42rem;border-radius:7px;background:#071827;text-align:center}.kwr-form-stat span{display:block;color:#657f96;font-size:.36rem}.kwr-form-stat b{display:block;margin-top:2px;font-size:.58rem}
.kwr-market-board{grid-column:1/-1;overflow:hidden}.kwr-book{display:grid;grid-template-columns:1.2fr .7fr .7fr .8fr;gap:6px;padding:.38rem .3rem;border-top:1px solid rgba(72,188,244,.07);font-size:.43rem}.kwr-book b{color:#dce7ef}.kwr-book span{color:#7690a4}.kwr-bottom{display:grid;grid-template-columns:1.3fr .75fr;gap:.55rem;margin-top:.55rem}.kwr-sim{display:grid;grid-template-columns:auto 1fr;gap:.7rem;align-items:center}.kwr-donut{width:112px;height:112px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#42dfb4 0 var(--p),#2f91f4 var(--p) 100%)}.kwr-donut:after{content:'';width:68px;height:68px;border-radius:50%;background:#07131e}.kwr-sim-grid{display:grid;grid-template-columns:1fr 1fr;gap:.35rem}.kwr-sim-stat{padding:.45rem;border-radius:8px;background:#06111b}.kwr-sim-stat span{display:block;color:#6e899f;font-size:.39rem}.kwr-sim-stat b{display:block;margin-top:2px;font-size:.68rem}.kwr-risks{display:grid;gap:.35rem}.kwr-risk{display:flex;justify-content:space-between;gap:10px;border-top:1px solid rgba(72,188,244,.07);padding:.35rem 0;font-size:.43rem}.kwr-risk:first-child{border-top:0}.kwr-risk span{color:#aebfcb}.kwr-risk b{padding:2px 6px;border-radius:999px;background:#2a2713;color:#f2d56c}.kwr-risk b.HIGH{background:#321317;color:#ff777d}.kwr-final{margin:.55rem 0 1rem;padding:.7rem;border:1px solid #36dba9;border-radius:12px;background:linear-gradient(90deg,#071b18,#07131d);display:grid;grid-template-columns:1.4fr .45fr .45fr;gap:.6rem;align-items:center}.kwr-final small{display:block;color:#5fe7bd;font-weight:950;font-size:.4rem}.kwr-final b{display:block;margin-top:3px;font-size:.92rem}.kwr-final-metric{text-align:center}.kwr-final-metric span{display:block;color:#728ca1;font-size:.36rem}.kwr-final-metric b{font-size:.76rem;color:#56e5ba}
@media(max-width:760px){.kwr-tabs{display:none}.kwr-match{grid-template-columns:1fr 1fr}.kwr-time{grid-column:1/-1;grid-row:1;text-align:left}.kwr-hero-grid,.kwr-grid2,.kwr-history-wrap,.kwr-bottom{grid-template-columns:1fr}.kwr-pick{grid-row:1}.kwr-metrics{grid-template-columns:1fr 1fr}.kwr-avail,.kwr-form{grid-template-columns:1fr}.kwr-factor{grid-template-columns:44px 1fr 74px 1fr 44px}.kwr-callouts,.kwr-paths{grid-template-columns:1fr}.kwr-final{grid-template-columns:1fr 1fr}.kwr-final>div:first-child{grid-column:1/-1}}
@media(max-width:520px){.kwr{width:100%;overflow-x:hidden}.kwr-hero{padding:.65rem}.kwr-team img{width:42px!important;height:42px!important}.kwr-team b{font-size:.78rem}.kwr-match{gap:.35rem}.kwr-hero-grid{grid-template-columns:1fr}.kwr-price{display:grid;grid-template-columns:1fr auto;align-items:center}.kwr-price b{margin:0}.kwr-pick{grid-row:auto}.kwr-metrics{grid-template-columns:1fr 1fr}.kwr-panel{padding:.58rem}.kwr-factor{grid-template-columns:38px 1fr 62px 1fr 38px;gap:4px;font-size:.4rem}.kwr-table{font-size:.4rem}.kwr-table th,.kwr-table td{padding:.32rem .22rem}.kwr-book{grid-template-columns:1fr .65fr .65fr}.kwr-book>*:last-child{display:none}.kwr-sim{grid-template-columns:1fr}.kwr-donut{margin:auto}.kwr-final{grid-template-columns:1fr 1fr}}
</style>
"""


def _clean(value: Any, fallback: str = "—") -> str:
    try: text = str(value if value is not None else "").strip()
    except Exception: text = ""
    return text or fallback


def _num(value: Any) -> float | None:
    try: n = float(value)
    except (TypeError, ValueError, OverflowError): return None
    return n if math.isfinite(n) else None


def _pct(value: Any, digits: int = 1) -> str:
    n = _num(value); return "—" if n is None else f"{100*n:.{digits}f}%"


def _pp(value: Any) -> str:
    n = _num(value); return "—" if n is None else f"{('+' if n>0 else '')}{100*n:.1f}%"


def _ml(value: Any) -> str:
    n = _num(value)
    if n is None: return "—"
    x=int(round(n)); return f"+{x}" if x>0 else str(x)


def _fmt(value: Any, digits: int = 1) -> str:
    n = _num(value); return "—" if n is None else f"{n:.{digits}f}"


def _logo(game: Mapping[str, Any], side: str) -> str:
    try: return presentation._team_logo(dict(game), side)
    except Exception: return ""


def _history_rows(rows: list[Mapping[str, Any]]) -> str:
    out=[]
    for row in rows:
        winner=_clean(row.get("winner_abbr")); score=_clean(row.get("score")); margin=_fmt(row.get("margin"),0)
        out.append(f'<tr><td>{escape(_clean(row.get("date")))}</td><td>{escape(_clean(row.get("site")))}</td><td><b>{escape(winner)}</b></td><td>{escape(score)}</td><td>+{escape(margin)}</td></tr>')
    return "".join(out)


def _availability_box(ctx: Mapping[str, Any], team: str) -> str:
    players=[f'<div class="kwr-player"><span>QB • {escape(_clean(ctx.get("starter_qb"),"Verification pending"))}</span><b class="kwr-status">{escape(_clean(ctx.get("starter_status"),"CHECK"))}</b></div>']
    for row in ctx.get("injuries") or []:
        players.append(f'<div class="kwr-player"><span>{escape(_clean(row.get("position")))} • {escape(_clean(row.get("name")))}</span><b class="kwr-status">{escape(_clean(row.get("status"),"CHECK"))}</b></div>')
    return f'<div class="kwr-team-box"><h4>{escape(team)}</h4>{"".join(players)}</div>'


def _factor_rows(context: Mapping[str, Any]) -> str:
    away=_clean((context.get("game") or {}).get("away_abbr"),"AWY"); home=_clean((context.get("game") or {}).get("home_abbr"),"HME")
    rows=[]
    for row in context.get("advantages") or []:
        av=_num(row.get("away")); hv=_num(row.get("home")); high=max(abs(av or 0),abs(hv or 0),1.0)
        aw=max(8,min(100,abs(av or 0)/high*100)); hw=max(8,min(100,abs(hv or 0)/high*100))
        rows.append(f'<div class="kwr-factor"><span class="val">{escape(_fmt(av))}</span><div class="kwr-bar"><i style="width:{aw:.0f}%"></i></div><span class="label">{escape(_clean(row.get("label")))}</span><div class="kwr-bar home"><i style="width:{hw:.0f}%"></i></div><span class="val home">{escape(_fmt(hv))}</span></div>')
    if not rows: return '<div class="kwr-empty">Verified comparison metrics are not yet available.</div>'
    return f'<div style="display:flex;justify-content:space-between;color:#6f8da4;font-size:.42rem"><b>{escape(away)}</b><b>{escape(home)}</b></div>'+"".join(rows)


def build_war_room_html(context: Mapping[str, Any]) -> str:
    game=context.get("game") or {}; verdict=context.get("verdict") or {}; history=context.get("history") or {}; sim=context.get("simulation") or {}
    away=_clean(game.get("away_team"),"Away"); home=_clean(game.get("home_team"),"Home"); away_abbr=_clean(game.get("away_abbr"),"AWY"); home_abbr=_clean(game.get("home_abbr"),"HME")
    market=context.get("market") or {}; best_away=market.get("best_away") or {}; best_home=market.get("best_home") or {}
    reasons=context.get("why") or {}; bullets=reasons.get("bullets") or []
    reason_html="".join(f'<div class="kwr-reason"><span class="kwr-num">{i}</span><span>{escape(_clean(text))}</span></div>' for i,text in enumerate(bullets,1)) or '<div class="kwr-empty">Verified explanatory evidence is still resolving.</div>'
    recent=history.get("recent_meetings") or []; full=history.get("full_meetings") or []
    if history.get("status")=="READY":
        history_main=f'<table class="kwr-table"><thead><tr><th>DATE</th><th>LOCATION</th><th>WINNER</th><th>SCORE</th><th>MARGIN</th></tr></thead><tbody>{_history_rows(recent)}</tbody></table>'
        full_details=f'<details><summary>VIEW FULL HISTORY →</summary><table class="kwr-table"><tbody>{_history_rows(full)}</tbody></table></details>'
    else:
        history_main=f'<div class="kwr-empty">{escape(_clean(history.get("reason"),"No previous verified matchup history is available."))}</div>'
        full_details='<details><summary>VIEW FULL HISTORY →</summary><div class="kwr-empty">No additional verified meetings are available.</div></details>'
    hist_insight = f'{_clean(history.get("series_summary"),"No verified series edge")} across the verified history. Historical results are context only and do not alter model P(win).'
    avail=context.get("availability") or {}; form=context.get("recent_form") or {}
    away_prof=form.get("away") or {}; home_prof=form.get("home") or {}
    books=[]
    for row in (market.get("rows") or [])[:6]: books.append(f'<div class="kwr-book"><b>{escape(_clean(row.get("book")))}</b><span>{escape(_ml(row.get("away_ml")))}</span><span>{escape(_ml(row.get("home_ml")))}</span><span>{escape(_clean(row.get("freshness")))}</span></div>')
    if not books: books=['<div class="kwr-empty">No verified sportsbook rows are available in the frozen market snapshot.</div>']
    home_win=_num(sim.get("home_win_rate")); away_win=_num(sim.get("away_win_rate")); pick_side=_clean(verdict.get("pick_side"),"home")
    pick_win=home_win if pick_side=="home" else away_win
    if pick_win is None: pick_win=_num(verdict.get("model_probability")) or 0.5
    donut=max(0,min(100,100*pick_win))
    risks="".join(f'<div class="kwr-risk"><span>{escape(_clean(r.get("label")))}</span><b class="{escape(_clean(r.get("level"),"MEDIUM"))}">{escape(_clean(r.get("level"),"MEDIUM"))}</b></div>' for r in context.get("risks") or [])
    script=context.get("game_script") or {}
    pick_path="<br>✓ ".join(escape(_clean(x)) for x in script.get("pick_path") or []); upset_path="<br>• ".join(escape(_clean(x)) for x in script.get("upset_path") or [])
    away_p=context.get("profiles",{}).get("away",{}); home_p=context.get("profiles",{}).get("home",{})
    return f'''<div class="kwr" data-testid="nfl-moneyline-page2-war-room">
<div class="kwr-nav"><a class="kwr-back" href="?sport=nfl&market=moneyline">← Back to Games</a><div class="kwr-tabs"><span>Overview</span><span class="active">Analysis</span><span>Matchup</span><span>Odds</span><span>Trends</span></div></div>
<section class="kwr-hero"><div class="kwr-kicker">KYRE SPORTS AI • NFL MONEYLINE WAR ROOM</div><div class="kwr-match"><div class="kwr-team">{_logo(game,"away")}<div><b>{escape(away)}</b><span>{escape(away_abbr)} • {escape(_clean(game.get("away_record")))}</span></div></div><div class="kwr-time"><b>{escape(_clean(game.get("tip_et") or game.get("start_time"),"Kickoff TBD"))}</b><span>{escape(_clean(game.get("venue"),"Venue TBD"))}</span></div><div class="kwr-team right"><div><b>{escape(home)}</b><span>{escape(home_abbr)} • {escape(_clean(game.get("home_record")))}</span></div>{_logo(game,"home")}</div></div>
<div class="kwr-hero-grid"><div class="kwr-price"><span>BEST MONEYLINE • {escape(away_abbr)}</span><b>{escape(_ml(best_away.get("price")))}</b></div><div class="kwr-pick"><div><small>KYRE PICK</small><b>{escape(_clean(verdict.get("pick_team")))}</b><span class="kwr-grade">{escape(_clean(verdict.get("state")))}</span></div><div><small>WIN PROBABILITY</small><div class="prob">{escape(_pct(verdict.get("model_probability"),0))}</div></div></div><div class="kwr-price"><span>BEST MONEYLINE • {escape(home_abbr)}</span><b>{escape(_ml(best_home.get("price")))}</b></div></div></section>
<div class="kwr-metrics"><div class="kwr-metric"><span>MODEL PROBABILITY</span><b>{escape(_pct(verdict.get("model_probability")))}</b></div><div class="kwr-metric"><span>MARKET PROBABILITY</span><b>{escape(_pct(verdict.get("market_probability")))}</b></div><div class="kwr-metric good"><span>MODEL EDGE</span><b>{escape(_pp(verdict.get("edge")))}</b></div><div class="kwr-metric"><span>CONFIDENCE / FINAL STATE</span><b>{escape(_clean(verdict.get("state")))}</b></div></div>
<div class="kwr-grid2"><section class="kwr-panel"><div class="kwr-title"><b>💡 WHY KYRE LIKES THIS SIDE</b><span>Verified evidence only</span></div><div class="kwr-list">{reason_html}</div><div class="kwr-callouts"><div class="kwr-callout"><b>BIGGEST REASON</b><p>{escape(_clean(reasons.get("biggest_reason")))}</p></div><div class="kwr-callout risk"><b>BIGGEST REASON IT COULD LOSE</b><p>{escape(_clean(reasons.get("could_lose")))}</p></div></div></section><section class="kwr-panel"><div class="kwr-title"><b>⚔ TEAM VS TEAM ADVANTAGE</b><span>Frozen profile values</span></div>{_factor_rows(context)}</section></div>
<section class="kwr-panel kwr-history"><div class="kwr-title"><b>🕰 MATCHUP HISTORY</b><span>Last 5 Meetings • verified only</span></div><div class="kwr-history-wrap"><div>{history_main}{full_details}</div><div class="kwr-history-summary"><div class="kwr-summary"><span>SERIES SNAPSHOT</span><b>{escape(_clean(history.get("series_summary")))}</b></div><div class="kwr-summary"><span>AT CURRENT HOME SITE</span><b>{escape(_clean(history.get("current_home_record")))}</b></div><div class="kwr-summary"><span>AVERAGE MARGIN</span><b>{escape(_fmt(history.get("average_margin")))}</b></div><div class="kwr-summary"><span>AVERAGE TOTAL</span><b>{escape(_fmt(history.get("average_combined_score")))}</b></div><div class="kwr-summary"><span>HISTORY INSIGHT</span><b style="font-size:.45rem;line-height:1.45">{escape(hist_insight)}</b></div></div></div></section>
<div class="kwr-grid2"><section class="kwr-panel"><div class="kwr-title"><b>🧭 EXPECTED GAME SCRIPT</b><span>Display context</span></div><div class="kwr-empty" style="padding:0 0 .5rem">{escape(_clean(script.get("summary")))}</div><div class="kwr-paths"><div class="kwr-path"><b>{escape(_clean(verdict.get("pick_abbr")))} WIN PATH</b><p>✓ {pick_path}</p></div><div class="kwr-path upset"><b>UPSET PATH</b><p>• {upset_path}</p></div></div></section><section class="kwr-panel"><div class="kwr-title"><b>🚑 KEY PLAYER AVAILABILITY</b><span>Verified context</span></div><div class="kwr-avail">{_availability_box(avail.get("away") or {},away)}{_availability_box(avail.get("home") or {},home)}</div></section></div>
<section class="kwr-panel" style="margin-top:.55rem"><div class="kwr-title"><b>📊 RECENT FORM & SITUATIONAL INTEL</b><span>Frozen team profiles</span></div><div class="kwr-form"><div class="kwr-team-box"><h4>{escape(away)}</h4><div class="kwr-form-stats"><div class="kwr-form-stat"><span>WIN %</span><b>{escape(_pct(away_prof.get("win_pct")))}</b></div><div class="kwr-form-stat"><span>PF/G</span><b>{escape(_fmt(away_prof.get("ppg")))}</b></div><div class="kwr-form-stat"><span>PA/G</span><b>{escape(_fmt(away_prof.get("papg")))}</b></div></div></div><div class="kwr-team-box"><h4>{escape(home)}</h4><div class="kwr-form-stats"><div class="kwr-form-stat"><span>WIN %</span><b>{escape(_pct(home_prof.get("win_pct")))}</b></div><div class="kwr-form-stat"><span>PF/G</span><b>{escape(_fmt(home_prof.get("ppg")))}</b></div><div class="kwr-form-stat"><span>PA/G</span><b>{escape(_fmt(home_prof.get("papg")))}</b></div></div></div></div></section>
<section class="kwr-panel" style="margin-top:.55rem"><div class="kwr-title"><b>💰 MARKET INTELLIGENCE</b><span>Frozen snapshot • model firewall</span></div><div class="kwr-market"><div class="kwr-summary"><span>MARKET QUALITY</span><b>{escape(_clean(market.get("quality")))}</b></div><div class="kwr-summary"><span>MODEL / MARKET FIREWALL</span><b>0.0% model influence</b></div><div class="kwr-market-board"><div class="kwr-book"><b>SPORTSBOOK</b><span>{escape(away_abbr)}</span><span>{escape(home_abbr)}</span><span>FRESHNESS</span></div>{''.join(books)}</div></div></section>
<div class="kwr-bottom"><section class="kwr-panel"><div class="kwr-title"><b>🎲 5M SIMULATION LAB</b><span>{'CONVERGED' if sim.get('converged') else 'CHECK'}</span></div><div class="kwr-sim"><div class="kwr-donut" style="--p:{donut:.1f}%"></div><div class="kwr-sim-grid"><div class="kwr-sim-stat"><span>{escape(away_abbr)} WIN</span><b>{escape(_pct(away_win,0))}</b></div><div class="kwr-sim-stat"><span>{escape(home_abbr)} WIN</span><b>{escape(_pct(home_win,0))}</b></div><div class="kwr-sim-stat"><span>SIMULATIONS</span><b>{int(sim.get('simulations') or 0):,}</b></div><div class="kwr-sim-stat"><span>MODEL EDGE</span><b>{escape(_pp(verdict.get('edge')))}</b></div></div></div></section><section class="kwr-panel"><div class="kwr-title"><b>⚠ RISK / UPSET RADAR</b><span>Fail-closed</span></div><div class="kwr-risks">{risks}</div></section></div>
<section class="kwr-final"><div><small>🏆 KYRE SPORTS AI FINAL VERDICT</small><b>{escape(_clean(verdict.get("pick_team")))} MONEYLINE • {escape(_clean(verdict.get("state")))}</b></div><div class="kwr-final-metric"><span>WIN PROBABILITY</span><b>{escape(_pct(verdict.get("model_probability"),0))}</b></div><div class="kwr-final-metric"><span>MODEL EDGE</span><b>{escape(_pp(verdict.get("edge")))}</b></div></section></div>'''


def render_context(context: Mapping[str, Any]) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(build_war_room_html(context), unsafe_allow_html=True)
    st.caption("Page 2 is presentation/enrichment only. Frozen Moneyline probability, simulation, market, edge/EV and final grading remain authoritative.")


__all__=["DISPLAY_ONLY","MODEL_VERSION","PRESENTATION_ONLY","SPORTSBOOK_MODEL_INFLUENCE","SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED","build_war_room_html","render_context"]