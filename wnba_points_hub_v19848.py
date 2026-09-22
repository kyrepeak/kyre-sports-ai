"""WNBA Points V1.9.8.4.8 — Step 3 minutes + role + usage audit.

Presentation/context-only wrapper over V1.9.8.4.6. The validated V1.9.8.4.5
Points projection, SportsGameOdds transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and player-level sanity
quarantine remain unchanged.

Step 3 is restricted to the same Top-5 player-vs-team-history candidates already
shown by V1.9.8.4.6. It exposes existing production fields only: projected
minutes, recent team-rotation minutes, player-form minutes, usage, role/status,
minute delta and base scoring rate. It adds no new projection adjustment and
cannot rerank the Top 5.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19846 as evidence
import wnba_points_hub_v194 as h2h

# Genuine V1.9.8.4.5 runtime object loaded by the clean import chain.
base = evidence.prior
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.8 • STEP 3 MINUTES ROLE USAGE"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Save the verified V1.9.8.4.6 H2H renderer before replacing its presentation hook.
_ORIGINAL_H2H_RENDER = evidence._render_top5_h2h_evidence


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix=""):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _pct(value):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    # Provider/role layers normally store usage as 0-100, but tolerate ratios.
    if 0 <= x <= 1.5:
        x *= 100.0
    return f"{x:.1f}%"


def _truthy(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value or "").strip().upper()
    return text in {"1", "TRUE", "YES", "Y", "STARTER", "CONFIRMED"}


def _production_projection_frame(day: str) -> pd.DataFrame:
    """Read existing projection fields without changing the live prepare function."""
    try:
        prepare = getattr(base, "_ORIGINAL_PREPARE", None)
        if prepare is None:
            prepare = points._prepare
        projections, _pairs, _snap, _meta, _lineups = prepare(str(day))
    except Exception:
        return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()
    frame = projections.copy()
    if "game_id" in frame.columns:
        frame["game_id"] = frame["game_id"].astype(str)
    if "player_key" in frame.columns:
        frame["player_key"] = frame["player_key"].astype(str)
    if {"game_id", "player_key"}.issubset(frame.columns):
        frame = frame.drop_duplicates(["game_id", "player_key"], keep="first")
    return frame


def _same_top5(day: str) -> pd.DataFrame:
    try:
        context = h2h._candidate_order(day, h2h._history_context_rows(day))
    except Exception:
        return pd.DataFrame()
    if not isinstance(context, pd.DataFrame) or context.empty:
        return pd.DataFrame()
    top = context.loc[
        ~context["Decision"].astype(str).str.contains("AVOID", na=False)
    ].head(5)
    return context.head(5) if top.empty else top


def _match_projection(projections: pd.DataFrame, row) -> dict:
    if projections is None or projections.empty:
        return {}
    gid = str(row.get("game_id") or "")
    pkey = str(row.get("player_key") or "")
    matched = projections
    if {"game_id", "player_key"}.issubset(projections.columns):
        matched = projections.loc[
            projections["game_id"].astype(str).eq(gid)
            & projections["player_key"].astype(str).eq(pkey)
        ]
    if matched.empty:
        pid = str(row.get("PLAYER_ID") or "").replace(".0", "")
        if pid and "PLAYER_ID" in projections.columns:
            matched = projections.loc[
                projections["PLAYER_ID"].astype(str).str.replace(".0", "", regex=False).eq(pid)
            ]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _usage_value(data: dict):
    for key in ("L5_USG_PCT", "L10_USG_PCT", "USG_PCT"):
        value = _num(data.get(key), np.nan)
        if pd.notna(value):
            if 0 <= value <= 1.5:
                value *= 100.0
            return value
    return np.nan


def _opportunity_grade(data: dict) -> tuple[str, str]:
    mins = _num(data.get("PROJ_MIN"), np.nan)
    usage = _usage_value(data)
    if pd.notna(mins) and pd.notna(usage):
        if mins >= 32 and usage >= 24:
            return "ELITE OPPORTUNITY", "elite"
        if mins >= 28 and usage >= 20:
            return "STRONG OPPORTUNITY", "strong"
        if mins >= 23:
            return "NORMAL OPPORTUNITY", "normal"
        return "LIMITED OPPORTUNITY", "limited"
    if pd.notna(mins):
        if mins >= 33:
            return "STRONG MINUTES • USAGE LIMITED", "strong"
        if mins >= 24:
            return "NORMAL MINUTES • USAGE LIMITED", "normal"
        return "LIMITED MINUTES • USAGE LIMITED", "limited"
    return "DATA LIMITED", "limited"


def _minute_trend(data: dict) -> str:
    proj = _num(data.get("PROJ_MIN"), np.nan)
    recent = _num(data.get("RECENT_TEAM_L3_MIN"), np.nan)
    if pd.isna(recent):
        recent = _num(data.get("RECENT_TEAM_L5_MIN"), np.nan)
    if pd.isna(proj) or pd.isna(recent):
        return "DATA LIMITED"
    delta = proj - recent
    if delta >= 3.0:
        return f"EXPANDED ROLE • {delta:+.1f} MIN vs recent"
    if delta <= -3.0:
        return f"REDUCED ROLE • {delta:+.1f} MIN vs recent"
    return f"STABLE ROLE • {delta:+.1f} MIN vs recent"


def _role_text(data: dict) -> str:
    role = str(data.get("ROLE_LABEL") or "").strip()
    designation = str(data.get("DESIGNATION") or "").strip()
    starter = _truthy(data.get("STARTER_CONFIRMED"))
    parts = []
    if starter:
        parts.append("CONFIRMED STARTER")
    elif role:
        parts.append(role.upper())
    else:
        parts.append("ROTATION ROLE")
    if designation and designation.upper() not in {"ACTIVE", "AVAILABLE", "NONE", "NAN"}:
        parts.append(designation.upper())
    return " • ".join(parts)


def _render_step3_role_usage(day: str) -> None:
    top = _same_top5(day)
    projections = _production_projection_frame(day)

    st.markdown("### ⏱️ Step 3 — Minutes + Role + Usage")
    st.caption(
        "Same Top-5 Points candidates as Player vs Team History. Existing production values only — "
        "this audit does not add a new minutes/usage adjustment, change Monte Carlo, or rerank the Top 5."
    )

    if top.empty:
        st.info("Step 3 is waiting on the verified Top-5 Points candidate handoff.")
        return

    cards = []
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        data = _match_projection(projections, row)
        player = escape(str(row.get("Player") or row.get("PLAYER_NAME") or "WNBA Player"))
        team = escape(str(row.get("team_name") or data.get("team_name") or "Team"))
        opponent = escape(str(row.get("opponent") or data.get("opponent") or "Opponent"))

        grade, grade_class = _opportunity_grade(data)
        trend = escape(_minute_trend(data))
        role_text = escape(_role_text(data))

        proj_min = _fmt(data.get("PROJ_MIN"))
        l3_team = _fmt(data.get("RECENT_TEAM_L3_MIN"))
        l5_team = _fmt(data.get("RECENT_TEAM_L5_MIN"))
        l10_min = _fmt(data.get("L10_MIN"))
        l5_min = _fmt(data.get("L5_MIN"))
        season_min = _fmt(data.get("MIN"))
        usg = _pct(data.get("USG_PCT"))
        l10_usg = _pct(data.get("L10_USG_PCT"))
        l5_usg = _pct(data.get("L5_USG_PCT"))
        usage_ratio = _num(data.get("USG_RATIO"), np.nan)
        usage_ratio_text = "—" if pd.isna(usage_ratio) else f"{usage_ratio:.2f}×"
        min_delta = _num(data.get("MIN_DELTA"), np.nan)
        min_delta_text = "—" if pd.isna(min_delta) else f"{min_delta:+.1f}"
        pts_rate = _num(data.get("PTS_RATE"), np.nan)
        pts_rate_text = "—" if pd.isna(pts_rate) else f"{pts_rate:.3f} PTS/min"
        source = escape(str(data.get("MINUTES_SOURCE") or "Existing Points rotation/minutes engine"))

        cards.append(f"""
<div class="kyre-p3-card">
  <div class="kyre-p3-head"><span>🏀 TOP {rank} • {player}</span><span class="kyre-p3-grade {grade_class}">{escape(grade)}</span></div>
  <div class="kyre-p3-match">{team} vs {opponent}</div>
  <div class="kyre-p3-role"><b>Role</b> • {role_text}<br><b>Minutes trend</b> • {trend}</div>
  <div class="kyre-p3-grid">
    <div><small>PROJECTED MIN</small><strong>{proj_min}</strong></div>
    <div><small>SEASON MIN</small><strong>{season_min}</strong></div>
    <div><small>TEAM ROTATION L3</small><strong>{l3_team}</strong></div>
    <div><small>TEAM ROTATION L5</small><strong>{l5_team}</strong></div>
    <div><small>PLAYER L10 MIN</small><strong>{l10_min}</strong></div>
    <div><small>PLAYER L5 MIN</small><strong>{l5_min}</strong></div>
    <div><small>SEASON USAGE</small><strong>{usg}</strong></div>
    <div><small>L10 USAGE</small><strong>{l10_usg}</strong></div>
    <div><small>L5 USAGE</small><strong>{l5_usg}</strong></div>
    <div><small>USAGE RATIO</small><strong>{usage_ratio_text}</strong></div>
    <div><small>MIN DELTA VS BASE</small><strong>{min_delta_text}</strong></div>
    <div><small>BASE SCORING RATE</small><strong>{pts_rate_text}</strong></div>
  </div>
  <div class="kyre-p3-source">Minutes source • {source}</div>
  <div class="kyre-p3-note">Audit/context only • values are already produced by the protected Points engine • Step 3 adds no new probability adjustment.</div>
</div>
""")

    st.markdown(
        """
<style>
.kyre-p3-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 16px}
.kyre-p3-card{background:linear-gradient(145deg,#101b31,#081522);border:1px solid #45627e;border-radius:20px;padding:16px;box-shadow:0 8px 22px rgba(0,0,0,.17)}
.kyre-p3-head{display:flex;justify-content:space-between;align-items:center;gap:10px;color:#7fceff;font-size:.66rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.kyre-p3-grade{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.57rem}.kyre-p3-grade.elite{background:#0b422f;color:#7df2ba;border:1px solid #237a59}.kyre-p3-grade.strong{background:#103a32;color:#7ce7c2;border:1px solid #2c7463}.kyre-p3-grade.normal{background:#3a3009;color:#ffe17a;border:1px solid #756313}.kyre-p3-grade.limited{background:#34202a;color:#ffb1c0;border:1px solid #724457}
.kyre-p3-match{color:#9eb1c2;font-size:.76rem;margin:7px 0 10px}.kyre-p3-role{background:#0a1b2a;border:1px solid #294b64;border-radius:11px;padding:9px 10px;color:#dce9f4;font-size:.72rem;line-height:1.55;margin-bottom:9px}.kyre-p3-role b{color:#86d9ff}
.kyre-p3-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.kyre-p3-grid div{background:#091827;border:1px solid #27475f;border-radius:10px;padding:8px}.kyre-p3-grid small{display:block;color:#718ba0;font-size:.48rem;font-weight:900;letter-spacing:.045em}.kyre-p3-grid strong{display:block;color:#f6fbff;font-size:.84rem;margin-top:3px}
.kyre-p3-source{color:#91a9bb;font-size:.64rem;margin-top:10px}.kyre-p3-note{color:#72899b;font-size:.59rem;line-height:1.45;margin-top:5px}
@media(max-width:760px){.kyre-p3-wrap{grid-template-columns:1fr}.kyre-p3-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kyre-p3-head{align-items:flex-start;flex-direction:column}}
</style>
<div class="kyre-p3-wrap">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def _render_h2h_plus_step3(day: str) -> None:
    _ORIGINAL_H2H_RENDER(day)
    _render_step3_role_usage(day)


def _install() -> None:
    # V1.9.8.4.6's own install routine reads this symbol at render time, so
    # replacing it here makes the existing route install our combined renderer
    # into both historical H2H hooks without touching model/data functions.
    evidence._render_top5_h2h_evidence = _render_h2h_plus_step3


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "⏱️ Points V1.9.8.4.8 • Step 3 Minutes + Role + Usage ACTIVE for the same Top 5 • "
        "presentation audit only • protected model/ranking unchanged"
    )
    return evidence.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(evidence, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "base", "v171", "ui", "points",
    "render_wnba_points_hub",
]
