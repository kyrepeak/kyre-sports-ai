"""WNBA Points V1.9.8.4.25 — Step 10 rest + schedule + fatigue context.

Presentation/context-only wrapper over V1.9.8.4.24. Adds Step 10 to the same
Top-5 WNBA Points cards after Step 9.

Step 10 uses verified completed WNBA schedule data before the selected slate date
plus the already-cached verified player appearance log to expose rest days,
back-to-back / 3-in-4 / 4-in-6 pressure, recent game density, previous-game
minutes, opponent rest advantage and home/road schedule transition.

Travel distance, time-zone fatigue and recovery effects are NOT inferred because
the connected verified feeds do not publish a validated travel-distance layer.
No new fatigue multiplier is fed into the protected Points model. Projection,
Monte Carlo probability, calibration, sportsbook transport and Top-5 ordering
remain unchanged.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198424 as prior
import wnba_points_hub_v198422 as step9mod
import wnba_points_hub_v198410 as recent
import wnba_points_v13 as roster_mod
import wnba_schedule_v25 as schedule25

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.25 • STEP 10 REST + SCHEDULE + FATIGUE AUDIT"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_STEP9_COMBINER = getattr(
    step9mod,
    "_kyre_v198425_base_step9_combiner",
    step9mod._step7_plus_step8_plus_step9,
)
setattr(step9mod, "_kyre_v198425_base_step9_combiner", _BASE_STEP9_COMBINER)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _compact_html(html: str) -> str:
    return re.sub(r">\s+<", "><", str(html or "").strip())


def _site(row, team_id: int) -> str:
    try:
        tid = int(team_id)
        away = int(float(row.get("away_team_id") or 0))
        home = int(float(row.get("home_team_id") or 0))
    except Exception:
        return "UNKNOWN"
    if home == tid:
        return "HOME"
    if away == tid:
        return "AWAY"
    return "UNKNOWN"


@st.cache_data(ttl=900, show_spinner=False, max_entries=64)
def _team_schedule_profile(day_str: str, team_id: int) -> dict:
    try:
        selected = pd.to_datetime(day_str).normalize()
        tid = int(team_id)
    except Exception:
        return {}
    if not tid:
        return {}

    try:
        history = roster_mod._season_history(selected.strftime("%Y-%m-%d"), {tid})
    except Exception:
        history = pd.DataFrame()

    games = pd.DataFrame()
    if history is not None and not history.empty:
        games = history.loc[
            history["away_team_id"].astype(int).eq(tid)
            | history["home_team_id"].astype(int).eq(tid)
        ].copy()
        if not games.empty:
            games["_DATE"] = pd.to_datetime(games.get("game_date"), errors="coerce").dt.normalize()
            games = games.dropna(subset=["_DATE"]).sort_values("_DATE", ascending=False).drop_duplicates("game_id")

    prev_date = pd.NaT
    prev_site = "UNKNOWN"
    rest_days = np.nan
    calendar_gap = np.nan
    if not games.empty:
        prev = games.iloc[0]
        prev_date = pd.to_datetime(prev.get("_DATE"), errors="coerce")
        prev_site = _site(prev, tid)
        if pd.notna(prev_date):
            calendar_gap = int((selected - prev_date).days)
            rest_days = max(0, calendar_gap - 1)

    def _count_prior(days: int) -> int:
        if games.empty:
            return 0
        cutoff = selected - pd.Timedelta(days=days)
        return int(((games["_DATE"] >= cutoff) & (games["_DATE"] < selected)).sum())

    prior3 = _count_prior(3)
    prior5 = _count_prior(5)
    prior7 = _count_prior(7)
    games4 = 1 + prior3
    games6 = 1 + prior5
    games8 = 1 + prior7

    current_site = "UNKNOWN"
    current_venue = ""
    try:
        slate = schedule25.schedule_for_date(selected.strftime("%Y-%m-%d"))
    except Exception:
        slate = pd.DataFrame()
    if slate is not None and not slate.empty:
        match = slate.loc[
            slate["away_team_id"].astype(int).eq(tid)
            | slate["home_team_id"].astype(int).eq(tid)
        ]
        if not match.empty:
            row = match.iloc[0]
            current_site = _site(row, tid)
            current_venue = str(row.get("venue") or "")

    return {
        "rest_days": rest_days,
        "calendar_gap": calendar_gap,
        "prev_date": prev_date,
        "prev_site": prev_site,
        "current_site": current_site,
        "venue": current_venue,
        "games4": games4,
        "games6": games6,
        "games8": games8,
        "b2b": bool(pd.notna(calendar_gap) and calendar_gap == 1),
        "three_in_four": bool(games4 >= 3),
        "four_in_six": bool(games6 >= 4),
        "source": "ESPN/WNBA verified completed schedule before slate date",
    }


def _player_workload(day: str, data: dict) -> dict:
    try:
        tid = int(float(data.get("TEAM_ID")))
        pid = int(float(data.get("PLAYER_ID")))
    except Exception:
        return {}
    if not tid or not pid:
        return {}
    try:
        logs = recent._recent_player_points(day, tid, pid)
    except Exception:
        logs = pd.DataFrame()
    if logs is None or logs.empty:
        return {}
    mins = pd.to_numeric(logs.get("MIN"), errors="coerce")
    prev = float(mins.iloc[0]) if len(mins) and pd.notna(mins.iloc[0]) else np.nan
    l3 = float(mins.head(3).mean()) if mins.head(3).notna().any() else np.nan
    return {"prev_min": prev, "l3_min": l3, "appearances": int(min(3, mins.notna().sum()))}


def _grade(team: dict, opp: dict, workload: dict):
    score = 0
    evidence = 0
    reasons = []

    rest = _num(team.get("rest_days"), np.nan)
    if pd.notna(rest):
        evidence += 1
        if team.get("b2b"):
            score -= 2; reasons.append("back-to-back")
        elif rest >= 2:
            score += 1; reasons.append(f"{int(rest)} full rest days")
        else:
            reasons.append(f"{int(rest)} full rest day")

    if team:
        evidence += 1
        if team.get("four_in_six"):
            score -= 2; reasons.append("4-in-6 schedule pressure")
        elif team.get("three_in_four"):
            score -= 1; reasons.append("3-in-4 schedule pressure")
        elif int(team.get("games6") or 0) <= 2:
            score += 1; reasons.append("light recent schedule")
        else:
            reasons.append("normal recent game density")

    prev_min = _num(workload.get("prev_min"), np.nan)
    if pd.notna(prev_min):
        evidence += 1
        if prev_min >= 36:
            score -= 1; reasons.append(f"heavy previous-game workload ({prev_min:.1f} min)")
        elif prev_min <= 24:
            score += 1; reasons.append(f"light previous-game workload ({prev_min:.1f} min)")
        else:
            reasons.append(f"normal previous-game workload ({prev_min:.1f} min)")

    opp_rest = _num(opp.get("rest_days"), np.nan)
    if pd.notna(rest) and pd.notna(opp_rest):
        evidence += 1
        adv = rest - opp_rest
        if adv >= 2:
            score += 1; reasons.append(f"rest advantage {adv:+.0f} days")
        elif adv <= -2:
            score -= 1; reasons.append(f"rest disadvantage {adv:+.0f} days")
        else:
            reasons.append(f"rest differential {adv:+.0f} days")

    if evidence < 2:
        return "DATA LIMITED", "limited", "NEUTRAL", score, evidence, reasons
    if score >= 3:
        return "ELITE REST SPOT", "elite", "SUPPORTS SCORER", score, evidence, reasons
    if score >= 1:
        return "FRESH", "fresh", "SUPPORTS SCORER", score, evidence, reasons
    if score <= -3:
        return "HARD SCHEDULE SPOT", "hard", "HURTS SCORER", score, evidence, reasons
    if score <= -1:
        return "FATIGUE WATCH", "fatigue", "HURTS SCORER", score, evidence, reasons
    return "NEUTRAL", "neutral", "NEUTRAL", score, evidence, reasons


def _step10_block(day: str, data: dict) -> str:
    try:
        tid = int(float(data.get("TEAM_ID")))
        opp_id = int(float(data.get("opponent_team_id")))
    except Exception:
        tid = opp_id = 0

    team = _team_schedule_profile(day, tid) if tid else {}
    opp = _team_schedule_profile(day, opp_id) if opp_id else {}
    workload = _player_workload(day, data)
    grade, grade_class, verdict, score, evidence, reasons = _grade(team, opp, workload)

    rest = _num(team.get("rest_days"), np.nan)
    opp_rest = _num(opp.get("rest_days"), np.nan)
    rest_adv = rest - opp_rest if pd.notna(rest) and pd.notna(opp_rest) else np.nan
    prev_date = team.get("prev_date")
    prev_date_text = pd.to_datetime(prev_date).strftime("%b %d") if pd.notna(prev_date) else "—"
    transition = f"{team.get('prev_site','UNKNOWN')} → {team.get('current_site','UNKNOWN')}"
    flags = []
    if team.get("b2b"): flags.append("BACK-TO-BACK")
    if team.get("three_in_four"): flags.append("3-IN-4")
    if team.get("four_in_six"): flags.append("4-IN-6")
    flag_text = " • ".join(flags) if flags else "NO DENSE-SCHEDULE FLAG"
    reason_text = " • ".join(reasons) if reasons else "Verified fatigue evidence unavailable"

    html = f"""
<style>
.kyre-v198425-step10{{background:#161a22;border:1px solid #596d8f;border-radius:15px;padding:12px;margin-top:10px}}
.kyre-v198425-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#9fc7ff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
.kyre-v198425-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
.kyre-v198425-grade.elite,.kyre-v198425-grade.fresh{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198425-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
.kyre-v198425-grade.fatigue{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
.kyre-v198425-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198425-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198425-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198425-grid div{{border:1px solid #405474;border-radius:10px;padding:8px;background:#0d1118}}
.kyre-v198425-grid small{{display:block;color:#8da5c6;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198425-grid strong{{display:block;color:#f4f7ff;font-size:.82rem;margin-top:3px;word-break:break-word}}
.kyre-v198425-detail{{background:#0d1118;border:1px solid #405474;border-radius:10px;padding:9px;color:#dce6f5;font-size:.66rem;line-height:1.52;margin-top:8px}}
.kyre-v198425-detail b{{color:#9fc7ff}}
.kyre-v198425-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#172131;border:1px solid #596d8f;color:#f4f8ff;font-size:.68rem;font-weight:850}}
.kyre-v198425-note{{color:#8190a6;font-size:.57rem;line-height:1.42;margin-top:7px}}
@media(max-width:760px){{.kyre-v198425-head{{align-items:flex-start;flex-direction:column}}}}
</style>
<div class="kyre-v198425-step10">
<div class="kyre-v198425-head"><span>STEP 10 • REST + SCHEDULE + TRAVEL / FATIGUE CONTEXT</span><span class="kyre-v198425-grade {grade_class}">{escape(grade)}</span></div>
<div class="kyre-v198425-grid">
<div><small>FULL REST DAYS</small><strong>{"—" if pd.isna(rest) else int(rest)}</strong></div><div><small>OPP REST DAYS</small><strong>{"—" if pd.isna(opp_rest) else int(opp_rest)}</strong></div>
<div><small>REST ADVANTAGE</small><strong>{_fmt(rest_adv,0, " days") if pd.notna(rest_adv) else "—"}</strong></div><div><small>PREVIOUS GAME</small><strong>{prev_date_text}</strong></div>
<div><small>CURRENT 4-DAY LOAD</small><strong>{team.get('games4','—')} games</strong></div><div><small>CURRENT 6-DAY LOAD</small><strong>{team.get('games6','—')} games</strong></div>
<div><small>CURRENT 8-DAY LOAD</small><strong>{team.get('games8','—')} games</strong></div><div><small>SCHEDULE FLAGS</small><strong>{escape(flag_text)}</strong></div>
<div><small>PREVIOUS-GAME MIN</small><strong>{_fmt(workload.get('prev_min'))}</strong></div><div><small>L3 PLAYER MIN</small><strong>{_fmt(workload.get('l3_min'))}</strong></div>
<div><small>SCHEDULE TRANSITION</small><strong>{escape(transition)}</strong></div><div><small>CURRENT VENUE</small><strong>{escape(str(team.get('venue') or '—'))}</strong></div>
</div>
<div class="kyre-v198425-detail"><b>Fatigue evidence</b> • {evidence} scored signals • score {score:+d}<br><b>Read</b> • {escape(reason_text)}<br><b>Schedule source</b> • ESPN/WNBA verified completed schedule before slate date<br><b>Travel firewall</b> • home/road transition is shown, but travel miles, time-zone fatigue and recovery effects are NOT SCORED without a verified distance layer</div>
<div class="kyre-v198425-verdict">Rest / schedule context • {escape(verdict)}</div>
<div class="kyre-v198425-note">Audit/context only • Step 10 does not add a fatigue/rest/travel multiplier or change projection, Monte Carlo probability, calibration, sportsbook data or Top-5 ordering.</div>
</div>
"""
    return _compact_html(html)


def _step7_8_9_10(day: str, data: dict) -> str:
    return _BASE_STEP9_COMBINER(day, data) + _step10_block(day, data)


def _install() -> None:
    # V1.9.8.4.23 reattaches step9mod._step7_plus_step8_plus_step9 at the final
    # render boundary. Replace that dynamic function first so its late installer
    # preserves Step 10 too, then run the normal V1.9.8.4.24 install chain.
    step9mod._step7_plus_step8_plus_step9 = _step7_8_9_10
    prior._install()


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🛌 Points V1.9.8.4.25 • Step 10 rest/schedule/fatigue audit ACTIVE • "
        "verified schedule + cached player workload • no inferred travel miles • model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
