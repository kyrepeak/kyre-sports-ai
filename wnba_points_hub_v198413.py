"""WNBA Points V1.9.8.4.13 — Step 6 pace-baseline display repair.

Presentation/context-only wrapper over V1.9.8.4.12. The validated V1.9.8.4.5
Points projection, sportsbook transport, Monte Carlo, calibration, candidate
hierarchy, persistence, readiness gates and sanity quarantine remain unchanged.

V1.9.8.4.12 displayed a verified slate audit pace delta beside the protected
model pace_factor even though those values can use different comparison
baselines. That made a negative audit pace delta appear to conflict with a
positive protected factor. V1.9.8.4.13 separates the two namespaces explicitly:
- AUDIT PACE uses verified team/opponent L10 pace and the selected-slate baseline;
- PROTECTED MODEL PACE shows the existing model factor only and never claims the
  audit slate baseline is the model calibration baseline;
- if the protected model baseline is not exposed by the production row, the card
  says so instead of reverse-engineering or inventing one.

No probability, projection, Monte Carlo, ranking or model feature is changed.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198412 as prior

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.13 • STEP 6 PACE BASELINE REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _step6_block(day: str, data: dict) -> str:
    """Render Step 6 with audit and protected pace contexts kept separate."""
    try:
        team_id = int(float(data.get("TEAM_ID")))
    except Exception:
        team_id = 0
    try:
        opp_id = int(float(data.get("opponent_team_id")))
    except Exception:
        opp_id = 0

    team = prior._team_environment(day, team_id) if team_id else {}
    opp = prior._team_environment(day, opp_id) if opp_id else {}
    baseline = prior._slate_environment_baseline(day)

    team_pace = _num(team.get("pace_l10"), np.nan)
    opp_pace = _num(opp.get("pace_l10"), np.nan)

    # Audit pace is deliberately self-contained: verified L10 team/opponent pace
    # compared only with the verified selected-slate L10 baseline.
    audit_expected = prior._mean_valid([team_pace, opp_pace])
    audit_base = _num(baseline.get("pace"), np.nan)
    audit_delta = audit_expected - audit_base if pd.notna(audit_expected) and pd.notna(audit_base) else np.nan
    audit_ratio = audit_expected / audit_base if pd.notna(audit_expected) and pd.notna(audit_base) and audit_base > 0 else np.nan
    audit_ratio_text = "—" if pd.isna(audit_ratio) else f"{audit_ratio:.3f}×"
    audit_effect_text = "—" if pd.isna(audit_ratio) else f"{(audit_ratio - 1.0) * 100.0:+.1f}% vs slate baseline"

    # Protected values are shown exactly as produced by the existing model row.
    # They are NOT recomputed from the audit baseline.
    protected_expected = _num(data.get("expected_pace"), np.nan)
    protected_factor = _num(data.get("pace_factor"), np.nan)
    protected_expected_text = _fmt(protected_expected)
    protected_factor_text = "—" if pd.isna(protected_factor) else f"{protected_factor:.3f}×"
    protected_effect_text = "—" if pd.isna(protected_factor) else f"{(protected_factor - 1.0) * 100.0:+.1f}% model pace factor"

    # Do not reverse-engineer a baseline from a potentially capped/transformed
    # factor. Only display a baseline if the production row explicitly exposes it.
    model_base = np.nan
    model_base_source = "NOT EXPOSED BY PROTECTED RUNTIME"
    for key in ("pace_baseline", "PACE_BASELINE", "pace_base", "PACE_BASE", "model_pace_baseline"):
        candidate = _num(data.get(key), np.nan)
        if pd.notna(candidate) and candidate > 0:
            model_base = candidate
            model_base_source = f"EXPOSED FIELD • {key}"
            break
    model_base_text = _fmt(model_base)

    grade, grade_class, verdict, score, evidence_n = prior._environment_grade(
        team, opp, baseline, audit_expected
    )

    team_name = escape(str(data.get("team_name") or "Team"))
    opponent = escape(str(data.get("opponent") or "Opponent"))

    season_pf = _num(team.get("season_pf"), np.nan)
    l10_pf = _num(team.get("l10_pf"), np.nan)
    team_scoring_trend = "DATA LIMITED"
    if pd.notna(season_pf) and pd.notna(l10_pf):
        delta = l10_pf - season_pf
        if delta >= 2.0:
            team_scoring_trend = f"RISING • L10 {delta:+.1f} PPG vs season"
        elif delta <= -2.0:
            team_scoring_trend = f"COOLING • L10 {delta:+.1f} PPG vs season"
        else:
            team_scoring_trend = f"STABLE • L10 {delta:+.1f} PPG vs season"

    comparison_note = "SEPARATE BASELINES • DO NOT DIRECTLY COMPARE"
    if pd.notna(model_base) and pd.notna(audit_base) and abs(model_base - audit_base) < 0.05:
        comparison_note = "BASELINES MATCH WITHIN DISPLAY PRECISION"

    return f"""
  <style>
  .kyre-v198413-step6{{background:#101c2a;border:1px solid #476d93;border-radius:15px;padding:12px;margin-top:10px}}
  .kyre-v198413-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#8bc9ff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
  .kyre-v198413-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
  .kyre-v198413-grade.elite,.kyre-v198413-grade.favorable{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
  .kyre-v198413-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
  .kyre-v198413-grade.slow{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
  .kyre-v198413-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
  .kyre-v198413-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
  .kyre-v198413-subhead{{color:#8bc9ff;font-size:.54rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:10px 0 7px}}
  .kyre-v198413-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
  .kyre-v198413-grid div{{border:1px solid #355873;border-radius:10px;padding:8px;background:#091522}}
  .kyre-v198413-grid small{{display:block;color:#789ab5;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
  .kyre-v198413-grid strong{{display:block;color:#f3f9ff;font-size:.84rem;margin-top:3px}}
  .kyre-v198413-model{{background:#0e1723;border:1px solid #6a5b8d;border-radius:10px;padding:9px;margin-top:9px}}
  .kyre-v198413-model .label{{color:#c1a8ff;font-size:.54rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin-bottom:7px}}
  .kyre-v198413-modelgrid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
  .kyre-v198413-modelgrid div{{background:#0a111b;border:1px solid #4a4263;border-radius:9px;padding:8px}}
  .kyre-v198413-modelgrid small{{display:block;color:#9b8db7;font-size:.47rem;font-weight:900}}
  .kyre-v198413-modelgrid strong{{display:block;color:#f6f1ff;font-size:.78rem;margin-top:3px}}
  .kyre-v198413-sep{{margin-top:7px;color:#d4c4f2;font-size:.59rem;line-height:1.45}}
  .kyre-v198413-detail{{background:#091522;border:1px solid #355873;border-radius:10px;padding:8px 9px;color:#d9e9f6;font-size:.68rem;line-height:1.55;margin-top:8px}}
  .kyre-v198413-detail b{{color:#8bc9ff}}
  .kyre-v198413-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#122033;border:1px solid #476d93;color:#eef7ff;font-size:.68rem;font-weight:850}}
  .kyre-v198413-note{{color:#7890a5;font-size:.57rem;line-height:1.4;margin-top:7px}}
  @media(max-width:760px){{.kyre-v198413-head{{align-items:flex-start;flex-direction:column}}}}
  </style>
  <div class="kyre-v198413-step6">
    <div class="kyre-v198413-head">
      <span>STEP 6 • PACE + GAME SCORING ENVIRONMENT</span>
      <span class="kyre-v198413-grade {grade_class}">{escape(grade)}</span>
    </div>

    <div class="kyre-v198413-subhead">AUDIT PACE • VERIFIED L10 VS SELECTED-SLATE BASELINE</div>
    <div class="kyre-v198413-grid">
      <div><small>TEAM</small><strong>{team_name}</strong></div>
      <div><small>OPPONENT</small><strong>{opponent}</strong></div>
      <div><small>TEAM L10 PACE</small><strong>{_fmt(team_pace)}</strong></div>
      <div><small>OPP L10 PACE</small><strong>{_fmt(opp_pace)}</strong></div>
      <div><small>AUDIT MATCHUP PACE</small><strong>{_fmt(audit_expected)}</strong></div>
      <div><small>SLATE AUDIT BASELINE</small><strong>{_fmt(audit_base)}</strong></div>
      <div><small>AUDIT PACE DELTA</small><strong>{_fmt(audit_delta,1," poss")}</strong></div>
      <div><small>AUDIT PACE RATIO</small><strong>{audit_ratio_text}</strong></div>
      <div><small>TEAM L10 OFF RTG</small><strong>{_fmt(team.get("ortg_l10"))}</strong></div>
      <div><small>OPP L10 DEF RTG</small><strong>{_fmt(opp.get("drtg_l10"))}</strong></div>
      <div><small>TEAM SEASON PPG</small><strong>{_fmt(season_pf)}</strong></div>
      <div><small>TEAM L10 PPG</small><strong>{_fmt(l10_pf)}</strong></div>
    </div>

    <div class="kyre-v198413-model">
      <div class="label">PROTECTED MODEL PACE • SEPARATE CALIBRATION CONTEXT</div>
      <div class="kyre-v198413-modelgrid">
        <div><small>MODEL EXPECTED PACE</small><strong>{protected_expected_text}</strong></div>
        <div><small>MODEL PACE FACTOR</small><strong>{protected_factor_text}</strong></div>
        <div><small>MODEL PACE BASELINE</small><strong>{model_base_text}</strong></div>
        <div><small>BASELINE STATUS</small><strong>{escape(model_base_source)}</strong></div>
      </div>
      <div class="kyre-v198413-sep"><b>{escape(comparison_note)}</b> • audit ratio is {audit_effect_text}; protected factor is {protected_effect_text}. Step 6 never substitutes the audit baseline into protected model math.</div>
    </div>

    <div class="kyre-v198413-detail">
      <b>Team scoring trend</b> • {escape(team_scoring_trend)}<br>
      <b>Environment audit</b> • {evidence_n}/4 available signals • score {score:+d}<br>
      <b>Grade basis</b> • verified audit pace + team L10 offense + opponent L10 defense + team L10 scoring
    </div>
    <div class="kyre-v198413-verdict">Points environment • {escape(verdict)}</div>
    <div class="kyre-v198413-note">Audit/context only • V1.9.8.4.13 separates the verified slate audit baseline from the protected model pace factor so opposite-signed values are never presented as if they share one denominator. No projection, Monte Carlo probability, calibration or Top-5 ordering is changed.</div>
  </div>
"""


def _install() -> None:
    # v198412's embedded Step-6 combiner resolves its module-global
    # _step6_block at render time, so replacing only this presentation seam is
    # enough to repair the card without touching any protected model function.
    prior._step6_block = _step6_block


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🔧 Points V1.9.8.4.13 • Step 6 pace-baseline separation ACTIVE • "
        "audit pace and protected model pace are displayed in separate contexts"
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
