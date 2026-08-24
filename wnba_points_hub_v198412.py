"""WNBA Points V1.9.8.4.12 — embedded Step 6 pace + game scoring environment.

Presentation/context-only wrapper over V1.9.8.4.11. The validated V1.9.8.4.5
Points projection, SportsGameOdds transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and player-level sanity
quarantine remain unchanged.

Step 6 is restricted to the same Top-5 candidates already rendered by Steps
2-5. It exposes verified L10 pace/offense/defense context and the pace factor
already carried by the protected Points model. No second pace, offense or
defense multiplier is applied and Step 6 cannot rerank the Top 5.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198411 as prior
import wnba_context_v26 as context

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.12 • STEP 6 PACE + SCORING ENVIRONMENT"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_STEP5_BLOCK = prior._step5_block


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _mean_valid(values):
    vals = []
    for value in values:
        x = _num(value, np.nan)
        if pd.notna(x) and np.isfinite(x):
            vals.append(float(x))
    return float(np.mean(vals)) if vals else np.nan


@st.cache_data(ttl=900, show_spinner=False, max_entries=64)
def _team_environment(day_str: str, team_id: int) -> dict:
    """Verified team scoring/pace context using games completed before day_str."""
    try:
        selected = pd.to_datetime(day_str)
        season = int(selected.year)
        tid = int(team_id or 0)
    except Exception:
        return {}
    if not tid:
        return {}

    try:
        games = context._season_team_games(season)
    except Exception:
        games = pd.DataFrame()
    if games is None or games.empty:
        return {}

    frame = games.copy()
    frame["GAME_DATE"] = pd.to_datetime(frame.get("GAME_DATE"), errors="coerce")
    frame = frame.loc[frame["GAME_DATE"] < selected].copy()
    if frame.empty:
        return {}

    try:
        record = context._record_summary(frame, tid) or {}
    except Exception:
        record = {}
    try:
        adv = context._advanced_summary(frame, tid, 10) or {}
    except Exception:
        adv = {}

    return {
        "gp": int(_num(record.get("GP"), 0)),
        "season_pf": _num(record.get("PF"), np.nan),
        "season_pa": _num(record.get("PA"), np.nan),
        "l10_pf": _num(record.get("L10_PF"), np.nan),
        "l10_pa": _num(record.get("L10_PA"), np.nan),
        "pace_l10": _num(adv.get("PACE_L10"), np.nan),
        "ortg_l10": _num(adv.get("ORTG_L10"), np.nan),
        "drtg_l10": _num(adv.get("DRTG_L10"), np.nan),
        "adv_games": int(_num(adv.get("ADV_GAMES"), 0)),
    }


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _slate_environment_baseline(day_str: str) -> dict:
    """Average verified L10 environment across teams on the selected slate."""
    try:
        contexts, _diag = context.slate_context(pd.to_datetime(day_str).strftime("%Y-%m-%d"))
    except Exception:
        contexts = {}

    pace, ortg, drtg, pf = [], [], [], []
    for game_ctx in (contexts or {}).values():
        for side in ("away", "home"):
            obj = (game_ctx or {}).get(side) or {}
            for bucket, key in ((pace, "PACE_L10"), (ortg, "ORTG_L10"), (drtg, "DRTG_L10"), (pf, "L10_PF")):
                x = _num(obj.get(key), np.nan)
                if pd.notna(x) and np.isfinite(x):
                    bucket.append(float(x))
    return {
        "pace": _mean_valid(pace),
        "ortg": _mean_valid(ortg),
        "drtg": _mean_valid(drtg),
        "pf": _mean_valid(pf),
        "teams": max(len(pace), len(ortg), len(drtg), len(pf)),
    }


def _environment_grade(team: dict, opp: dict, baseline: dict, expected_pace: float):
    """Audit grade only. It never feeds the protected projection."""
    pace_base = _num(baseline.get("pace"), np.nan)
    ortg_base = _num(baseline.get("ortg"), np.nan)
    drtg_base = _num(baseline.get("drtg"), np.nan)
    pf_base = _num(baseline.get("pf"), np.nan)

    pace_delta = expected_pace - pace_base if pd.notna(expected_pace) and pd.notna(pace_base) else np.nan
    ortg_delta = _num(team.get("ortg_l10"), np.nan) - ortg_base if pd.notna(_num(team.get("ortg_l10"), np.nan)) and pd.notna(ortg_base) else np.nan
    opp_drtg_delta = _num(opp.get("drtg_l10"), np.nan) - drtg_base if pd.notna(_num(opp.get("drtg_l10"), np.nan)) and pd.notna(drtg_base) else np.nan
    pf_delta = _num(team.get("l10_pf"), np.nan) - pf_base if pd.notna(_num(team.get("l10_pf"), np.nan)) and pd.notna(pf_base) else np.nan

    score = 0
    evidence = 0
    if pd.notna(pace_delta):
        evidence += 1
        score += 2 if pace_delta >= 2.0 else 1 if pace_delta >= 0.8 else -2 if pace_delta <= -2.0 else -1 if pace_delta <= -0.8 else 0
    if pd.notna(ortg_delta):
        evidence += 1
        score += 1 if ortg_delta >= 3.0 else -1 if ortg_delta <= -3.0 else 0
    if pd.notna(opp_drtg_delta):
        evidence += 1
        # Higher opponent DRTG means weaker defense / friendlier scoring environment.
        score += 1 if opp_drtg_delta >= 3.0 else -1 if opp_drtg_delta <= -3.0 else 0
    if pd.notna(pf_delta):
        evidence += 1
        score += 1 if pf_delta >= 3.0 else -1 if pf_delta <= -3.0 else 0

    if evidence < 2:
        return "DATA LIMITED", "limited", "NEUTRAL", score, evidence
    if score >= 3:
        return "ELITE ENVIRONMENT", "elite", "SUPPORTS SCORER", score, evidence
    if score >= 1:
        return "FAVORABLE", "favorable", "SUPPORTS SCORER", score, evidence
    if score <= -3:
        return "HARD ENVIRONMENT", "hard", "HURTS SCORER", score, evidence
    if score <= -1:
        return "SLOW / TOUGH", "slow", "HURTS SCORER", score, evidence
    return "NEUTRAL", "neutral", "NEUTRAL", score, evidence


def _step6_block(day: str, data: dict) -> str:
    try:
        team_id = int(float(data.get("TEAM_ID")))
    except Exception:
        team_id = 0
    try:
        opp_id = int(float(data.get("opponent_team_id")))
    except Exception:
        opp_id = 0

    team = _team_environment(day, team_id) if team_id else {}
    opp = _team_environment(day, opp_id) if opp_id else {}
    baseline = _slate_environment_baseline(day)

    team_pace = _num(team.get("pace_l10"), np.nan)
    opp_pace = _num(opp.get("pace_l10"), np.nan)
    protected_expected = _num(data.get("expected_pace"), np.nan)
    expected_pace = protected_expected if pd.notna(protected_expected) else _mean_valid([team_pace, opp_pace])
    pace_base = _num(baseline.get("pace"), np.nan)
    pace_delta = expected_pace - pace_base if pd.notna(expected_pace) and pd.notna(pace_base) else np.nan

    pace_factor = _num(data.get("pace_factor"), np.nan)
    pace_factor_text = "—" if pd.isna(pace_factor) else f"{pace_factor:.3f}×"
    pace_effect_text = "—" if pd.isna(pace_factor) else f"{(pace_factor - 1.0) * 100.0:+.1f}% raw pace factor"

    grade, grade_class, verdict, score, evidence_n = _environment_grade(team, opp, baseline, expected_pace)
    team_name = escape(str(data.get("team_name") or "Team"))
    opponent = escape(str(data.get("opponent") or "Opponent"))
    source_expected = "protected Points context" if pd.notna(protected_expected) else "verified L10 team pace average"

    team_scoring_trend = "DATA LIMITED"
    season_pf = _num(team.get("season_pf"), np.nan)
    l10_pf = _num(team.get("l10_pf"), np.nan)
    if pd.notna(season_pf) and pd.notna(l10_pf):
        delta = l10_pf - season_pf
        if delta >= 2.0:
            team_scoring_trend = f"RISING • L10 {delta:+.1f} PPG vs season"
        elif delta <= -2.0:
            team_scoring_trend = f"COOLING • L10 {delta:+.1f} PPG vs season"
        else:
            team_scoring_trend = f"STABLE • L10 {delta:+.1f} PPG vs season"

    return f"""
  <style>
  .kyre-v198412-step6{{background:#101c2a;border:1px solid #476d93;border-radius:15px;padding:12px;margin-top:10px}}
  .kyre-v198412-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#8bc9ff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
  .kyre-v198412-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
  .kyre-v198412-grade.elite,.kyre-v198412-grade.favorable{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
  .kyre-v198412-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
  .kyre-v198412-grade.slow{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
  .kyre-v198412-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
  .kyre-v198412-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
  .kyre-v198412-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
  .kyre-v198412-grid div{{border:1px solid #355873;border-radius:10px;padding:8px;background:#091522}}
  .kyre-v198412-grid small{{display:block;color:#789ab5;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
  .kyre-v198412-grid strong{{display:block;color:#f3f9ff;font-size:.84rem;margin-top:3px}}
  .kyre-v198412-detail{{background:#091522;border:1px solid #355873;border-radius:10px;padding:8px 9px;color:#d9e9f6;font-size:.68rem;line-height:1.55;margin-top:8px}}
  .kyre-v198412-detail b{{color:#8bc9ff}}
  .kyre-v198412-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#122033;border:1px solid #476d93;color:#eef7ff;font-size:.68rem;font-weight:850}}
  .kyre-v198412-note{{color:#7890a5;font-size:.57rem;line-height:1.4;margin-top:7px}}
  @media(max-width:760px){{.kyre-v198412-head{{align-items:flex-start;flex-direction:column}}}}
  </style>
  <div class="kyre-v198412-step6">
    <div class="kyre-v198412-head">
      <span>STEP 6 • PACE + GAME SCORING ENVIRONMENT</span>
      <span class="kyre-v198412-grade {grade_class}">{escape(grade)}</span>
    </div>
    <div class="kyre-v198412-grid">
      <div><small>TEAM</small><strong>{team_name}</strong></div>
      <div><small>OPPONENT</small><strong>{opponent}</strong></div>
      <div><small>TEAM L10 PACE</small><strong>{_fmt(team_pace)}</strong></div>
      <div><small>OPP L10 PACE</small><strong>{_fmt(opp_pace)}</strong></div>
      <div><small>EXPECTED MATCHUP PACE</small><strong>{_fmt(expected_pace)}</strong></div>
      <div><small>SLATE PACE BASELINE</small><strong>{_fmt(pace_base)}</strong></div>
      <div><small>PACE DELTA</small><strong>{_fmt(pace_delta,1," poss")}</strong></div>
      <div><small>PROTECTED PACE FACTOR</small><strong>{pace_factor_text}</strong></div>
      <div><small>TEAM L10 OFF RTG</small><strong>{_fmt(team.get("ortg_l10"))}</strong></div>
      <div><small>OPP L10 DEF RTG</small><strong>{_fmt(opp.get("drtg_l10"))}</strong></div>
      <div><small>TEAM SEASON PPG</small><strong>{_fmt(season_pf)}</strong></div>
      <div><small>TEAM L10 PPG</small><strong>{_fmt(l10_pf)}</strong></div>
    </div>
    <div class="kyre-v198412-detail">
      <b>Existing protected pace signal</b> • {pace_effect_text}<br>
      <b>Expected pace source</b> • {escape(source_expected)}<br>
      <b>Team scoring trend</b> • {escape(team_scoring_trend)}<br>
      <b>Environment audit</b> • {evidence_n}/4 available signals • score {score:+d}
    </div>
    <div class="kyre-v198412-verdict">Points environment • {escape(verdict)}</div>
    <div class="kyre-v198412-note">Audit/context only • verified completed-game team context before the selected slate date. Step 6 displays the pace/environment evidence already represented by the protected Points engine and does not apply a second pace, offense or defense adjustment. Projection, Monte Carlo probability and Top-5 order remain unchanged.</div>
  </div>
"""


def _step5_plus_step6(day: str, data: dict) -> str:
    return _ORIGINAL_STEP5_BLOCK(day, data) + _step6_block(day, data)


def _install() -> None:
    prior._step5_block = _step5_plus_step6


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "⚡ Points V1.9.8.4.12 • Step 6 Pace + Game Scoring Environment ACTIVE "
        "inside the same Top-5 cards • audit only • protected model/ranking unchanged"
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
