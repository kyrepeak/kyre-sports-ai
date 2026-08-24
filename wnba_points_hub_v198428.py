"""WNBA Points V1.9.8.4.28 — Step 12 final Top-5 evidence synthesis.

Presentation/context-only wrapper over V1.9.8.4.27. Adds a final evidence
summary to the same Top-5 WNBA Points cards after Step 11.

Step 12 summarizes the already-rendered Step 2-11 evidence into a compact
agreement/coverage score, pick-strength label, matchup grade and support/concern
ledger. It does NOT add any new projection factor, modify Monte Carlo,
calibration, sportsbook lines or Top-5 ordering. Context layers that overlap are
intentionally down-weighted, H2H is low-weight and small H2H samples are treated
as data-limited rather than predictive.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198427 as prior
import wnba_points_hub_v198426 as v426
import wnba_points_hub_v19849 as s23
import wnba_points_hub_v198410 as s4
import wnba_points_hub_v198411 as s5
import wnba_points_hub_v198412 as s6
import wnba_points_hub_v198416 as s7
import wnba_points_hub_v198418 as s8
import wnba_points_hub_v198422 as s9
import wnba_points_hub_v198425 as s10

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.28 • STEP 12 FINAL TOP-5 EVIDENCE SYNTHESIS"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_STEP11_COMBINER = getattr(
    v426,
    "_kyre_v198428_base_step11_combiner",
    v426._step7_8_9_10_11,
)
setattr(v426, "_kyre_v198428_base_step11_combiner", _BASE_STEP11_COMBINER)

_WEIGHTS = {
    2: 0.50,  # H2H is descriptive and intentionally low weight.
    3: 1.30,  # Minutes/role/usage is core opportunity evidence.
    4: 1.00,
    5: 1.00,
    6: 0.80,  # Context layers are reduced to avoid pseudo-double-counting.
    7: 1.00,
    8: 1.25,  # Availability/rotation is a hard production concern.
    9: 0.80,
    10: 0.70,
    11: 0.80,
}


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _compact_html(html: str) -> str:
    return re.sub(r">\s+<", "><", str(html or "").strip())


def _id_text(value) -> str:
    try:
        return str(int(float(value)))
    except Exception:
        return str(value or "").strip()


def _candidate_row(day: str, data: dict):
    try:
        top = s23._same_top5(day)
    except Exception:
        top = pd.DataFrame()
    if top is None or top.empty:
        return None

    pid = _id_text(data.get("PLAYER_ID"))
    pkey = str(data.get("player_key") or "").strip()
    if pid and "PLAYER_ID" in top.columns:
        ids = top["PLAYER_ID"].apply(_id_text)
        part = top.loc[ids.eq(pid)]
        if not part.empty:
            return part.iloc[0]
    if pkey and "player_key" in top.columns:
        part = top.loc[top["player_key"].astype(str).eq(pkey)]
        if not part.empty:
            return part.iloc[0]
    return None


def _line_side(day: str, data: dict):
    row = _candidate_row(day, data)
    line = np.nan
    proj = _num(data.get("PROJ_PTS"), np.nan)
    decision = ""
    if row is not None:
        line = _num(row.get("line"), np.nan)
        if pd.isna(proj):
            proj = _num(row.get("Proj PTS"), np.nan)
        for key in ("Decision", "Side", "side", "Pick", "pick"):
            raw = str(row.get(key) or "").upper().strip()
            if "OVER" in raw or raw == "O":
                decision = "OVER"; break
            if "UNDER" in raw or raw == "U":
                decision = "UNDER"; break
    if pd.isna(line):
        for key in ("line", "LINE", "points_line", "K_LINE"):
            x = _num(data.get(key), np.nan)
            if pd.notna(x):
                line = x; break
    if not decision and pd.notna(proj) and pd.notna(line):
        decision = "OVER" if proj >= line else "UNDER"
    if not decision:
        decision = "OVER"
    edge = (proj - line) if pd.notna(proj) and pd.notna(line) else np.nan
    pick_edge = edge if decision == "OVER" else (-edge if pd.notna(edge) else np.nan)
    return row, line, proj, decision, pick_edge


def _signal(step: int, name: str, grade: str, scorer_dir: int, available=True, note=""):
    scorer_dir = 1 if scorer_dir > 0 else -1 if scorer_dir < 0 else 0
    return {
        "step": int(step), "name": str(name), "grade": str(grade or "NEUTRAL"),
        "scorer_dir": scorer_dir, "available": bool(available), "note": str(note or ""),
        "weight": float(_WEIGHTS.get(int(step), 1.0)),
    }


def _verdict_dir(verdict: str) -> int:
    text = str(verdict or "").upper()
    if "SUPPORT" in text or "BOOST" in text:
        return 1
    if "HURT" in text or "RISK" in text or "TOUGH" in text or "HARD" in text:
        return -1
    return 0


def _step2_signal(day: str, data: dict, row, line, proj):
    if row is None:
        return _signal(2, "H2H", "DATA LIMITED", 0, False, "Top-5 H2H row unavailable")
    try:
        meetings = s23.evidence._player_meetings(str(day), row)
        summary = s23.evidence._meeting_summary(meetings, line, proj)
    except Exception:
        summary = {}
    gp = int(summary.get("games") or 0)
    hit = _num(summary.get("hit_rate"), np.nan)
    margin = _num(summary.get("avg_margin"), np.nan)
    try:
        label, _cls = s23.evidence._context_read(summary, line)
    except Exception:
        label = "SMALL SAMPLE" if gp < 3 else "NEUTRAL"
    if gp < 3 or pd.isna(line):
        return _signal(2, "H2H", str(label), 0, False, f"{gp} game sample • descriptive only")
    direction = 0
    if (pd.notna(hit) and hit >= 0.60) or (pd.notna(margin) and margin >= 1.5):
        direction = 1
    elif (pd.notna(hit) and hit <= 0.40) or (pd.notna(margin) and margin <= -1.5):
        direction = -1
    return _signal(2, "H2H", str(label), direction, True, f"{gp} verified games")


def _step3_signal(data: dict):
    try:
        grade, cls = s23.prior._opportunity_grade(data)
        trend = s23.prior._minute_trend(data)
    except Exception:
        return _signal(3, "Opportunity", "DATA LIMITED", 0, False)
    text = str(grade).upper()
    if "DATA LIMITED" in text:
        return _signal(3, "Opportunity", grade, 0, False, trend)
    direction = 1 if cls in {"elite", "strong"} else -1 if (cls == "limited" and "MINUTES" in text) else 0
    return _signal(3, "Opportunity", grade, direction, True, trend)


def _step4_signal(day: str, data: dict, line: float):
    try:
        tid = int(float(data.get("TEAM_ID"))); pid = int(float(data.get("PLAYER_ID")))
        logs = s4._recent_player_points(day, tid, pid)
        sm = s4._recent_summary(logs, line, data)
    except Exception:
        return _signal(4, "Recent form", "DATA LIMITED", 0, False)
    cls = str(sm.get("grade_class") or "")
    grade = str(sm.get("grade") or "DATA LIMITED")
    if cls == "limited": return _signal(4, "Recent form", grade, 0, False, sm.get("trend"))
    direction = 1 if cls in {"elite", "strong"} else -1 if cls == "cold" else 0
    return _signal(4, "Recent form", grade, direction, True, sm.get("trend"))


def _step5_signal(data: dict):
    try:
        grade, _cls, verdict = s5._defense_grade(data)
        return _signal(5, "Defense + position", grade, _verdict_dir(verdict), True)
    except Exception:
        return _signal(5, "Defense + position", "DATA LIMITED", 0, False)


def _step6_signal(day: str, data: dict):
    try:
        tid = int(float(data.get("TEAM_ID"))); oid = int(float(data.get("opponent_team_id")))
        team = s6._team_environment(day, tid); opp = s6._team_environment(day, oid)
        baseline = s6._slate_environment_baseline(day)
        expected = s6._mean_valid([team.get("pace_l10"), opp.get("pace_l10")])
        grade, _cls, verdict, score, evidence = s6._environment_grade(team, opp, baseline, expected)
        return _signal(6, "Pace + environment", grade, _verdict_dir(verdict), evidence >= 2, f"{evidence}/4 signals • score {score:+d}")
    except Exception:
        return _signal(6, "Pace + environment", "DATA LIMITED", 0, False)


def _step7_signal(day: str, data: dict):
    try:
        season_p, l10_p, l5_p, _src = s9._player_profiles(day, data)
        grade, _cls, verdict, score, evidence, vol, eff = s7.prior._grade(season_p, l10_p, l5_p)
        available = str(grade).upper() != "DATA LIMITED" and evidence > 0
        return _signal(7, "Shot profile", grade, _verdict_dir(verdict), available, f"{vol} • {eff}")
    except Exception:
        return _signal(7, "Shot profile", "DATA LIMITED", 0, False)


def _step8_signal(data: dict):
    try:
        _roster, player_status, _src, _flagged = s8._roster_context(data)
        grade, _cls, verdict, min_delta, usage_delta = s8._rotation_read(data, player_status)
        available = str(grade).upper() != "DATA LIMITED"
        note = []
        if pd.notna(_num(min_delta, np.nan)): note.append(f"MIN {float(min_delta):+.1f}")
        if pd.notna(_num(usage_delta, np.nan)): note.append(f"USG {float(usage_delta):+.1f} pp")
        return _signal(8, "Availability + rotation", grade, _verdict_dir(verdict), available, " • ".join(note))
    except Exception:
        return _signal(8, "Availability + rotation", "DATA LIMITED", 0, False)


def _step9_signal(day: str, data: dict):
    try:
        oid = int(float(data.get("opponent_team_id")))
        season_p, l10_p, l5_p, _src = s9._player_profiles(day, data)
        logs = s9._opponent_shooting_allowed_history(day, oid)
        season_a = s9._aggregate_allowed(logs, None); l10_a = s9._aggregate_allowed(logs, 10)
        grade, _cls, verdict, score, evidence, _reasons, method = s9._grade_matchup(l5_p, season_a, l10_a)
        return _signal(9, "Scoring-method matchup", grade, _verdict_dir(verdict), evidence >= 1, f"{method} • {evidence} signals")
    except Exception:
        return _signal(9, "Scoring-method matchup", "DATA LIMITED", 0, False)


def _step10_signal(day: str, data: dict):
    try:
        tid = int(float(data.get("TEAM_ID"))); oid = int(float(data.get("opponent_team_id")))
        team = s10._team_schedule_profile(day, tid); opp = s10._team_schedule_profile(day, oid)
        workload = s10._player_workload(day, data)
        grade, _cls, verdict, score, evidence, _reasons = s10._grade(team, opp, workload)
        return _signal(10, "Rest + fatigue", grade, _verdict_dir(verdict), evidence >= 2, f"{evidence} signals • score {score:+d}")
    except Exception:
        return _signal(10, "Rest + fatigue", "DATA LIMITED", 0, False)


def _step11_signal(day: str, data: dict):
    try:
        ctx = v426._consensus_for_game(day, data)
        grade, _cls, verdict, score, evidence, _reasons = prior._grade_context_aware(ctx)
        return _signal(11, "Game script", grade, _verdict_dir(verdict), str(ctx.get("state")) == "FRESH" and evidence >= 2, f"{evidence} signals • score {score:+d}")
    except Exception:
        return _signal(11, "Game script", "DATA LIMITED", 0, False)


def _collect(day: str, data: dict):
    row, line, proj, side, pick_edge = _line_side(day, data)
    signals = [
        _step2_signal(day, data, row, line, proj),
        _step3_signal(data),
        _step4_signal(day, data, line),
        _step5_signal(data),
        _step6_signal(day, data),
        _step7_signal(day, data),
        _step8_signal(data),
        _step9_signal(day, data),
        _step10_signal(day, data),
        _step11_signal(day, data),
    ]
    for sig in signals:
        sig["pick_dir"] = sig["scorer_dir"] if side == "OVER" else -sig["scorer_dir"]
    return row, line, proj, side, pick_edge, signals


def _summary(day: str, data: dict):
    row, line, proj, side, pick_edge, signals = _collect(day, data)
    total_weight = sum(float(s["weight"]) for s in signals)
    available = [s for s in signals if s["available"]]
    avail_weight = sum(float(s["weight"]) for s in available)
    weighted = sum(float(s["weight"]) * int(s["pick_dir"]) for s in available)
    raw = weighted / avail_weight if avail_weight > 0 else 0.0
    coverage = avail_weight / total_weight if total_weight > 0 else 0.0
    evidence_score = int(round(np.clip(50.0 + 40.0 * raw * coverage, 5.0, 95.0)))

    if coverage < 0.55:
        strength, strength_class = "DATA LIMITED", "limited"
    elif evidence_score >= 80:
        strength, strength_class = "ELITE", "elite"
    elif evidence_score >= 66:
        strength, strength_class = "STRONG", "strong"
    elif evidence_score >= 54:
        strength, strength_class = "MEDIUM", "medium"
    else:
        strength, strength_class = "WEAK", "weak"

    matchup_steps = [s for s in signals if s["step"] in {5, 6, 9, 11} and s["available"]]
    m_weight = sum(float(s["weight"]) for s in matchup_steps)
    m_score = sum(float(s["weight"]) * int(s["scorer_dir"]) for s in matchup_steps) / m_weight if m_weight else 0.0
    if not matchup_steps:
        matchup = "DATA LIMITED"
    elif m_score >= 0.55:
        matchup = "ELITE FOR SCORER"
    elif m_score >= 0.20:
        matchup = "FAVORABLE FOR SCORER"
    elif m_score <= -0.55:
        matchup = "HARD FOR SCORER"
    elif m_score <= -0.20:
        matchup = "TOUGH FOR SCORER"
    else:
        matchup = "NEUTRAL"

    supports = [s for s in available if s["pick_dir"] > 0]
    concerns = [s for s in available if s["pick_dir"] < 0]
    neutral = [s for s in available if s["pick_dir"] == 0]
    limited = [s for s in signals if not s["available"]]

    return {
        "row": row, "line": line, "proj": proj, "side": side, "pick_edge": pick_edge,
        "signals": signals, "score": evidence_score, "coverage": coverage,
        "strength": strength, "strength_class": strength_class, "matchup": matchup,
        "supports": supports, "concerns": concerns, "neutral": neutral, "limited": limited,
    }


def _list_text(items, empty="None"):
    if not items:
        return empty
    return " • ".join(f"Step {s['step']} {escape(s['name'])} ({escape(s['grade'])})" for s in items)


def _step12_block(day: str, data: dict) -> str:
    out = _summary(day, data)
    line = _num(out.get("line"), np.nan); proj = _num(out.get("proj"), np.nan); edge = _num(out.get("pick_edge"), np.nan)
    line_text = "—" if pd.isna(line) else f"{line:.1f}"
    proj_text = "—" if pd.isna(proj) else f"{proj:.2f}"
    edge_text = "—" if pd.isna(edge) else f"{edge:+.2f} PTS"
    coverage_text = f"{out['coverage']*100:.0f}%"
    supports = _list_text(out["supports"])
    concerns = _list_text(out["concerns"])
    neutral = _list_text(out["neutral"])
    limited = _list_text(out["limited"])

    rows = "".join(
        f'<div class="kyre-v198428-signal"><span>STEP {s["step"]} • {escape(s["name"])}</span><b>{escape(s["grade"])}</b><em>{"SUPPORT" if s["pick_dir"]>0 and s["available"] else "CONCERN" if s["pick_dir"]<0 and s["available"] else "NEUTRAL" if s["available"] else "DATA LIMITED"}</em></div>'
        for s in out["signals"]
    )

    html = f"""
<style>
.kyre-v198428-step12{{background:linear-gradient(145deg,#18180f,#10170f);border:1px solid #8d7424;border-radius:17px;padding:13px;margin-top:11px;box-shadow:0 7px 18px rgba(0,0,0,.15)}}
.kyre-v198428-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#ffe28a;font-size:.62rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase;margin-bottom:10px}}
.kyre-v198428-lock{{color:#a89a6d;font-size:.5rem;white-space:nowrap}}
.kyre-v198428-badges{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:9px}}
.kyre-v198428-badge{{border-radius:999px;padding:6px 9px;font-size:.55rem;font-weight:950;letter-spacing:.025em}}
.kyre-v198428-badge.elite,.kyre-v198428-badge.strong{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198428-badge.medium{{background:#4a370c;color:#ffe17a;border:1px solid #8d7118}}
.kyre-v198428-badge.weak{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198428-badge.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198428-badge.info{{background:#102338;color:#9ed4ff;border:1px solid #3b6484}}
.kyre-v198428-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198428-grid div{{border:1px solid #5f532d;border-radius:10px;padding:8px;background:#0d110c}}
.kyre-v198428-grid small{{display:block;color:#a89a6d;font-size:.47rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198428-grid strong{{display:block;color:#fff9e8;font-size:.82rem;margin-top:3px;word-break:break-word}}
.kyre-v198428-ledger{{margin-top:9px;display:grid;gap:6px}}
.kyre-v198428-ledger div{{border-radius:9px;padding:8px 9px;font-size:.61rem;line-height:1.45}}
.kyre-v198428-support{{background:#0b2d20;border:1px solid #23664b;color:#bff3dc}}
.kyre-v198428-concern{{background:#33240d;border:1px solid #79601f;color:#ffe0a0}}
.kyre-v198428-neutral{{background:#151922;border:1px solid #46505e;color:#cad1dc}}
.kyre-v198428-limitedrow{{background:#121a20;border:1px solid #344c5b;color:#aac1d0}}
.kyre-v198428-ledger b{{color:#fff}}
.kyre-v198428-signals{{margin-top:9px;border-top:1px solid #5f532d;padding-top:7px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}}
.kyre-v198428-signal{{background:#0d110c;border:1px solid #40391f;border-radius:8px;padding:7px;min-width:0}}
.kyre-v198428-signal span{{display:block;color:#c9b977;font-size:.48rem;font-weight:900}}
.kyre-v198428-signal b{{display:block;color:#f5f0df;font-size:.59rem;margin-top:2px}}
.kyre-v198428-signal em{{display:block;color:#8e987e;font-size:.45rem;margin-top:2px;font-style:normal}}
.kyre-v198428-note{{color:#92896b;font-size:.56rem;line-height:1.45;margin-top:8px}}
@media(max-width:760px){{.kyre-v198428-head{{align-items:flex-start;flex-direction:column}}.kyre-v198428-signals{{grid-template-columns:1fr}}}}
</style>
<div class="kyre-v198428-step12">
<div class="kyre-v198428-head"><span>🏆 STEP 12 • FINAL TOP-5 EVIDENCE SUMMARY</span><span class="kyre-v198428-lock">RANKING UNCHANGED</span></div>
<div class="kyre-v198428-badges"><span class="kyre-v198428-badge {out['strength_class']}">PICK STRENGTH • {escape(out['strength'])}</span><span class="kyre-v198428-badge info">MATCHUP • {escape(out['matchup'])}</span><span class="kyre-v198428-badge info">EVIDENCE • {out['score']}/100</span><span class="kyre-v198428-badge info">COVERAGE • {coverage_text}</span></div>
<div class="kyre-v198428-grid"><div><small>MODEL SIDE</small><strong>{escape(out['side'])}</strong></div><div><small>POSTED LINE</small><strong>{line_text}</strong></div><div><small>PROTECTED PROJECTION</small><strong>{proj_text}</strong></div><div><small>PROJECTION EDGE TO SIDE</small><strong>{edge_text}</strong></div></div>
<div class="kyre-v198428-ledger"><div class="kyre-v198428-support"><b>✅ Supports</b> • {supports}</div><div class="kyre-v198428-concern"><b>⚠️ Concerns</b> • {concerns}</div><div class="kyre-v198428-neutral"><b>Neutral</b> • {neutral}</div><div class="kyre-v198428-limitedrow"><b>N/A / data-limited</b> • {limited}</div></div>
<div class="kyre-v198428-signals">{rows}</div>
<div class="kyre-v198428-note">Synthesis/audit only • Evidence Score measures weighted agreement + verified data coverage across Steps 2–11; it is NOT a second probability model. H2H is low-weight, overlapping context layers are down-weighted, and data-limited signals do not receive neutral credit. Step 12 cannot change the protected Points projection, Monte Carlo probability, calibration, sportsbook line, pick side or Top-5 order.</div>
</div>
"""
    return _compact_html(html)


def _step7_8_9_10_11_12(day: str, data: dict) -> str:
    return _BASE_STEP11_COMBINER(day, data) + _step12_block(day, data)


def _install() -> None:
    # V1.9.8.4.26's installer resolves its module-global Step-11 combiner at
    # render time. Replace that final boundary first, then run V1.9.8.4.27's
    # established install chain so all Step-8/9 repairs and Step-11 labels stay.
    v426._step7_8_9_10_11 = _step7_8_9_10_11_12
    prior._install()


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🏆 Points V1.9.8.4.28 • Step 12 final Top-5 evidence synthesis ACTIVE • "
        "weighted agreement + coverage only • projection/Monte Carlo/ranking unchanged"
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
