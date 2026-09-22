"""MLB Moneyline V16.9 — Step 4 team offense quality.

Presentation/evidence wrapper over permanently frozen V16.8. Step 4 adds a
season-long team offense baseline from official MLB team hitting statistics.
It is intentionally separate from Step 3 matchup evidence and Step 6 lineup
strength/missing-player adjustments.

No Moneyline probability, simulation, fair-odds, ranking, candidate selection,
or market math changes. Fail-closed when team hitting evidence is incomplete.
"""
from __future__ import annotations

from html import escape
import json
import math
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st
import mlb_moneyline_hub_v168 as prior

MODEL_VERSION = "V16.9 • MONEYLINE STEP 4 • OFFENSE QUALITY"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v168"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_GAMES = 10
MIN_COMPONENTS = 4

_STEP4_CSS = r"""
<style>
.ml169-step4{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(55,184,151,.27);border-radius:13px;background:linear-gradient(145deg,rgba(7,28,24,.95),rgba(7,17,27,.97));box-shadow:inset 3px 0 #3fd2aa}
.ml169-step4-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml169-step4-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#82e8cb}
.ml169-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #536269;background:#1b252a;color:#d0dadf}
.ml169-grade.home{border-color:#31755d;background:#0b3025;color:#98e7bf}.ml169-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml169-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml169-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml169-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ml169-side{border:1px solid rgba(55,184,151,.20);border-radius:10px;background:rgba(8,18,24,.80);padding:8px}.ml169-side.home{text-align:right}.ml169-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml169-side small{color:#718890;font-size:.44rem}.ml169-score{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #42695c;background:#102820;color:#a7e7ce;font-size:.45rem;font-weight:900}.ml169-score.strong{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml169-score.average{border-color:#75621e;background:#30290d;color:#f4dc78}.ml169-score.weak{border-color:#70484a;background:#30191b;color:#f0b0b3}.ml169-score.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml169-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml169-stat{border:1px solid rgba(91,140,166,.16);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml169-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml169-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml169-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml169-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(55,184,151,.22);background:#0d241e;color:#a8ddcd;font-size:.46rem;font-weight:850}.ml169-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml169-grid{grid-template-columns:1fr}.ml169-side.home{text-align:left}.ml169-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml169-step4{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except (TypeError,ValueError):
        return None


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError,ValueError,OverflowError):
        return None


def _rate(value: Any) -> float | None:
    val=_f(value)
    if val is None:
        return None
    if abs(val)>1.0:
        val/=100.0
    return max(0.0,min(1.0,val))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low,min(high,float(value)))


def _json(url: str) -> dict[str,Any] | None:
    try:
        req=Request(url,headers={"User-Agent":"KyreSportsAI/16.9"})
        with urlopen(req,timeout=8) as response:
            payload=json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload,dict) else None
    except Exception:
        return None


@st.cache_data(ttl=900,show_spinner=False)
def _team_hitting(team_id: int) -> dict[str,Any] | None:
    query=urlencode({"stats":"season","group":"hitting","season":SEASON,"gameType":"R"})
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


def _metrics(stat: Mapping[str,Any] | None) -> dict[str,Any]:
    if not stat:
        return {}
    games=_i(stat.get("gamesPlayed")) or 0
    runs=_i(stat.get("runs")) or 0
    hr=_i(stat.get("homeRuns")) or 0
    pa=_i(stat.get("plateAppearances")) or 0
    bb=_i(stat.get("baseOnBalls")) or 0
    so=_i(stat.get("strikeOuts")) or 0
    avg=_rate(stat.get("avg"))
    obp=_rate(stat.get("obp"))
    slg=_rate(stat.get("slg"))
    ops=_f(stat.get("ops"))
    if ops is not None and ops>2:
        ops/=1000.0
    return {
        "games":games,
        "runs":runs,
        "rpg":runs/games if games>0 else None,
        "avg":avg,
        "obp":obp,
        "slg":slg,
        "ops":ops,
        "hr":hr,
        "hrpg":hr/games if games>0 else None,
        "pa":pa,
        "bb_pct":bb/pa if pa>0 else None,
        "k_pct":so/pa if pa>0 else None,
    }


def _signal(value: float | None, center: float, scale: float, high_good: bool=True) -> float | None:
    if value is None:
        return None
    raw=(float(value)-center)/scale
    if not high_good:
        raw*=-1.0
    return _clamp(raw,-1.0,1.0)


def _score(metrics: Mapping[str,Any]) -> dict[str,Any]:
    pieces=[
        (_signal(metrics.get("rpg"),4.40,1.20,True),0.28,"R/G"),
        (_signal(metrics.get("ops"),0.720,0.120,True),0.24,"OPS"),
        (_signal(metrics.get("obp"),0.320,0.060,True),0.12,"OBP"),
        (_signal(metrics.get("slg"),0.400,0.100,True),0.12,"SLG"),
        (_signal(metrics.get("hrpg"),1.15,0.75,True),0.10,"HR/G"),
        (_signal(metrics.get("bb_pct"),0.085,0.050,True),0.07,"BB%"),
        (_signal(metrics.get("k_pct"),0.225,0.090,False),0.07,"K%"),
    ]
    usable=[(float(sig),weight,name) for sig,weight,name in pieces if sig is not None]
    games=int(metrics.get("games") or 0)
    if games<MIN_GAMES or len(usable)<MIN_COMPONENTS:
        return {
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "components":len(usable),
            "games":games,
        }
    denom=sum(weight for _,weight,_ in usable)
    combined=sum(sig*weight for sig,weight,_ in usable)/denom
    score=int(round(_clamp(50.0+25.0*combined,25.0,75.0)))
    if score>=64:
        label,cls="ELITE OFFENSE","strong"
    elif score>=57:
        label,cls="STRONG OFFENSE","strong"
    elif score>=44:
        label,cls="AVERAGE OFFENSE","average"
    elif score>=36:
        label,cls="WEAK OFFENSE","weak"
    else:
        label,cls="VERY WEAK OFFENSE","weak"
    return {
        "score":score,
        "label":label,
        "label_cls":cls,
        "components":len(usable),
        "games":games,
    }


def _team_ctx(team_id: Any, team_name: Any) -> dict[str,Any]:
    tid=_i(team_id)
    if not tid:
        return {
            "team_id":None,
            "team_name":str(team_name or "Team"),
            "metrics":{},
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "quality":0,
            "reason":"Official MLB team ID unavailable.",
        }
    stat=_team_hitting(tid)
    metrics=_metrics(stat)
    graded=_score(metrics)
    components=int(graded.get("components") or 0)
    games=int(metrics.get("games") or 0)
    quality=0
    quality+=25 if tid else 0
    quality+=25 if games>=MIN_GAMES else int(round(25*_clamp(games/MIN_GAMES,0.0,1.0)))
    quality+=int(round(50*_clamp(components/7.0,0.0,1.0)))
    reason="" if graded.get("score") is not None else "Season offense sample/metrics are below the fail-closed threshold."
    return {
        "team_id":tid,
        "team_name":str(team_name or f"Team {tid}"),
        "metrics":metrics,
        "score":graded.get("score"),
        "label":graded.get("label"),
        "label_cls":graded.get("label_cls"),
        "quality":quality,
        "reason":reason,
    }


def _overall_grade(away: Mapping[str,Any], home: Mapping[str,Any]) -> tuple[str,str,float|None]:
    away_score=_f(away.get("score"))
    home_score=_f(home.get("score"))
    if away_score is None or home_score is None:
        return "DATA LIMITED / PENDING","limited",None
    edge=home_score-away_score
    if edge>=10:
        return "STRONG HOME OFFENSE EDGE","home",edge
    if edge>=4:
        return "HOME OFFENSE EDGE","home",edge
    if edge<=-10:
        return "STRONG AWAY OFFENSE EDGE","away",edge
    if edge<=-4:
        return "AWAY OFFENSE EDGE","away",edge
    return "OFFENSES CLOSE","neutral",edge


def _ctx(result: Mapping[str,Any]) -> dict[str,Any]:
    away=_team_ctx(result.get("away_team_id"),result.get("away_name"))
    home=_team_ctx(result.get("home_team_id"),result.get("home_name"))
    grade,grade_cls,edge=_overall_grade(away,home)
    return {
        "away":away,
        "home":home,
        "grade":grade,
        "grade_cls":grade_cls,
        "edge":edge,
        "reason":"" if edge is not None else "Both teams need sufficient official season offense evidence before grading.",
    }


def _fmt(value: Any,digits: int=3,suffix: str="") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _side_html(side: Mapping[str,Any],home: bool=False) -> str:
    m=side.get("metrics") or {}
    score=side.get("score")
    score_text="N/A" if score is None else f"{int(score)}/100"
    return (
        f'<div class="ml169-side {"home" if home else ""}">'
        f'<h4>{escape(str(side.get("team_name") or "Team"))}</h4>'
        f'<small>{int(m.get("games") or 0)} games • season offense baseline</small>'
        f'<div class="ml169-score {escape(str(side.get("label_cls") or "limited"))}">{escape(str(side.get("label") or "DATA LIMITED / PENDING"))} • {escape(score_text)}</div>'
        '<div class="ml169-stats">'
        f'<div class="ml169-stat"><b>{_fmt(m.get("rpg"),2)}</b><span>R/G</span></div>'
        f'<div class="ml169-stat"><b>{_fmt(m.get("ops"))}</b><span>OPS</span></div>'
        f'<div class="ml169-stat"><b>{_fmt(m.get("obp"))}</b><span>OBP</span></div>'
        f'<div class="ml169-stat"><b>{_fmt(m.get("slg"))}</b><span>SLG</span></div>'
        '</div>'
        '<div class="ml169-stats">'
        f'<div class="ml169-stat"><b>{_fmt(m.get("avg"))}</b><span>AVG</span></div>'
        f'<div class="ml169-stat"><b>{_fmt(m.get("hrpg"),2)}</b><span>HR/G</span></div>'
        f'<div class="ml169-stat"><b>{_fmt((m.get("bb_pct")*100) if m.get("bb_pct") is not None else None,1,"%")}</b><span>BB%</span></div>'
        f'<div class="ml169-stat"><b>{_fmt((m.get("k_pct")*100) if m.get("k_pct") is not None else None,1,"%")}</b><span>K%</span></div>'
        '</div>'
        f'<div class="ml169-source">Data quality {int(side.get("quality") or 0)}/100. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str,Any]) -> str:
    edge=context.get("edge")
    edge_text="N/A" if edge is None else f"{abs(float(edge)):.1f} pts"
    return (
        '<div class="ml169-step4">'
        '<div class="ml169-step4-head">'
        '<span class="ml169-step4-title">STEP 4 • OFFENSE QUALITY</span>'
        f'<span class="ml169-grade {escape(str(context.get("grade_cls") or "limited"))}">{escape(str(context.get("grade") or "DATA LIMITED / PENDING"))}</span>'
        '</div>'
        '<div class="ml169-grid">'
        f'{_side_html(context.get("away") or {},False)}'
        f'{_side_html(context.get("home") or {},True)}'
        '</div>'
        '<div class="ml169-pills">'
        f'<span class="ml169-pill">OFFENSE DIFFERENTIAL • {escape(edge_text)}</span>'
        '<span class="ml169-pill">SEASON BASELINE</span>'
        '<span class="ml169-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        f'<div class="ml169-source">Official MLB Stats API team season hitting • R/G, AVG, OBP, SLG, OPS, HR/G, BB%, K% • recent form intentionally reserved for Step 9. {escape(str(context.get("reason") or ""))}</div>'
        '</div>'
    )


def _inject(card: str,html: str) -> str:
    text=str(card or "")
    if not html or "ks-pick-card" not in text or "ml169-step4" in text:
        return text
    return text[:-6]+html+"</div>" if text.endswith("</div>") else text+html


_FROZEN_STEP3_RENDERER=prior._renderer


def _renderer(original,rows,lineups):
    step3=_FROZEN_STEP3_RENDERER(original,rows,lineups)

    def wrapped(results,status_info,team_logo,h):
        ordered=list(results or [])[:5]
        cursor={"i":0}
        original_markdown=st.markdown

        def capture(body: Any,*args: Any,**kwargs: Any):
            text=str(body or "")
            if "ks-pick-card" in text and cursor["i"]<len(ordered):
                text=_inject(text,_html(_ctx(ordered[cursor["i"]])))
                cursor["i"]+=1
            return original_markdown(text,*args,**kwargs)

        st.markdown=capture
        try:
            return step3(results,status_info,team_logo,h)
        finally:
            st.markdown=original_markdown

    return wrapped


def render_moneyline_hub(games_df,section_header,status_info,team_logo,h):
    """Render frozen V16.8 plus presentation-only Step 4 offense evidence."""
    st.markdown(_STEP4_CSS,unsafe_allow_html=True)
    original_renderer=prior._renderer
    prior._renderer=_renderer
    try:
        return prior.render_moneyline_hub(games_df,section_header,status_info,team_logo,h)
    finally:
        prior._renderer=original_renderer


__all__=[
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MIN_COMPONENTS",
    "MIN_GAMES",
    "MODEL_VERSION",
    "_metrics",
    "_overall_grade",
    "_score",
    "_team_ctx",
    "render_moneyline_hub",
]
