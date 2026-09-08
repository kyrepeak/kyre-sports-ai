"""MLB Moneyline V17.0 — Step 5 bullpen strength + availability.

Presentation/evidence wrapper over permanently frozen V16.9. Step 5 compares each
team's active relief corps using season quality plus recent bullpen workload.

Data sources:
- Official MLB active roster
- Official MLB individual season pitching stats
- Official MLB prior-day pitching workloads
- Baseball Savant expected stats when available (optional enrichment)

No Moneyline probability, simulation, fair-odds, ranking, candidate selection,
or market math changes. Fail-closed when bullpen identity, season evidence, or
recent workload verification is incomplete.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_moneyline_hub_v169 as prior
import mlb_moneyline_hub_v167 as step2
import mlb_matchup_bullpen_v1 as bullpen

MODEL_VERSION = "V17.0 • MONEYLINE STEP 5 • BULLPEN STRENGTH + AVAILABILITY"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v169"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_RELIEVERS = 4
MIN_DATA_SCORE = 60

_STEP5_CSS = r"""
<style>
.ml170-step5{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(196,111,255,.28);border-radius:13px;background:linear-gradient(145deg,rgba(24,10,34,.96),rgba(9,17,28,.97));box-shadow:inset 3px 0 #ba72ff}
.ml170-step5-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml170-step5-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#d6adff}
.ml170-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #5d5369;background:#241c2c;color:#e2d8ea}
.ml170-grade.home{border-color:#31755d;background:#0b3025;color:#98e7bf}.ml170-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml170-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml170-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml170-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ml170-side{border:1px solid rgba(196,111,255,.18);border-radius:10px;background:rgba(10,17,26,.80);padding:8px}.ml170-side.home{text-align:right}.ml170-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml170-side small{color:#788a95;font-size:.44rem}
.ml170-score{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #5d4e75;background:#1d1727;color:#d7bdf0;font-size:.45rem;font-weight:900}.ml170-score.strong{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml170-score.average{border-color:#75621e;background:#30290d;color:#f4dc78}.ml170-score.weak{border-color:#70484a;background:#30191b;color:#f0b0b3}.ml170-score.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml170-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml170-stat{border:1px solid rgba(102,120,160,.16);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml170-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml170-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml170-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml170-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(196,111,255,.22);background:#20152b;color:#d7b4ef;font-size:.46rem;font-weight:850}.ml170-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml170-grid{grid-template-columns:1fr}.ml170-side.home{text-align:left}.ml170-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml170-step5{padding:9px}}
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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low,min(high,float(value)))


def _game_date(result: Mapping[str,Any]) -> str:
    raw=str(result.get("game_date") or "").strip()
    if len(raw)>=10:
        return raw[:10]
    pk=_i(result.get("game_pk"))
    if not pk:
        return ""
    feed=step2._game_feed(pk)
    if not feed:
        return ""
    return str((((feed.get("gameData") or {}).get("datetime") or {}).get("officialDate") or ""))[:10]


def _starter_context(result: Mapping[str,Any]) -> dict[str,Any]:
    context=step2._ctx(result)
    out={}
    for side in ("away","home"):
        block=context.get(side) or {}
        recent=block.get("recent") or {}
        starts=int(recent.get("starts") or 0)
        recent_ip=_f(recent.get("ip"))
        recent_ip_per_start=(recent_ip/starts) if recent_ip is not None and starts>0 else None
        out[side]={
            "starter_id":_i(block.get("id")),
            "starter_name":str(block.get("name") or "TBD"),
            "profile":{
                "recent5":{
                    "status":"VERIFIED" if recent_ip_per_start is not None else "PENDING",
                    "ip_per_start":recent_ip_per_start,
                }
            },
        }
    return out


@st.cache_data(ttl=1800,show_spinner=False)
def _savant_payload() -> dict[str,Any]:
    return bullpen.fetch_savant_expected_table(SEASON)


def _team_profile(
    team_id: Any,
    team_name: Any,
    game_date: str,
    starter: Mapping[str,Any],
    savant_payload: Mapping[str,Any] | None,
) -> dict[str,Any]:
    tid=_i(team_id)
    if not tid:
        return {
            "team_id":None,
            "team_name":str(team_name or "Team"),
            "status":"PENDING",
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "reason":"Official MLB team ID unavailable.",
            "profile":{},
        }
    if not game_date:
        return {
            "team_id":tid,
            "team_name":str(team_name or f"Team {tid}"),
            "status":"PENDING",
            "score":None,
            "label":"DATA LIMITED / PENDING",
            "label_cls":"limited",
            "reason":"Official game date unavailable for bullpen workload verification.",
            "profile":{},
        }

    active=bullpen.fetch_active_pitchers(tid,SEASON,game_date)
    season=bullpen.fetch_team_pitcher_stats(tid,SEASON)
    recent=bullpen.fetch_recent_workload(tid,SEASON,game_date)
    foundation={
        "starter_id":_i(starter.get("starter_id")),
        "starter_name":str(starter.get("starter_name") or "TBD"),
    }
    profile=bullpen.build_bullpen_profile(
        foundation=foundation,
        opponent_team_id=tid,
        active_payload=active,
        season_payload=season,
        recent_payload=recent,
        savant_payload=dict(savant_payload or {"status":"PENDING","frame":None}),
        starter_profile=dict(starter.get("profile") or {}),
    )

    sufficient=(
        active.get("status")=="VERIFIED"
        and season.get("status")=="VERIFIED"
        and recent.get("status")=="VERIFIED"
        and int(profile.get("reliever_count") or 0)>=MIN_RELIEVERS
        and profile.get("bullpen_path_score") is not None
        and profile.get("availability_index") is not None
        and int(profile.get("bullpen_data_score") or 0)>=MIN_DATA_SCORE
    )
    score=int(profile.get("bullpen_path_score")) if sufficient else None
    if score is None:
        label,cls="DATA LIMITED / PENDING","limited"
    elif score>=68:
        label,cls="ELITE BULLPEN","strong"
    elif score>=58:
        label,cls="STRONG BULLPEN","strong"
    elif score>=43:
        label,cls="AVERAGE BULLPEN","average"
    elif score>=33:
        label,cls="WEAK BULLPEN","weak"
    else:
        label,cls="VERY WEAK BULLPEN","weak"

    if sufficient:
        reason=""
    elif recent.get("status")!="VERIFIED":
        reason="Recent MLB bullpen workload feed is incomplete; availability fails closed."
    elif active.get("status")!="VERIFIED" or season.get("status")!="VERIFIED":
        reason="Active roster or season relief-pitching evidence is incomplete."
    elif int(profile.get("reliever_count") or 0)<MIN_RELIEVERS:
        reason=f"Fewer than {MIN_RELIEVERS} verified active relievers with season data."
    else:
        reason="Bullpen evidence did not clear the fail-closed data-quality threshold."

    return {
        "team_id":tid,
        "team_name":str(team_name or f"Team {tid}"),
        "status":"VERIFIED" if sufficient else "PENDING",
        "score":score,
        "label":label,
        "label_cls":cls,
        "reason":reason,
        "profile":profile,
    }


def _availability_label(value: Any) -> str:
    x=_f(value)
    if x is None:
        return "PENDING"
    if x>=0.90:
        return "READY"
    if x>=0.72:
        return "MOSTLY READY"
    if x>=0.52:
        return "TAXED"
    return "HEAVILY TAXED"


def _overall_grade(away: Mapping[str,Any],home: Mapping[str,Any]) -> tuple[str,str,float|None]:
    away_score=_f(away.get("score"))
    home_score=_f(home.get("score"))
    if away_score is None or home_score is None:
        return "DATA LIMITED / PENDING","limited",None
    edge=home_score-away_score
    if edge>=10:
        return "STRONG HOME BULLPEN EDGE","home",edge
    if edge>=4:
        return "HOME BULLPEN EDGE","home",edge
    if edge<=-10:
        return "STRONG AWAY BULLPEN EDGE","away",edge
    if edge<=-4:
        return "AWAY BULLPEN EDGE","away",edge
    return "BULLPENS CLOSE","neutral",edge


def _ctx(result: Mapping[str,Any]) -> dict[str,Any]:
    game_date=_game_date(result)
    starters=_starter_context(result)
    try:
        savant=_savant_payload()
    except Exception:
        savant={"status":"PENDING","frame":None,"source":"Baseball Savant unavailable"}
    away=_team_profile(
        result.get("away_team_id"),
        result.get("away_name"),
        game_date,
        starters.get("away") or {},
        savant,
    )
    home=_team_profile(
        result.get("home_team_id"),
        result.get("home_name"),
        game_date,
        starters.get("home") or {},
        savant,
    )
    grade,grade_cls,edge=_overall_grade(away,home)
    return {
        "game_date":game_date,
        "away":away,
        "home":home,
        "grade":grade,
        "grade_cls":grade_cls,
        "edge":edge,
        "reason":"" if edge is not None else "Both bullpens must clear roster, season, workload, and data-quality gates.",
    }


def _fmt(value: Any,digits: int=2,suffix: str="") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _side_html(side: Mapping[str,Any],home: bool=False) -> str:
    p=side.get("profile") or {}
    score=side.get("score")
    score_text="N/A" if score is None else f"{int(score)}/100"
    availability=p.get("availability_index")
    return (
        f'<div class="ml170-side {"home" if home else ""}">'
        f'<h4>{escape(str(side.get("team_name") or "Team"))}</h4>'
        f'<small>{int(p.get("reliever_count") or 0)} verified relievers • {escape(_availability_label(availability))}</small>'
        f'<div class="ml170-score {escape(str(side.get("label_cls") or "limited"))}">{escape(str(side.get("label") or "DATA LIMITED / PENDING"))} • {escape(score_text)}</div>'
        '<div class="ml170-stats">'
        f'<div class="ml170-stat"><b>{_fmt(p.get("era"))}</b><span>ERA</span></div>'
        f'<div class="ml170-stat"><b>{_fmt(p.get("whip"))}</b><span>WHIP</span></div>'
        f'<div class="ml170-stat"><b>{_fmt((p.get("k_pct")*100) if p.get("k_pct") is not None else None,1,"%")}</b><span>K%</span></div>'
        f'<div class="ml170-stat"><b>{_fmt((p.get("bb_pct")*100) if p.get("bb_pct") is not None else None,1,"%")}</b><span>BB%</span></div>'
        '</div>'
        '<div class="ml170-stats">'
        f'<div class="ml170-stat"><b>{_fmt((availability*100) if availability is not None else None,0,"%")}</b><span>Availability</span></div>'
        f'<div class="ml170-stat"><b>{int(p.get("ready_count") or 0)}</b><span>Ready</span></div>'
        f'<div class="ml170-stat"><b>{int(p.get("watch_count") or 0)}</b><span>Watch</span></div>'
        f'<div class="ml170-stat"><b>{int(p.get("limited_count") or 0)}</b><span>Limited</span></div>'
        '</div>'
        f'<div class="ml170-source">Data quality {int(p.get("bullpen_data_score") or 0)}/100 • expected bullpen IP {_fmt(p.get("expected_bullpen_ip"),1)}. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str,Any]) -> str:
    edge=context.get("edge")
    edge_text="N/A" if edge is None else f"{abs(float(edge)):.1f} pts"
    return (
        '<div class="ml170-step5">'
        '<div class="ml170-step5-head">'
        '<span class="ml170-step5-title">STEP 5 • BULLPEN STRENGTH + AVAILABILITY</span>'
        f'<span class="ml170-grade {escape(str(context.get("grade_cls") or "limited"))}">{escape(str(context.get("grade") or "DATA LIMITED / PENDING"))}</span>'
        '</div>'
        '<div class="ml170-grid">'
        f'{_side_html(context.get("away") or {},False)}'
        f'{_side_html(context.get("home") or {},True)}'
        '</div>'
        '<div class="ml170-pills">'
        f'<span class="ml170-pill">BULLPEN DIFFERENTIAL • {escape(edge_text)}</span>'
        '<span class="ml170-pill">RECENT WORKLOAD VERIFIED</span>'
        '<span class="ml170-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        f'<div class="ml170-source">Official MLB active roster + season pitching + prior-day workloads; Baseball Savant expected stats optional. Availability is workload-derived and fails closed when recent-day verification is incomplete. {escape(str(context.get("reason") or ""))}</div>'
        '</div>'
    )


def _inject(card: str,html: str) -> str:
    text=str(card or "")
    if not html or "ks-pick-card" not in text or "ml170-step5" in text:
        return text
    return text[:-6]+html+"</div>" if text.endswith("</div>") else text+html


_FROZEN_STEP4_RENDERER=prior._renderer


def _renderer(original,rows,lineups):
    step4=_FROZEN_STEP4_RENDERER(original,rows,lineups)

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
            return step4(results,status_info,team_logo,h)
        finally:
            st.markdown=original_markdown

    return wrapped


def render_moneyline_hub(games_df,section_header,status_info,team_logo,h):
    """Render frozen V16.9 plus presentation-only Step 5 bullpen evidence."""
    st.markdown(_STEP5_CSS,unsafe_allow_html=True)
    original_renderer=prior._renderer
    prior._renderer=_renderer
    try:
        return prior.render_moneyline_hub(games_df,section_header,status_info,team_logo,h)
    finally:
        prior._renderer=original_renderer


__all__=[
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MIN_DATA_SCORE",
    "MIN_RELIEVERS",
    "MODEL_VERSION",
    "_availability_label",
    "_overall_grade",
    "_starter_context",
    "_team_profile",
    "render_moneyline_hub",
]
