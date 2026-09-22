"""MLB Moneyline V17.4 — Step 8 defense + baserunning.

Additive presentation/evidence wrapper over permanently frozen V17.3 Step 7.
Pregame cards gain official team fielding execution plus a stolen-base baserunning
proxy. Frozen Step 5L live mode remains untouched.

Evidence:
- Official MLB team season fielding stats
- Official MLB team season stolen-base / caught-stealing stats

Important boundaries:
- Pitching prevention is not reused here; this is fielding execution only.
- Offensive production is not reused here; baserunning is isolated to SB/CS.
- SB/CS is explicitly labeled a baserunning proxy, not complete baserunning value.

No Moneyline probability, simulation, fair-odds, ranking, candidate selection,
or market math changes. Fail-closed when team defense/baserunning evidence does
not clear minimum sample and data-quality thresholds.
"""
from __future__ import annotations

from html import escape
import json
import math
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

import mlb_moneyline_hub_v173 as prior
import mlb_moneyline_hub_v170 as pregame

MODEL_VERSION = "V17.4 • MONEYLINE STEP 8 • DEFENSE + BASERUNNING"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v173"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_GAMES = 30
MIN_SB_ATTEMPTS = 10
MIN_DATA_SCORE = 65

FIELDING_PCT_BASELINE = 0.985
ERRORS_PER_GAME_BASELINE = 0.55
SB_SUCCESS_BASELINE = 0.75
SB_ATTEMPTS_PER_GAME_BASELINE = 0.80

_STEP8_CSS = r"""
<style>
.ml174-step8{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(106,219,255,.28);border-radius:13px;background:linear-gradient(145deg,rgba(7,29,38,.96),rgba(9,17,27,.97));box-shadow:inset 3px 0 #65d8ff}
.ml174-step8-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml174-step8-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#a4eaff}
.ml174-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #536269;background:#1b252a;color:#d0dadf}
.ml174-grade.home{border-color:#31755d;background:#0b3025;color:#98e7bf}.ml174-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml174-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml174-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml174-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ml174-side{border:1px solid rgba(106,219,255,.18);border-radius:10px;background:rgba(8,18,28,.80);padding:8px}.ml174-side.home{text-align:right}.ml174-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml174-side small{color:#718890;font-size:.44rem}
.ml174-score{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #4a6d79;background:#10232a;color:#bceaf7;font-size:.45rem;font-weight:900}.ml174-score.strong{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml174-score.average{border-color:#75621e;background:#30290d;color:#f4dc78}.ml174-score.weak{border-color:#70484a;background:#30191b;color:#f0b0b3}.ml174-score.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml174-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml174-stat{border:1px solid rgba(91,140,166,.16);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml174-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml174-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml174-note{margin-top:7px;border:1px solid rgba(106,219,255,.14);border-radius:8px;padding:6px 7px;background:#0b1723;color:#aab9c4;font-size:.45rem;line-height:1.42}.ml174-note b{color:#dce8ef}
.ml174-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml174-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(106,219,255,.22);background:#10222b;color:#bde9f5;font-size:.46rem;font-weight:850}.ml174-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml174-grid{grid-template-columns:1fr}.ml174-side.home{text-align:left}.ml174-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml174-step8{padding:9px}}
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


def _rate(value: Any) -> float | None:
    val=_f(value)
    if val is None:
        return None
    if val>1.0:
        val/=100.0
    return max(0.0,min(1.0,val))


def _clamp(value: float,low: float,high: float) -> float:
    return max(low,min(high,float(value)))


def _json(url: str) -> dict[str,Any] | None:
    try:
        req=Request(url,headers={"User-Agent":"KyreSportsAI/17.4"})
        with urlopen(req,timeout=8) as response:
            payload=json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload,dict) else None
    except Exception:
        return None


@st.cache_data(ttl=1800,show_spinner=False)
def _team_stat(team_id: int,group: str) -> dict[str,Any] | None:
    query=urlencode({"stats":"season","group":str(group),"season":SEASON,"gameType":"R"})
    data=_json(f"https://statsapi.mlb.com/api/v1/teams/{int(team_id)}/stats?{query}")
    if not data:
        return None
    try:
        blocks=data.get("stats") or []
        splits=(blocks[0].get("splits") or []) if blocks else []
        stat=(splits[0].get("stat") or {}) if splits else {}
        return dict(stat) if isinstance(stat,dict) else None
    except Exception:
        return None


def _fielding_metrics(stat: Mapping[str,Any] | None) -> dict[str,Any]:
    stat=stat or {}
    games=_i(stat.get("gamesPlayed") or stat.get("games"))
    errors=_i(stat.get("errors"))
    fpct=_f(stat.get("fielding") or stat.get("fieldingPercentage"))
    if fpct is not None and fpct>1.0:
        fpct/=1000.0
    if fpct is None:
        putouts=_i(stat.get("putOuts"))
        assists=_i(stat.get("assists"))
        chances=putouts+assists+errors
        fpct=(putouts+assists)/chances if chances>0 else None
    dps=_i(stat.get("doublePlays"))
    return {
        "games":games,
        "errors":errors,
        "fielding_pct":fpct,
        "errors_per_game":errors/games if games>0 else None,
        "double_plays":dps,
        "double_plays_per_game":dps/games if games>0 else None,
    }


def _baserunning_metrics(stat: Mapping[str,Any] | None) -> dict[str,Any]:
    stat=stat or {}
    games=_i(stat.get("gamesPlayed"))
    sb=_i(stat.get("stolenBases"))
    cs=_i(stat.get("caughtStealing"))
    attempts=sb+cs
    success=_rate(stat.get("stolenBasePercentage"))
    if success is None and attempts>0:
        success=sb/attempts
    return {
        "games":games,
        "stolen_bases":sb,
        "caught_stealing":cs,
        "attempts":attempts,
        "success_rate":success,
        "attempts_per_game":attempts/games if games>0 else None,
        "sb_per_game":sb/games if games>0 else None,
    }


def _defense_score(metrics: Mapping[str,Any]) -> dict[str,Any]:
    games=int(metrics.get("games") or 0)
    fpct=_f(metrics.get("fielding_pct"))
    epg=_f(metrics.get("errors_per_game"))
    if games<MIN_GAMES or fpct is None or epg is None:
        return {"score":None,"signal":None,"reliability":0.0}

    fpct_signal=_clamp((fpct-FIELDING_PCT_BASELINE)/0.010,-1.0,1.0)
    error_signal=_clamp((ERRORS_PER_GAME_BASELINE-epg)/0.35,-1.0,1.0)
    signal=0.58*fpct_signal+0.42*error_signal
    reliability=_clamp(games/90.0,0.0,1.0)
    score=int(round(_clamp(50.0+22.0*signal*reliability,28.0,72.0)))
    return {"score":score,"signal":signal,"reliability":reliability}


def _baserunning_score(metrics: Mapping[str,Any]) -> dict[str,Any]:
    games=int(metrics.get("games") or 0)
    attempts=int(metrics.get("attempts") or 0)
    success=_f(metrics.get("success_rate"))
    apg=_f(metrics.get("attempts_per_game"))
    if games<MIN_GAMES or attempts<MIN_SB_ATTEMPTS or success is None or apg is None:
        return {"score":None,"signal":None,"reliability":0.0}

    efficiency=_clamp((success-SB_SUCCESS_BASELINE)/0.15,-1.0,1.0)
    activity=_clamp(apg/SB_ATTEMPTS_PER_GAME_BASELINE,0.0,1.5)
    activity_weight=0.65+0.35*min(activity,1.0)
    signal=_clamp(efficiency*activity_weight,-1.0,1.0)
    reliability=min(
        _clamp(games/90.0,0.0,1.0),
        _clamp(attempts/80.0,0.0,1.0),
    )
    score=int(round(_clamp(50.0+20.0*signal*reliability,30.0,70.0)))
    return {"score":score,"signal":signal,"reliability":reliability}


def _composite(defense: Mapping[str,Any],baserunning: Mapping[str,Any]) -> dict[str,Any]:
    d=_f(defense.get("score"))
    b=_f(baserunning.get("score"))
    dr=float(defense.get("reliability") or 0.0)
    br=float(baserunning.get("reliability") or 0.0)
    if d is None or b is None:
        return {
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "coverage":0.0,
        }

    dweight=0.62*dr
    bweight=0.38*br
    denom=dweight+bweight
    if denom<=0:
        return {
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "coverage":0.0,
        }

    score=int(round((d*dweight+b*bweight)/denom))
    coverage=_clamp(dweight+bweight,0.0,1.0)

    if score>=61:
        label,cls="STRONG DEFENSE + BASERUNNING","strong"
    elif score>=55:
        label,cls="ABOVE-AVERAGE DEFENSE + BASERUNNING","strong"
    elif score>=45:
        label,cls="AVERAGE DEFENSE + BASERUNNING","average"
    elif score>=39:
        label,cls="BELOW-AVERAGE DEFENSE + BASERUNNING","weak"
    else:
        label,cls="WEAK DEFENSE + BASERUNNING","weak"

    return {
        "score":score,
        "label":label,
        "label_cls":cls,
        "coverage":coverage,
    }


def _data_score(team_id: int,fielding: Mapping[str,Any],running: Mapping[str,Any],defense: Mapping[str,Any],baserunning: Mapping[str,Any]) -> int:
    score=10 if team_id else 0
    games=max(int(fielding.get("games") or 0),int(running.get("games") or 0))
    score+=10 if games>=MIN_GAMES else int(round(10*_clamp(games/MIN_GAMES,0.0,1.0)))

    if fielding.get("fielding_pct") is not None:
        score+=22
    if fielding.get("errors_per_game") is not None:
        score+=18

    attempts=int(running.get("attempts") or 0)
    if running.get("success_rate") is not None:
        score+=18
    if running.get("attempts_per_game") is not None:
        score+=12
    score+=int(round(10*_clamp(attempts/max(MIN_SB_ATTEMPTS,1),0.0,1.0)))

    if defense.get("score") is None:
        score=min(score,64)
    if baserunning.get("score") is None:
        score=min(score,64)

    return int(_clamp(score,0,100))


def _team_context(team_id: Any,team_name: Any) -> dict[str,Any]:
    tid=_i(team_id)
    if not tid:
        return {
            "team_id":None,
            "team_name":str(team_name or "Team"),
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "fielding":{},
            "running":{},
            "defense":{},
            "baserunning":{},
            "data_score":0,
            "reason":"Official MLB team ID unavailable.",
        }

    fielding_stat=_team_stat(tid,"fielding")
    hitting_stat=_team_stat(tid,"hitting")
    fielding=_fielding_metrics(fielding_stat)
    running=_baserunning_metrics(hitting_stat)
    defense=_defense_score(fielding)
    baserunning=_baserunning_score(running)
    combined=_composite(defense,baserunning)
    data_score=_data_score(tid,fielding,running,defense,baserunning)

    sufficient=combined.get("score") is not None and data_score>=MIN_DATA_SCORE
    if sufficient:
        score=combined.get("score")
        label=combined.get("label")
        cls=combined.get("label_cls")
        reason=""
    else:
        score=None
        label="DATA LIMITED / PENDING"
        cls="limited"
        if max(int(fielding.get("games") or 0),int(running.get("games") or 0))<MIN_GAMES:
            reason=f"Team sample is below the {MIN_GAMES}-game fail-closed threshold."
        elif defense.get("score") is None:
            reason="Official fielding evidence is incomplete."
        elif baserunning.get("score") is None:
            reason="Official SB/CS baserunning sample is incomplete."
        else:
            reason="Defense/baserunning evidence did not clear the data-quality threshold."

    return {
        "team_id":tid,
        "team_name":str(team_name or f"Team {tid}"),
        "score":score,
        "label":label,
        "label_cls":cls,
        "fielding":fielding,
        "running":running,
        "defense":defense,
        "baserunning":baserunning,
        "data_score":data_score,
        "coverage":combined.get("coverage"),
        "reason":reason,
    }


def _overall_grade(away: Mapping[str,Any],home: Mapping[str,Any]) -> tuple[str,str,float|None]:
    a=_f(away.get("score"))
    h=_f(home.get("score"))
    if a is None or h is None:
        return "DATA LIMITED / PENDING","limited",None
    edge=h-a
    if edge>=10:
        return "STRONG HOME DEFENSE/BASERUNNING EDGE","home",edge
    if edge>=4:
        return "HOME DEFENSE/BASERUNNING EDGE","home",edge
    if edge<=-10:
        return "STRONG AWAY DEFENSE/BASERUNNING EDGE","away",edge
    if edge<=-4:
        return "AWAY DEFENSE/BASERUNNING EDGE","away",edge
    return "DEFENSE/BASERUNNING CLOSE","neutral",edge


def _build_context(rows: Mapping[int,Mapping[str,Any]]) -> dict[int,dict[str,Any]]:
    out={}
    cache={}
    for pk,row in (rows or {}).items():
        item={}
        for side in ("away","home"):
            tid=_i(row.get(f"{side}_team_id"))
            if tid not in cache:
                cache[tid]=_team_context(
                    tid,
                    row.get(f"{side}_team") or row.get(f"{side}_name"),
                )
            item[side]=cache[tid]
        ipk=_i(pk)
        if ipk:
            out[ipk]=item
    return out


def _fmt(value: Any,digits: int=2,suffix: str="") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _side_html(side: Mapping[str,Any],home: bool=False) -> str:
    f=side.get("fielding") or {}
    r=side.get("running") or {}
    d=side.get("defense") or {}
    b=side.get("baserunning") or {}
    score=side.get("score")
    score_text="N/A" if score is None else f"{int(score)}/100"
    sbpct=(float(r.get("success_rate"))*100) if r.get("success_rate") is not None else None

    return (
        f'<div class="ml174-side {"home" if home else ""}">'
        f'<h4>{escape(str(side.get("team_name") or "Team"))}</h4>'
        f'<small>Fielding execution + SB/CS baserunning proxy</small>'
        f'<div class="ml174-score {escape(str(side.get("label_cls") or "limited"))}">{escape(str(side.get("label") or "DATA LIMITED / PENDING"))} • {escape(score_text)}</div>'
        '<div class="ml174-stats">'
        f'<div class="ml174-stat"><b>{_fmt(f.get("fielding_pct"),3)}</b><span>Fielding %</span></div>'
        f'<div class="ml174-stat"><b>{_fmt(f.get("errors_per_game"),2)}</b><span>Errors/G</span></div>'
        f'<div class="ml174-stat"><b>{_fmt(d.get("score"),0)}</b><span>Defense score</span></div>'
        f'<div class="ml174-stat"><b>{int(f.get("double_plays") or 0)}</b><span>Double plays</span></div>'
        '</div>'
        '<div class="ml174-stats">'
        f'<div class="ml174-stat"><b>{int(r.get("stolen_bases") or 0)}</b><span>SB</span></div>'
        f'<div class="ml174-stat"><b>{int(r.get("caught_stealing") or 0)}</b><span>CS</span></div>'
        f'<div class="ml174-stat"><b>{_fmt(sbpct,1,"%")}</b><span>SB success</span></div>'
        f'<div class="ml174-stat"><b>{_fmt(b.get("score"),0)}</b><span>Baserun score</span></div>'
        '</div>'
        '<div class="ml174-note">'
        '<b>Baserunning scope:</b> this is a stolen-base/caught-stealing proxy only. '
        'It does not claim to measure all first-to-third, tag-up, or advancement value.'
        '</div>'
        f'<div class="ml174-source">Data quality {int(side.get("data_score") or 0)}/100. Pitching prevention is excluded from this defense score, and offensive run production is excluded from the baserunning score. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str,Any]) -> str:
    away=context.get("away") or {}
    home=context.get("home") or {}
    grade,grade_cls,edge=_overall_grade(away,home)
    edge_text="N/A" if edge is None else f"{abs(float(edge)):.1f} pts"
    return (
        '<div class="ml174-step8">'
        '<div class="ml174-step8-head">'
        '<span class="ml174-step8-title">STEP 8 • DEFENSE + BASERUNNING</span>'
        f'<span class="ml174-grade {escape(grade_cls)}">{escape(grade)}</span>'
        '</div>'
        '<div class="ml174-grid">'
        f'{_side_html(away,False)}'
        f'{_side_html(home,True)}'
        '</div>'
        '<div class="ml174-pills">'
        f'<span class="ml174-pill">TEAM EDGE • {escape(edge_text)}</span>'
        '<span class="ml174-pill">FIELDING ONLY • NO PITCHING DOUBLE COUNT</span>'
        '<span class="ml174-pill">SB/CS BASERUNNING PROXY</span>'
        '<span class="ml174-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        '<div class="ml174-source">Official MLB team season fielding + hitting baserunning statistics. Defense and baserunning remain descriptive until final probability/calibration.</div>'
        '</div>'
    )


def _inject(card: str,html: str) -> str:
    text=str(card or "")
    if not html or "ks-pick-card" not in text or "ml174-step8" in text:
        return text
    return text[:-6]+html+"</div>" if text.endswith("</div>") else text+html


_FROZEN_STEP7_RENDERER=prior._renderer


def _renderer(original,rows,lineups):
    step7=_FROZEN_STEP7_RENDERER(original,rows,lineups)
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
            return step7(results,status_info,team_logo,h)
        finally:
            st.markdown=original_markdown

    return wrapped


def _render_pregame_with_step8(games_df,section_header,status_info,team_logo,h):
    original_renderer=pregame._renderer
    pregame._renderer=_renderer
    try:
        return pregame.render_moneyline_hub(games_df,section_header,status_info,team_logo,h)
    finally:
        pregame._renderer=original_renderer


def render_moneyline_hub(games_df,section_header,status_info,team_logo,h):
    """Preserve frozen Step 5L live mode while extending only pregame evidence."""
    st.markdown(_STEP8_CSS,unsafe_allow_html=True)
    original_step7_pregame=prior._render_pregame_with_step7
    prior._render_pregame_with_step7=_render_pregame_with_step8
    try:
        return prior.render_moneyline_hub(games_df,section_header,status_info,team_logo,h)
    finally:
        prior._render_pregame_with_step7=original_step7_pregame


__all__=[
    "FIELDING_PCT_BASELINE",
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MIN_DATA_SCORE",
    "MIN_GAMES",
    "MIN_SB_ATTEMPTS",
    "MODEL_VERSION",
    "SB_ATTEMPTS_PER_GAME_BASELINE",
    "SB_SUCCESS_BASELINE",
    "_baserunning_metrics",
    "_baserunning_score",
    "_build_context",
    "_composite",
    "_data_score",
    "_defense_score",
    "_fielding_metrics",
    "_overall_grade",
    "_team_context",
    "render_moneyline_hub",
]
