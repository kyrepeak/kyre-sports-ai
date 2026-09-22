"""WNBA Points V1.9.8.4.10 — embedded Step 4 recent scoring form.

Presentation/context-only wrapper over V1.9.8.4.9. The validated V1.9.8.4.5
Points projection, SportsGameOdds transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and player-level sanity
quarantine remain unchanged.

Step 4 is restricted to the same Top-5 candidates already rendered by the
Step-2/Step-3 card. It uses verified completed ESPN WNBA box scores before the
selected slate date to expose recent scoring form versus today's exact Points
line. The recent-form panel is descriptive only and adds no projection weight,
probability adjustment or reranking.
"""
from __future__ import annotations

from contextvars import ContextVar
from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19849 as prior
import wnba_points_v13 as roster_mod
import wnba_players_v25 as players

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.10 • STEP 4 RECENT SCORING FORM"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_STEP3_BLOCK = prior._step3_block
_ORIGINAL_TOP5_RENDER = prior._render_top5_h2h_with_embedded_step3
_STEP4_CONTEXT = ContextVar("wnba_points_v198410_step4_context", default={})


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _id_text(value) -> str:
    try:
        return str(int(float(value)))
    except Exception:
        return str(value or "").strip()


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


@st.cache_data(ttl=900, show_spinner=False, max_entries=128)
def _recent_player_points(day_str: str, team_id: int, player_id: int) -> pd.DataFrame:
    """Last ten verified player appearances before day_str for the current team."""
    try:
        day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
        tid = int(team_id or 0)
        pid = int(player_id or 0)
    except Exception:
        return pd.DataFrame()
    if not tid or not pid:
        return pd.DataFrame()

    try:
        history = roster_mod._season_history(day_str, {tid})
    except Exception:
        history = pd.DataFrame()
    if history is None or history.empty:
        return pd.DataFrame()

    games = history.loc[
        history["away_team_id"].astype(int).eq(tid)
        | history["home_team_id"].astype(int).eq(tid)
    ].copy()
    if games.empty:
        return pd.DataFrame()

    games["_DATE"] = pd.to_datetime(games.get("game_date"), errors="coerce")
    # Pull a few extra team games so an isolated DNP does not turn a player's
    # L10 appearance audit into an artificially short sample.
    games = (
        games.sort_values("_DATE", ascending=False)
        .drop_duplicates("game_id", keep="first")
        .head(15)
    )

    rows = []
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            box = players._espn_game_summary(gid, gdate)
        except Exception:
            box = pd.DataFrame()
        if box is None or box.empty or "TEAM_ID" not in box.columns:
            continue

        part = box.loc[
            pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(tid)
            & pd.to_numeric(box.get("PLAYER_ID"), errors="coerce").eq(pid)
        ].copy()
        if part.empty:
            continue
        r = part.iloc[0]
        pts = _num(r.get("PTS"), np.nan)
        mins = _num(r.get("MIN"), np.nan)
        if pd.isna(pts):
            continue
        rows.append({
            "GAME_DATE": pd.to_datetime(r.get("GAME_DATE") or gdate, errors="coerce"),
            "PTS": float(pts),
            "MIN": mins,
            "GAME_ID": gid,
        })
        if len(rows) >= 10:
            break

    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values("GAME_DATE", ascending=False)
        .drop_duplicates("GAME_ID", keep="first")
        .head(10)
        .reset_index(drop=True)
    )


def _recent_summary(logs: pd.DataFrame, line: float, data: dict) -> dict:
    season_ppg = _num(data.get("PTS"), np.nan)
    l10_ppg = _num(data.get("L10_PTS"), np.nan)
    l5_ppg = _num(data.get("L5_PTS"), np.nan)

    frame = logs.copy() if isinstance(logs, pd.DataFrame) else pd.DataFrame()
    if not frame.empty:
        frame["PTS"] = pd.to_numeric(frame.get("PTS"), errors="coerce")
        frame = frame.dropna(subset=["PTS"]).head(10)
    l10 = frame.head(10)
    l5 = frame.head(5)

    if pd.isna(l10_ppg) and not l10.empty:
        l10_ppg = float(l10["PTS"].mean())
    if pd.isna(l5_ppg) and not l5.empty:
        l5_ppg = float(l5["PTS"].mean())

    line_ok = pd.notna(line)
    l5_over = int((l5["PTS"] > line).sum()) if line_ok and not l5.empty else 0
    l10_over = int((l10["PTS"] > line).sum()) if line_ok and not l10.empty else 0
    l5_push = int((l5["PTS"] == line).sum()) if line_ok and not l5.empty else 0
    l10_push = int((l10["PTS"] == line).sum()) if line_ok and not l10.empty else 0
    l5_rate = l5_over / len(l5) if line_ok and len(l5) else np.nan
    l10_rate = l10_over / len(l10) if line_ok and len(l10) else np.nan
    l5_margin = float((l5["PTS"] - line).mean()) if line_ok and len(l5) else np.nan
    l10_margin = float((l10["PTS"] - line).mean()) if line_ok and len(l10) else np.nan

    delta = l5_ppg - l10_ppg if pd.notna(l5_ppg) and pd.notna(l10_ppg) else np.nan
    if pd.isna(delta):
        trend = "DATA LIMITED"
    elif delta >= 1.5:
        trend = f"RISING • L5 vs L10 {delta:+.1f} PPG"
    elif delta <= -1.5:
        trend = f"FALLING • L5 vs L10 {delta:+.1f} PPG"
    else:
        trend = f"STABLE • L5 vs L10 {delta:+.1f} PPG"

    if len(l5) < 3 or not line_ok:
        grade, grade_class = "DATA LIMITED", "limited"
    elif l5_rate >= 0.80 and pd.notna(l5_ppg) and l5_ppg >= line + 2.0:
        grade, grade_class = "ELITE RECENT FORM", "elite"
    elif l5_rate >= 0.60 and pd.notna(l5_ppg) and l5_ppg >= line:
        grade, grade_class = "STRONG RECENT FORM", "strong"
    elif l5_rate <= 0.20 and pd.notna(l5_ppg) and l5_ppg <= line - 2.0:
        grade, grade_class = "COLD RECENT FORM", "cold"
    else:
        grade, grade_class = "MIXED RECENT FORM", "mixed"

    sequence = " • ".join(f"{x:.0f}" for x in l5["PTS"].tolist()) if len(l5) else "—"
    return {
        "season_ppg": season_ppg,
        "l10_ppg": l10_ppg,
        "l5_ppg": l5_ppg,
        "l5_n": int(len(l5)),
        "l10_n": int(len(l10)),
        "l5_over": l5_over,
        "l10_over": l10_over,
        "l5_push": l5_push,
        "l10_push": l10_push,
        "l5_rate": l5_rate,
        "l10_rate": l10_rate,
        "l5_margin": l5_margin,
        "l10_margin": l10_margin,
        "sequence": sequence,
        "trend": trend,
        "grade": grade,
        "grade_class": grade_class,
    }


def _rate_text(over: int, pushes: int, n: int, rate: float) -> str:
    if not n or pd.isna(rate):
        return "—"
    push = f" • {pushes} push" if pushes else ""
    return f"{over}/{n} • {rate*100:.0f}%{push}"


def _step4_block(day: str, line: float, data: dict) -> str:
    try:
        tid = int(float(data.get("TEAM_ID")))
        pid = int(float(data.get("PLAYER_ID")))
    except Exception:
        tid = pid = 0

    logs = _recent_player_points(day, tid, pid) if tid and pid else pd.DataFrame()
    summary = _recent_summary(logs, line, data)

    l5_rate_text = _rate_text(
        summary["l5_over"], summary["l5_push"], summary["l5_n"], summary["l5_rate"]
    )
    l10_rate_text = _rate_text(
        summary["l10_over"], summary["l10_push"], summary["l10_n"], summary["l10_rate"]
    )
    line_text = "—" if pd.isna(line) else f"{line:.1f}"

    return f"""
  <style>
  .kyre-v198410-step4{{background:#21162a;border:1px solid #73518a;border-radius:15px;padding:12px;margin-top:10px}}
  .kyre-v198410-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#dfabff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
  .kyre-v198410-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
  .kyre-v198410-grade.elite{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
  .kyre-v198410-grade.strong{{background:#103a32;color:#7ce7c2;border:1px solid #2c7463}}
  .kyre-v198410-grade.mixed{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
  .kyre-v198410-grade.cold{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
  .kyre-v198410-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
  .kyre-v198410-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
  .kyre-v198410-grid div{{border:1px solid #523d64;border-radius:10px;padding:8px;background:#120f1c}}
  .kyre-v198410-grid .wide{{grid-column:span 2}}
  .kyre-v198410-grid small{{display:block;color:#9b7bac;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
  .kyre-v198410-grid strong{{display:block;color:#f8f2ff;font-size:.84rem;margin-top:3px}}
  .kyre-v198410-trend{{background:#17101f;border:1px solid #523d64;border-radius:10px;padding:8px 9px;color:#e6d7ef;font-size:.68rem;line-height:1.5;margin-top:8px}}
  .kyre-v198410-trend b{{color:#dfabff}}
  .kyre-v198410-note{{color:#887293;font-size:.57rem;line-height:1.4;margin-top:7px}}
  @media(max-width:760px){{.kyre-v198410-head{{align-items:flex-start;flex-direction:column}}}}
  </style>
  <div class="kyre-v198410-step4">
    <div class="kyre-v198410-head">
      <span>STEP 4 • RECENT SCORING FORM</span>
      <span class="kyre-v198410-grade {summary['grade_class']}">{escape(summary['grade'])}</span>
    </div>
    <div class="kyre-v198410-grid">
      <div><small>SEASON PPG</small><strong>{_fmt(summary['season_ppg'])}</strong></div>
      <div><small>L10 PPG</small><strong>{_fmt(summary['l10_ppg'])}</strong></div>
      <div><small>L5 PPG</small><strong>{_fmt(summary['l5_ppg'])}</strong></div>
      <div><small>TODAY LINE</small><strong>{line_text}</strong></div>
      <div><small>L5 OVER TODAY LINE</small><strong>{l5_rate_text}</strong></div>
      <div><small>L10 OVER TODAY LINE</small><strong>{l10_rate_text}</strong></div>
      <div><small>L5 AVG MARGIN</small><strong>{_fmt(summary['l5_margin'],1)}</strong></div>
      <div><small>L10 AVG MARGIN</small><strong>{_fmt(summary['l10_margin'],1)}</strong></div>
      <div class="wide"><small>MOST RECENT 5 PTS</small><strong>{escape(summary['sequence'])}</strong></div>
    </div>
    <div class="kyre-v198410-trend"><b>Scoring trend</b> • {escape(summary['trend'])}</div>
    <div class="kyre-v198410-note">Verified completed-game appearances before the selected slate date • descriptive audit only • Step 4 does not add or re-apply recent-form weight to the protected Points projection, Monte Carlo or Top-5 ordering.</div>
  </div>
"""


def _context_key_from_row(row) -> tuple[str, str]:
    return _id_text(row.get("PLAYER_ID")), str(row.get("player_key") or "").strip()


def _context_key_from_data(data: dict) -> tuple[str, str]:
    return _id_text(data.get("PLAYER_ID")), str(data.get("player_key") or "").strip()


def _step3_plus_step4(data: dict) -> str:
    step3 = _ORIGINAL_STEP3_BLOCK(data)
    ctx = _STEP4_CONTEXT.get({}) or {}
    pid, pkey = _context_key_from_data(data)
    item = ctx.get((pid, pkey)) or ctx.get((pid, "")) or ctx.get(("", pkey)) or {}
    day = str(item.get("day") or "")
    line = _num(item.get("line"), np.nan)
    if not day:
        return step3
    return step3 + _step4_block(day, line, data)


def _render_top5_with_step4(day: str) -> None:
    try:
        top = prior._same_top5(day)
    except Exception:
        top = pd.DataFrame()

    context = {}
    if isinstance(top, pd.DataFrame) and not top.empty:
        for _, row in top.iterrows():
            pid, pkey = _context_key_from_row(row)
            item = {"day": str(day), "line": _num(row.get("line"), np.nan)}
            context[(pid, pkey)] = item
            if pid:
                context[(pid, "")] = item
            if pkey:
                context[("", pkey)] = item

    token = _STEP4_CONTEXT.set(context)
    try:
        return _ORIGINAL_TOP5_RENDER(day)
    finally:
        _STEP4_CONTEXT.reset(token)


def _install() -> None:
    # V1.9.8.4.9 resolves these globals when it builds the card. Patch only the
    # presentation functions; model/data preparation functions remain untouched.
    prior._step3_block = _step3_plus_step4
    prior._render_top5_h2h_with_embedded_step3 = _render_top5_with_step4


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "📈 Points V1.9.8.4.10 • Step 4 Recent Scoring Form embedded for the same Top 5 • "
        "verified completed-game audit • protected model/ranking unchanged"
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
