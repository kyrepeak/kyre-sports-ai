"""WNBA Points V1.9.8.4.11 — embedded Step 5 opponent defense + positional matchup.

Presentation/context-only wrapper over V1.9.8.4.10. The validated V1.9.8.4.5
Points projection, SportsGameOdds transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and player-level sanity
quarantine remain unchanged.

Step 5 is restricted to the same Top-5 candidates already rendered by Steps
2-4. It exposes the defense and positional residuals already produced by the
protected Points model plus verified opponent season/recent points allowed.
It does not add a second defensive adjustment and cannot rerank the Top 5.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198410 as prior
import wnba_context_v26 as context

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.11 • STEP 5 OPPONENT DEFENSE + POSITION"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_STEP4_BLOCK = prior._step4_block


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    if abs(x) <= 1.5:
        x *= 100.0
    return f"{x:.{digits}f}%"


@st.cache_data(ttl=900, show_spinner=False, max_entries=64)
def _team_defense_record(day_str: str, team_id: int) -> dict:
    """Verified season/L10 scoreboard run-prevention profile before day_str."""
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
        summary = context._record_summary(frame, tid) or {}
    except Exception:
        summary = {}
    return {
        "gp": int(_num(summary.get("GP"), 0)),
        "season_pa": _num(summary.get("PA"), np.nan),
        "l10_pa": _num(summary.get("L10_PA"), np.nan),
        "l10_w": int(_num(summary.get("L10_W"), 0)),
        "l10_l": int(_num(summary.get("L10_L"), 0)),
    }


def _defense_grade(data: dict) -> tuple[str, str, str]:
    """Describe the exact protected defense + position residual without reapplying it."""
    defense_factor = _num(data.get("defense_factor"), 1.0)
    position_factor = _num(data.get("position_factor"), 1.0)
    protected_residual = float(np.clip((defense_factor ** 0.85) * position_factor, 0.90, 1.10))

    if protected_residual >= 1.035:
        return "ELITE MATCHUP", "elite", "SUPPORTS SCORER"
    if protected_residual >= 1.015:
        return "FAVORABLE", "favorable", "SUPPORTS SCORER"
    if protected_residual <= 0.965:
        return "HARD MATCHUP", "hard", "HURTS SCORER"
    if protected_residual <= 0.985:
        return "TOUGH", "tough", "HURTS SCORER"
    return "NEUTRAL", "neutral", "NEUTRAL"


def _recent_defense_trend(season_pa, l10_pa) -> str:
    s = _num(season_pa, np.nan)
    r = _num(l10_pa, np.nan)
    if pd.isna(s) or pd.isna(r):
        return "DATA LIMITED"
    delta = r - s
    if delta <= -2.0:
        return f"IMPROVING DEFENSE • L10 {delta:+.1f} PA/G vs season"
    if delta >= 2.0:
        return f"WEAKENING DEFENSE • L10 {delta:+.1f} PA/G vs season"
    return f"STABLE DEFENSE • L10 {delta:+.1f} PA/G vs season"


def _step5_block(day: str, data: dict) -> str:
    opponent = escape(str(data.get("opponent") or "Opponent"))

    try:
        opp_id = int(float(data.get("opponent_team_id")))
    except Exception:
        opp_id = 0
    record = _team_defense_record(day, opp_id) if opp_id else {}

    grade, grade_class, verdict = _defense_grade(data)
    defense_factor = _num(data.get("defense_factor"), np.nan)
    pos_factor = _num(data.get("position_factor"), np.nan)
    pos_bucket = escape(str(data.get("position_bucket") or "UNKNOWN"))
    pos_games = int(_num(data.get("position_games"), 0))
    pos_share = _num(data.get("position_allow_share"), np.nan)
    base_share = _num(data.get("position_baseline_share"), np.nan)
    share_delta = (pos_share - base_share) * 100.0 if pd.notna(pos_share) and pd.notna(base_share) else np.nan
    opp_drtg = _num(data.get("opp_drtg_l10"), np.nan)
    opp_pa_l10_model = _num(data.get("opp_pa_l10"), np.nan)
    context_quality = _num(data.get("context_quality"), np.nan)
    defense_source = escape(str(data.get("defense_source") or "neutral"))
    position_source = escape(str(data.get("position_source") or "neutral"))

    season_pa = _num(record.get("season_pa"), np.nan)
    l10_pa = _num(record.get("l10_pa"), opp_pa_l10_model)
    gp = int(record.get("gp") or 0)
    trend = escape(_recent_defense_trend(season_pa, l10_pa))
    l10_record = "—" if not record else f"{int(record.get('l10_w') or 0)}-{int(record.get('l10_l') or 0)}"

    if pd.notna(defense_factor):
        def_adj_text = f"{(defense_factor ** 0.85 - 1.0) * 100.0:+.1f}%"
    else:
        def_adj_text = "—"
    if pd.notna(pos_factor):
        pos_adj_text = f"{(pos_factor - 1.0) * 100.0:+.1f}%"
    else:
        pos_adj_text = "—"

    position_sample = f"{pos_games} opponent games" if pos_games else "DATA LIMITED"

    return f"""
  <style>
  .kyre-v198411-step5{{background:#0d2021;border:1px solid #3d756f;border-radius:15px;padding:12px;margin-top:10px}}
  .kyre-v198411-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#78e6d4;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
  .kyre-v198411-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
  .kyre-v198411-grade.elite,.kyre-v198411-grade.favorable{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
  .kyre-v198411-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
  .kyre-v198411-grade.tough{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
  .kyre-v198411-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
  .kyre-v198411-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
  .kyre-v198411-grid div{{border:1px solid #315b58;border-radius:10px;padding:8px;background:#081718}}
  .kyre-v198411-grid small{{display:block;color:#78a6a0;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
  .kyre-v198411-grid strong{{display:block;color:#f3fffd;font-size:.84rem;margin-top:3px}}
  .kyre-v198411-detail{{background:#081718;border:1px solid #315b58;border-radius:10px;padding:8px 9px;color:#d8eeea;font-size:.68rem;line-height:1.55;margin-top:8px}}
  .kyre-v198411-detail b{{color:#78e6d4}}
  .kyre-v198411-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#122521;border:1px solid #3d756f;color:#ecfff9;font-size:.68rem;font-weight:850}}
  .kyre-v198411-note{{color:#75938f;font-size:.57rem;line-height:1.4;margin-top:7px}}
  @media(max-width:760px){{.kyre-v198411-head{{align-items:flex-start;flex-direction:column}}}}
  </style>
  <div class="kyre-v198411-step5">
    <div class="kyre-v198411-head">
      <span>STEP 5 • OPPONENT DEFENSE + POSITIONAL MATCHUP</span>
      <span class="kyre-v198411-grade {grade_class}">{escape(grade)}</span>
    </div>
    <div class="kyre-v198411-grid">
      <div><small>OPPONENT</small><strong>{opponent}</strong></div>
      <div><small>SEASON GAMES</small><strong>{gp if gp else "—"}</strong></div>
      <div><small>SEASON PA/G</small><strong>{_fmt(season_pa)}</strong></div>
      <div><small>L10 PA/G</small><strong>{_fmt(l10_pa)}</strong></div>
      <div><small>L10 DEF RTG</small><strong>{_fmt(opp_drtg)}</strong></div>
      <div><small>L10 RECORD</small><strong>{l10_record}</strong></div>
      <div><small>PLAYER POSITION BUCKET</small><strong>{pos_bucket}</strong></div>
      <div><small>POSITION SAMPLE</small><strong>{position_sample}</strong></div>
      <div><small>OPP POSITION PTS SHARE</small><strong>{_pct(pos_share)}</strong></div>
      <div><small>SLATE BASELINE SHARE</small><strong>{_pct(base_share)}</strong></div>
      <div><small>POSITION SHARE DELTA</small><strong>{_fmt(share_delta,1," pp")}</strong></div>
      <div><small>CONTEXT QUALITY</small><strong>{_pct(context_quality)}</strong></div>
    </div>
    <div class="kyre-v198411-detail">
      <b>Protected model defense residual</b> • {def_adj_text} scoring effect from team defense<br>
      <b>Protected positional residual</b> • {pos_adj_text} from {pos_bucket} scoring-share matchup<br>
      <b>Recent defense trend</b> • {trend}<br>
      <b>Sources</b> • {defense_source} • {position_source}
    </div>
    <div class="kyre-v198411-verdict">Points context • {escape(verdict)}</div>
    <div class="kyre-v198411-note">Audit/context only • Step 5 displays defense/position evidence already represented by the protected Points engine plus verified scoreboard context. It does not apply either factor a second time and cannot change projection, Monte Carlo probability or Top-5 order.</div>
  </div>
"""


def _step4_plus_step5(day: str, line: float, data: dict) -> str:
    return _ORIGINAL_STEP4_BLOCK(day, line, data) + _step5_block(day, data)


def _install() -> None:
    prior._step4_block = _step4_plus_step5


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🛡️ Points V1.9.8.4.11 • Step 5 Opponent Defense + Positional Matchup ACTIVE "
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
