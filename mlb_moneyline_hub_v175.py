"""MLB Moneyline V17.5 — Step 9 recent team form + schedule context.

Additive presentation/evidence wrapper over permanently frozen V17.4 Step 8.
Pregame cards gain official recent completed-game form and schedule-density context.
Frozen Step 5L live mode remains untouched.

Evidence:
- Official MLB schedule endpoint, strictly completed regular-season games before
  the selected game's official date
- Last 5 / last 10 team results
- Recent run differential
- Current result streak
- Days since previous game
- Games played over the prior 3 / 7 calendar days
- Consecutive game-day streak and recent doubleheader count

Important boundaries:
- Season offense quality remains owned by Step 4
- Bullpen availability remains owned by Step 5
- No player-level recent form is introduced
- Schedule density is descriptive and is NOT added to the recent-form score, to
  avoid double-counting bullpen fatigue/workload

No Moneyline probability, simulation, fair-odds, ranking, candidate selection,
or market math changes. Fail-closed when official completed-game history is
insufficient or cannot be verified as pregame-only.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
import json
import math
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

import mlb_moneyline_hub_v174 as prior
import mlb_moneyline_hub_v170 as pregame

MODEL_VERSION = "V17.5 • MONEYLINE STEP 9 • RECENT TEAM FORM + SCHEDULE CONTEXT"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v174"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_RECENT_GAMES = 8
FORM_WINDOW = 10
SHORT_WINDOW = 5
LOOKBACK_DAYS = 35
MIN_DATA_SCORE = 70

_STEP9_CSS = r"""
<style>
.ml175-step9{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(116,238,170,.28);border-radius:13px;background:linear-gradient(145deg,rgba(7,37,25,.96),rgba(9,17,27,.97));box-shadow:inset 3px 0 #74eeaa}
.ml175-step9-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml175-step9-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#aef2cb}
.ml175-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #536269;background:#1b252a;color:#d0dadf}
.ml175-grade.home{border-color:#31755d;background:#0b3025;color:#98e7bf}.ml175-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml175-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml175-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml175-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ml175-side{border:1px solid rgba(116,238,170,.18);border-radius:10px;background:rgba(8,18,28,.80);padding:8px}.ml175-side.home{text-align:right}.ml175-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml175-side small{color:#718890;font-size:.44rem}
.ml175-score{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #477159;background:#10251a;color:#b8edcd;font-size:.45rem;font-weight:900}.ml175-score.strong{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml175-score.average{border-color:#75621e;background:#30290d;color:#f4dc78}.ml175-score.weak{border-color:#70484a;background:#30191b;color:#f0b0b3}.ml175-score.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml175-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml175-stat{border:1px solid rgba(91,140,166,.16);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml175-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml175-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml175-note{margin-top:7px;border:1px solid rgba(116,238,170,.14);border-radius:8px;padding:6px 7px;background:#0b1d16;color:#aab9b0;font-size:.45rem;line-height:1.42}.ml175-note b{color:#dce8e1}
.ml175-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml175-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(116,238,170,.22);background:#10271a;color:#bdeed0;font-size:.46rem;font-weight:850}.ml175-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml175-grid{grid-template-columns:1fr}.ml175-side.home{text-align:left}.ml175-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml175-step9{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except (TypeError,ValueError):
        return None


def _i(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError,ValueError,OverflowError):
        return 0


def _clamp(value: float,low: float,high: float) -> float:
    return max(low,min(high,float(value)))


def _day(value: Any) -> date | None:
    text=str(value or "")[:10]
    try:
        return datetime.strptime(text,"%Y-%m-%d").date()
    except Exception:
        return None


def _json(url: str) -> dict[str,Any] | None:
    try:
        req=Request(url,headers={"User-Agent":"KyreSportsAI/17.5"})
        with urlopen(req,timeout=8) as response:
            payload=json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload,dict) else None
    except Exception:
        return None


@st.cache_data(ttl=900,show_spinner=False)
def _team_schedule(team_id: int,game_date: str) -> dict[str,Any]:
    current=_day(game_date)
    if not current:
        return {
            "status":"PENDING",
            "games":[],
            "error":"selected game date unavailable",
        }

    start=current-timedelta(days=LOOKBACK_DAYS)
    end=current-timedelta(days=1)
    query=urlencode({
        "sportId":1,
        "teamId":int(team_id),
        "startDate":start.isoformat(),
        "endDate":end.isoformat(),
        "gameType":"R",
        "hydrate":"linescore",
    })
    data=_json(f"https://statsapi.mlb.com/api/v1/schedule?{query}")
    if not data:
        return {
            "status":"PENDING",
            "games":[],
            "error":"official MLB schedule history unavailable",
        }

    rows=[]
    for block in data.get("dates") or []:
        for game in block.get("games") or []:
            status=game.get("status") or {}
            detail=str(status.get("detailedState") or status.get("abstractGameState") or "")
            if "final" not in detail.lower() and "game over" not in detail.lower() and "completed" not in detail.lower():
                continue

            official=str(game.get("officialDate") or block.get("date") or "")[:10]
            d=_day(official)
            if not d or d>=current:
                continue

            teams=game.get("teams") or {}
            away=teams.get("away") or {}
            home=teams.get("home") or {}
            away_id=_i(((away.get("team") or {}).get("id")))
            home_id=_i(((home.get("team") or {}).get("id")))
            tid=int(team_id)
            if tid==away_id:
                team_score=_i(away.get("score"))
                opp_score=_i(home.get("score"))
                side="away"
                opponent_id=home_id
            elif tid==home_id:
                team_score=_i(home.get("score"))
                opp_score=_i(away.get("score"))
                side="home"
                opponent_id=away_id
            else:
                continue

            rows.append({
                "date":official,
                "game_pk":_i(game.get("gamePk")) or None,
                "team_score":team_score,
                "opponent_score":opp_score,
                "run_diff":team_score-opp_score,
                "win":team_score>opp_score,
                "loss":team_score<opp_score,
                "side":side,
                "opponent_id":opponent_id or None,
                "doubleheader":str(game.get("doubleHeader") or "N"),
                "game_number":_i(game.get("gameNumber")) or 1,
                "status":detail,
            })

    rows.sort(key=lambda r:(r["date"],r.get("game_number") or 1,r.get("game_pk") or 0),reverse=True)
    return {
        "status":"VERIFIED" if rows else "PENDING",
        "games":rows,
        "error":"" if rows else "no completed pregame history returned",
    }


def _window_summary(games: list[Mapping[str,Any]],window: int) -> dict[str,Any]:
    rows=list(games or [])[:max(1,int(window))]
    total=len(rows)
    wins=sum(1 for row in rows if row.get("win"))
    losses=sum(1 for row in rows if row.get("loss"))
    team_runs=sum(_i(row.get("team_score")) for row in rows)
    opp_runs=sum(_i(row.get("opponent_score")) for row in rows)
    run_diff=team_runs-opp_runs
    return {
        "games":total,
        "wins":wins,
        "losses":losses,
        "win_pct":wins/total if total>0 else None,
        "team_runs":team_runs,
        "opp_runs":opp_runs,
        "run_diff":run_diff,
        "run_diff_per_game":run_diff/total if total>0 else None,
        "runs_per_game":team_runs/total if total>0 else None,
        "allowed_per_game":opp_runs/total if total>0 else None,
    }


def _streak(games: list[Mapping[str,Any]]) -> dict[str,Any]:
    rows=list(games or [])
    if not rows:
        return {"type":"—","count":0,"label":"NO VERIFIED STREAK"}
    first=rows[0]
    if first.get("win"):
        kind="W"
    elif first.get("loss"):
        kind="L"
    else:
        return {"type":"T","count":1,"label":"T1"}
    count=0
    for row in rows:
        same=(kind=="W" and row.get("win")) or (kind=="L" and row.get("loss"))
        if not same:
            break
        count+=1
    return {"type":kind,"count":count,"label":f"{kind}{count}"}


def _schedule_context(games: list[Mapping[str,Any]],game_date: str) -> dict[str,Any]:
    current=_day(game_date)
    rows=list(games or [])
    if not current:
        return {
            "rest_days":None,
            "games_last3":None,
            "games_last7":None,
            "consecutive_days":None,
            "doubleheaders_last7":None,
            "label":"SCHEDULE CONTEXT PENDING",
        }

    parsed=[(_day(row.get("date")),row) for row in rows]
    parsed=[(d,row) for d,row in parsed if d is not None and d<current]
    if not parsed:
        return {
            "rest_days":None,
            "games_last3":0,
            "games_last7":0,
            "consecutive_days":0,
            "doubleheaders_last7":0,
            "label":"SCHEDULE CONTEXT PENDING",
        }

    last_date=max(d for d,_ in parsed)
    rest_days=max(0,(current-last_date).days-1)
    last3_start=current-timedelta(days=3)
    last7_start=current-timedelta(days=7)
    last3=[row for d,row in parsed if d>=last3_start]
    last7=[row for d,row in parsed if d>=last7_start]

    played_dates={d for d,_ in parsed}
    consecutive=0
    cursor=current-timedelta(days=1)
    while cursor in played_dates:
        consecutive+=1
        cursor-=timedelta(days=1)

    by_date={}
    for d,row in parsed:
        if d<last7_start:
            continue
        by_date.setdefault(d,0)
        by_date[d]+=1
    doubleheaders=sum(1 for count in by_date.values() if count>=2)

    if rest_days>=2:
        label="EXTENDED REST"
    elif len(last7)>=8 or consecutive>=8:
        label="HEAVY SCHEDULE LOAD"
    elif len(last3)>=4 or consecutive>=6:
        label="DENSE SCHEDULE"
    elif rest_days>=1:
        label="RESTED"
    else:
        label="NORMAL SCHEDULE"

    return {
        "rest_days":rest_days,
        "games_last3":len(last3),
        "games_last7":len(last7),
        "consecutive_days":consecutive,
        "doubleheaders_last7":doubleheaders,
        "label":label,
    }


def _form_score(l5: Mapping[str,Any],l10: Mapping[str,Any]) -> dict[str,Any]:
    if int(l10.get("games") or 0)<MIN_RECENT_GAMES:
        return {
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
        }

    l10_wp=_f(l10.get("win_pct"))
    l10_rd=_f(l10.get("run_diff_per_game"))
    l5_wp=_f(l5.get("win_pct"))
    if l10_wp is None or l10_rd is None or l5_wp is None:
        return {
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
        }

    win_signal=_clamp((l10_wp-0.500)/0.250,-1.0,1.0)
    run_signal=_clamp(l10_rd/2.5,-1.0,1.0)
    short_signal=_clamp((l5_wp-0.500)/0.300,-1.0,1.0)
    signal=0.45*win_signal+0.35*run_signal+0.20*short_signal
    score=int(round(_clamp(50.0+24.0*signal,26.0,74.0)))

    if score>=64:
        label,cls="HOT TEAM FORM","strong"
    elif score>=57:
        label,cls="POSITIVE TEAM FORM","strong"
    elif score>=44:
        label,cls="NEUTRAL TEAM FORM","average"
    elif score>=36:
        label,cls="COOLING TEAM FORM","weak"
    else:
        label,cls="COLD TEAM FORM","weak"

    return {
        "score":score,
        "label":label,
        "label_cls":cls,
    }


def _data_score(payload: Mapping[str,Any],l10: Mapping[str,Any],schedule: Mapping[str,Any],game_date: str) -> int:
    score=0
    asof_ready=_day(game_date) is not None
    if payload.get("status")=="VERIFIED":
        score+=30
    games=int(l10.get("games") or 0)
    score+=int(round(30*_clamp(games/FORM_WINDOW,0.0,1.0)))
    if l10.get("win_pct") is not None:
        score+=15
    if l10.get("run_diff_per_game") is not None:
        score+=15
    if schedule.get("rest_days") is not None:
        score+=5
    if asof_ready:
        score+=5
    score=int(_clamp(score,0,100))
    # Pregame as-of identity is a hard gate, not a cosmetic data-quality bonus.
    # Without an official selected date we cannot prove current/future results were excluded.
    return score if asof_ready else min(score,MIN_DATA_SCORE-1)


def _team_context(team_id: Any,team_name: Any,game_date: str) -> dict[str,Any]:
    tid=_i(team_id)
    if not tid:
        return {
            "team_id":None,
            "team_name":str(team_name or "Team"),
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "l5":{},
            "l10":{},
            "streak":{},
            "schedule":{},
            "data_score":0,
            "reason":"Official MLB team ID unavailable.",
        }

    payload=_team_schedule(tid,game_date)
    games=list(payload.get("games") or [])
    l5=_window_summary(games,SHORT_WINDOW)
    l10=_window_summary(games,FORM_WINDOW)
    streak=_streak(games)
    schedule=_schedule_context(games,game_date)
    graded=_form_score(l5,l10)
    data_score=_data_score(payload,l10,schedule,game_date)

    sufficient=graded.get("score") is not None and data_score>=MIN_DATA_SCORE
    if sufficient:
        score=graded.get("score")
        label=graded.get("label")
        cls=graded.get("label_cls")
        reason=""
    else:
        score=None
        label="DATA LIMITED / PENDING"
        cls="limited"
        if payload.get("status")!="VERIFIED":
            reason="Official MLB completed-game history unavailable."
        elif int(l10.get("games") or 0)<MIN_RECENT_GAMES:
            reason=f"Fewer than {MIN_RECENT_GAMES} verified completed games before the selected game."
        elif _day(game_date) is None:
            reason="Selected official game date unavailable for pregame as-of filtering."
        else:
            reason="Recent-form evidence did not clear the data-quality threshold."

    return {
        "team_id":tid,
        "team_name":str(team_name or f"Team {tid}"),
        "score":score,
        "label":label,
        "label_cls":cls,
        "l5":l5,
        "l10":l10,
        "streak":streak,
        "schedule":schedule,
        "data_score":data_score,
        "games_available":len(games),
        "reason":reason,
    }


def _overall_grade(away: Mapping[str,Any],home: Mapping[str,Any]) -> tuple[str,str,float|None]:
    a=_f(away.get("score"))
    h=_f(home.get("score"))
    if a is None or h is None:
        return "DATA LIMITED / PENDING","limited",None
    edge=h-a
    if edge>=10:
        return "STRONG HOME RECENT-FORM EDGE","home",edge
    if edge>=4:
        return "HOME RECENT-FORM EDGE","home",edge
    if edge<=-10:
        return "STRONG AWAY RECENT-FORM EDGE","away",edge
    if edge<=-4:
        return "AWAY RECENT-FORM EDGE","away",edge
    return "RECENT FORM CLOSE","neutral",edge


def _build_context(rows: Mapping[int,Mapping[str,Any]]) -> dict[int,dict[str,Any]]:
    out={}
    cache={}
    for pk,row in (rows or {}).items():
        game_date=str(row.get("game_date") or "")[:10]
        item={}
        for side in ("away","home"):
            tid=_i(row.get(f"{side}_team_id"))
            key=(tid,game_date)
            if key not in cache:
                cache[key]=_team_context(
                    tid,
                    row.get(f"{side}_team") or row.get(f"{side}_name"),
                    game_date,
                )
            item[side]=cache[key]
        ipk=_i(pk)
        if ipk:
            out[ipk]=item
    return out


def _fmt(value: Any,digits: int=2,suffix: str="") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _record(summary: Mapping[str,Any]) -> str:
    games=int(summary.get("games") or 0)
    if games<=0:
        return "N/A"
    return f"{int(summary.get('wins') or 0)}-{int(summary.get('losses') or 0)}"


def _side_html(side: Mapping[str,Any],home: bool=False) -> str:
    l5=side.get("l5") or {}
    l10=side.get("l10") or {}
    schedule=side.get("schedule") or {}
    streak=side.get("streak") or {}
    score=side.get("score")
    score_text="N/A" if score is None else f"{int(score)}/100"

    return (
        f'<div class="ml175-side {"home" if home else ""}">'
        f'<h4>{escape(str(side.get("team_name") or "Team"))}</h4>'
        f'<small>{escape(str(streak.get("label") or "—"))} • {escape(str(schedule.get("label") or "SCHEDULE PENDING"))}</small>'
        f'<div class="ml175-score {escape(str(side.get("label_cls") or "limited"))}">{escape(str(side.get("label") or "DATA LIMITED / PENDING"))} • {escape(score_text)}</div>'
        '<div class="ml175-stats">'
        f'<div class="ml175-stat"><b>{escape(_record(l5))}</b><span>L5 record</span></div>'
        f'<div class="ml175-stat"><b>{escape(_record(l10))}</b><span>L10 record</span></div>'
        f'<div class="ml175-stat"><b>{_fmt(l10.get("run_diff_per_game"),2)}</b><span>L10 run diff/G</span></div>'
        f'<div class="ml175-stat"><b>{_fmt(l10.get("runs_per_game"),2)}</b><span>L10 R/G</span></div>'
        '</div>'
        '<div class="ml175-stats">'
        f'<div class="ml175-stat"><b>{_fmt(schedule.get("rest_days"),0)}</b><span>Rest days</span></div>'
        f'<div class="ml175-stat"><b>{_fmt(schedule.get("games_last3"),0)}</b><span>Games last 3d</span></div>'
        f'<div class="ml175-stat"><b>{_fmt(schedule.get("games_last7"),0)}</b><span>Games last 7d</span></div>'
        f'<div class="ml175-stat"><b>{_fmt(schedule.get("consecutive_days"),0)}</b><span>Consecutive days</span></div>'
        '</div>'
        '<div class="ml175-note">'
        f'<b>Schedule context:</b> {int(schedule.get("doubleheaders_last7") or 0)} doubleheader date(s) in prior 7 days. '
        'Schedule density is descriptive only and does not change this recent-form score, preventing bullpen-fatigue double counting.'
        '</div>'
        f'<div class="ml175-source">Data quality {int(side.get("data_score") or 0)}/100 • {int(side.get("games_available") or 0)} completed games found in lookback. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str,Any]) -> str:
    away=context.get("away") or {}
    home=context.get("home") or {}
    grade,grade_cls,edge=_overall_grade(away,home)
    edge_text="N/A" if edge is None else f"{abs(float(edge)):.1f} pts"
    return (
        '<div class="ml175-step9">'
        '<div class="ml175-step9-head">'
        '<span class="ml175-step9-title">STEP 9 • RECENT TEAM FORM + SCHEDULE CONTEXT</span>'
        f'<span class="ml175-grade {escape(grade_cls)}">{escape(grade)}</span>'
        '</div>'
        '<div class="ml175-grid">'
        f'{_side_html(away,False)}'
        f'{_side_html(home,True)}'
        '</div>'
        '<div class="ml175-pills">'
        f'<span class="ml175-pill">RECENT-FORM EDGE • {escape(edge_text)}</span>'
        '<span class="ml175-pill">STRICTLY PRE-GAME COMPLETED RESULTS</span>'
        '<span class="ml175-pill">SCHEDULE LOAD DESCRIPTIVE ONLY</span>'
        '<span class="ml175-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        '<div class="ml175-source">Official MLB completed regular-season schedule history only. Current/live/future games are excluded by official-date cutoff.</div>'
        '</div>'
    )


def _inject(card: str,html: str) -> str:
    text=str(card or "")
    if not html or "ks-pick-card" not in text or "ml175-step9" in text:
        return text
    return text[:-6]+html+"</div>" if text.endswith("</div>") else text+html


_FROZEN_STEP8_RENDERER=prior._renderer


def _renderer(original,rows,lineups):
    step8=_FROZEN_STEP8_RENDERER(original,rows,lineups)
    contexts=_build_context(rows)

    def wrapped(results,status_info,team_logo,h):
        ordered=list(results or [])[:5]
        cursor={"i":0}
        original_markdown=st.markdown

        def capture(body: Any,*args: Any,**kwargs: Any):
            text=str(body or "")
            if "ks-pick-card" in text and cursor["i"]<len(ordered):
                result=ordered[cursor["i"]]
                cursor["i"]+=1
                pk=_i(result.get("game_pk"))
                text=_inject(text,_html(contexts.get(pk) or {}))
            return original_markdown(text,*args,**kwargs)

        st.markdown=capture
        try:
            return step8(results,status_info,team_logo,h)
        finally:
            st.markdown=original_markdown

    return wrapped


def _render_pregame_with_step9(games_df,section_header,status_info,team_logo,h):
    original_renderer=pregame._renderer
    pregame._renderer=_renderer
    try:
        return pregame.render_moneyline_hub(games_df,section_header,status_info,team_logo,h)
    finally:
        pregame._renderer=original_renderer


def render_moneyline_hub(games_df,section_header,status_info,team_logo,h):
    """Preserve frozen Step 5L live mode while extending only pregame evidence."""
    st.markdown(_STEP9_CSS,unsafe_allow_html=True)
    original_step8_pregame=prior._render_pregame_with_step8
    prior._render_pregame_with_step8=_render_pregame_with_step9
    try:
        return prior.render_moneyline_hub(games_df,section_header,status_info,team_logo,h)
    finally:
        prior._render_pregame_with_step8=original_step8_pregame


__all__=[
    "FORM_WINDOW",
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "LOOKBACK_DAYS",
    "MIN_DATA_SCORE",
    "MIN_RECENT_GAMES",
    "MODEL_VERSION",
    "SHORT_WINDOW",
    "_build_context",
    "_data_score",
    "_form_score",
    "_overall_grade",
    "_schedule_context",
    "_streak",
    "_team_context",
    "_team_schedule",
    "_window_summary",
    "render_moneyline_hub",
]
