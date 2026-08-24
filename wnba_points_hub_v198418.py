"""WNBA Points V1.9.8.4.18 — Step 8 injuries + lineup / rotation effects.

Presentation/context-only wrapper over V1.9.8.4.17. The protected V1.9.8.4.5
Points projection, sportsbook transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and sanity quarantine remain
unchanged.

Step 8 is restricted to the same Top-5 candidates already rendered by Steps
2-7. It combines the current ESPN WNBA roster designation with role/minutes/
usage values already produced by the protected Points runtime. It never invents
an injury, starter confirmation, or teammate-usage redistribution when the
connected data does not explicitly publish one.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198417 as prior
import wnba_players_v25 as players

# V1.9.8.4.17 wraps V1.9.8.4.16. Step 7 is resolved from the V1.9.8.4.16
# module global when the existing Step-6/7 combiner renders a Top-5 card.
v416 = prior.prior
base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.18 • STEP 8 INJURY + LINEUP / ROTATION AUDIT"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Capture the genuine Step-7 function once. Repeated Streamlit reruns then assign
# the same combined wrapper instead of wrapping an already wrapped function.
_BASE_STEP7_BLOCK = getattr(v416, "_kyre_v198418_base_step7", v416._step7_block)
setattr(v416, "_kyre_v198418_base_step7", _BASE_STEP7_BLOCK)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, signed=False):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"


def _pct_value(value):
    x = _num(value, np.nan)
    if pd.isna(x):
        return np.nan
    if abs(x) <= 1.5:
        x *= 100.0
    return x


def _pct(value, digits=1, signed=False):
    x = _pct_value(value)
    if pd.isna(x):
        return "—"
    return (f"{x:+.{digits}f}%" if signed else f"{x:.{digits}f}%")


def _compact_html(html: str) -> str:
    # Keep nested card HTML inside one Markdown raw-HTML block. Blank/indented
    # fragments can otherwise be interpreted by Streamlit as Markdown code.
    return re.sub(r">\s+<", "><", str(html or "").strip())


def _text(data: dict, keys, default="") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip() not in ("", "nan", "None"):
            return str(value).strip()
    return default


def _boolish(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"TRUE", "YES", "Y", "1", "CONFIRMED"}:
        return True
    if text in {"FALSE", "NO", "N", "0", "UNCONFIRMED", "NOT CONFIRMED"}:
        return False
    return None


_HARD_STATUS = (
    "OUT", "DOUBTFUL", "INACTIVE", "SUSPENDED", "NOT WITH TEAM",
    "PERSONAL LEAVE", "EXEMPT",
)
_CAUTION_STATUS = (
    "QUESTIONABLE", "GAME TIME", "GAME-TIME", "GTD", "DAY-TO-DAY",
    "DAY TO DAY", "PROBABLE",
)
_NEUTRAL_STATUS = (
    "ACTIVE", "ROSTERED", "AVAILABLE", "NO DESIGNATION", "RECENT_ACTIVE_PROXY",
)


def _status_level(status: str) -> str:
    s = str(status or "").upper().strip()
    if not s:
        return "unknown"
    if any(token in s for token in _HARD_STATUS):
        return "hard"
    if any(token in s for token in _CAUTION_STATUS):
        return "caution"
    if any(token in s for token in _NEUTRAL_STATUS):
        return "clear"
    return "reported"


def _current_roster(data: dict) -> pd.DataFrame:
    try:
        team_id = int(float(data.get("TEAM_ID")))
    except Exception:
        return pd.DataFrame()
    if not team_id:
        return pd.DataFrame()
    team_name = _text(data, ["TEAM_NAME", "team_name", "TEAM"], "")
    team_abbr = _text(data, ["TEAM_ABBREVIATION", "TEAM_ABBR", "team_abbr"], "")
    try:
        frame = players._espn_roster(team_id, team_name, team_abbr)
    except Exception:
        frame = pd.DataFrame()
    return frame if frame is not None else pd.DataFrame()


def _roster_context(data: dict):
    roster = _current_roster(data)
    try:
        player_id = int(float(data.get("PLAYER_ID")))
    except Exception:
        player_id = 0

    player_status = "NOT EXPOSED"
    roster_source = "ESPN WNBA current roster unavailable"
    flagged = []

    if roster is not None and not roster.empty:
        if "ROSTER_SOURCE" in roster.columns:
            sources = [str(x) for x in roster["ROSTER_SOURCE"].dropna().tolist() if str(x).strip()]
            if sources:
                roster_source = sources[0]
        else:
            roster_source = "ESPN WNBA current roster"

        ids = pd.to_numeric(roster.get("PLAYER_ID"), errors="coerce") if "PLAYER_ID" in roster.columns else pd.Series(dtype=float)
        if player_id and not ids.empty:
            part = roster.loc[ids.eq(player_id)]
            if not part.empty:
                player_status = str(part.iloc[0].get("ROSTER_STATUS") or "ROSTERED").strip().upper()

        for _, row in roster.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                pid = 0
            if player_id and pid == player_id:
                continue
            status = str(row.get("ROSTER_STATUS") or "").strip().upper()
            level = _status_level(status)
            if level in ("hard", "caution"):
                name = str(row.get("PLAYER_NAME") or "Teammate").strip()
                flagged.append((name, status, level))

    return roster, player_status, roster_source, flagged


def _lineup_state(data: dict) -> tuple[str, str]:
    # Only call a lineup confirmed when the protected runtime explicitly exposes
    # a confirmation field. High minutes or a role label are never used to infer it.
    for key in ("LINEUP_CONFIRMED", "STARTER_CONFIRMED", "CONFIRMED_STARTER"):
        if key in data:
            value = _boolish(data.get(key))
            if value is True:
                return "CONFIRMED", f"protected runtime • {key}"
            if value is False:
                return "NOT CONFIRMED", f"protected runtime • {key}"

    for key in ("LINEUP_STATUS", "STARTER_STATUS", "STARTING_STATUS"):
        raw = _text(data, [key], "")
        if raw:
            return raw.upper(), f"protected runtime • {key}"

    starter = None
    for key in ("IS_STARTER", "STARTER"):
        if key in data:
            starter = _boolish(data.get(key))
            if starter is not None:
                return ("STARTER ROLE" if starter else "BENCH ROLE"), f"protected runtime • {key} • role only"

    return "NOT EXPOSED", "no explicit lineup-confirmation field in protected runtime"


def _recent_minutes(data: dict):
    l3 = _num(data.get("RECENT_TEAM_L3_MIN"), np.nan)
    l5 = _num(data.get("RECENT_TEAM_L5_MIN"), np.nan)
    if pd.notna(l3) and pd.notna(l5):
        return 0.65 * l3 + 0.35 * l5
    if pd.notna(l3):
        return l3
    if pd.notna(l5):
        return l5
    l5_player = _num(data.get("L5_MIN"), np.nan)
    l10_player = _num(data.get("L10_MIN"), np.nan)
    return l5_player if pd.notna(l5_player) else l10_player


def _rotation_read(data: dict, player_status: str):
    proj = _num(data.get("PROJ_MIN"), np.nan)
    recent = _recent_minutes(data)
    min_delta = proj - recent if pd.notna(proj) and pd.notna(recent) else np.nan

    season_usg = _pct_value(data.get("USG_PCT"))
    l10_usg = _pct_value(data.get("L10_USG_PCT"))
    l5_usg = _pct_value(data.get("L5_USG_PCT"))
    recent_usg = l5_usg if pd.notna(l5_usg) else l10_usg
    usage_delta = recent_usg - season_usg if pd.notna(recent_usg) and pd.notna(season_usg) else np.nan

    level = _status_level(player_status)
    if level == "hard":
        return "AVAILABILITY RISK", "hard", "HURTS SCORER", min_delta, usage_delta
    if level == "caution":
        return "MONITOR STATUS", "caution", "HURTS / MONITOR", min_delta, usage_delta

    if pd.notna(min_delta) and min_delta >= 2.0 and pd.notna(usage_delta) and usage_delta >= 1.5:
        return "BOOSTED OPPORTUNITY", "boost", "SUPPORTS SCORER", min_delta, usage_delta
    if (pd.notna(min_delta) and min_delta <= -2.5) or (pd.notna(usage_delta) and usage_delta <= -2.5):
        return "ROTATION RISK", "risk", "HURTS SCORER", min_delta, usage_delta
    if pd.isna(min_delta) and pd.isna(usage_delta) and level == "unknown":
        return "DATA LIMITED", "limited", "NEUTRAL", min_delta, usage_delta
    return "STABLE OPPORTUNITY", "stable", "NEUTRAL", min_delta, usage_delta


def _step8_block(day: str, data: dict) -> str:
    roster, player_status, roster_source, flagged = _roster_context(data)
    grade, grade_class, verdict, min_delta, usage_delta = _rotation_read(data, player_status)

    protected_role = _text(data, ["ROLE_LABEL", "ROLE", "PLAYER_ROLE"], "NOT EXPOSED")
    lineup_state, lineup_source = _lineup_state(data)

    proj_min = _num(data.get("PROJ_MIN"), np.nan)
    recent_min = _recent_minutes(data)
    season_min = _num(data.get("MIN"), np.nan)
    season_usg = _pct_value(data.get("USG_PCT"))
    l10_usg = _pct_value(data.get("L10_USG_PCT"))
    l5_usg = _pct_value(data.get("L5_USG_PCT"))

    if flagged:
        teammate_text = " • ".join(
            f"{escape(name)} — {escape(status)}" for name, status, _ in flagged[:3]
        )
        if len(flagged) > 3:
            teammate_text += f" • +{len(flagged)-3} more"
        teammate_state = f"{len(flagged)} explicit roster restriction(s)"
    elif roster is not None and not roster.empty:
        teammate_text = "No explicit OUT / DOUBTFUL / QUESTIONABLE-type teammate restriction published in this roster response. This is not a medical-clearance claim."
        teammate_state = "NO EXPLICIT RESTRICTION IN ROSTER FEED"
    else:
        teammate_text = "Current roster response unavailable; teammate injury/availability is not inferred."
        teammate_state = "DATA LIMITED"

    status_level = _status_level(player_status)
    status_note = {
        "hard": "Explicit restriction detected — do not treat the player as normally available.",
        "caution": "Explicit monitor designation detected — availability remains uncertain.",
        "clear": "Roster feed lists the player as active/rostered; this is not a medical-clearance guarantee.",
        "reported": "Roster feed supplied a designation; shown verbatim without extra interpretation.",
        "unknown": "No explicit current-roster designation was available.",
    }.get(status_level, "Shown verbatim from the connected roster source.")

    html = f"""
<style>
.kyre-v198418-step8{{background:#111c20;border:1px solid #477b72;border-radius:15px;padding:12px;margin-top:10px}}
.kyre-v198418-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#87e4d1;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
.kyre-v198418-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
.kyre-v198418-grade.boost{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198418-grade.stable{{background:#12382e;color:#91e7c8;border:1px solid #376e60}}
.kyre-v198418-grade.caution{{background:#4a370c;color:#ffe17a;border:1px solid #8d7118}}
.kyre-v198418-grade.risk,.kyre-v198418-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198418-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198418-status{{background:#0b1519;border:1px solid #3f6e67;border-radius:10px;padding:9px;color:#dbece8;font-size:.68rem;line-height:1.55;margin-bottom:8px}}
.kyre-v198418-status b{{color:#87e4d1}}
.kyre-v198418-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198418-grid div{{border:1px solid #3f6e67;border-radius:10px;padding:8px;background:#0a1317}}
.kyre-v198418-grid small{{display:block;color:#83a9a1;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198418-grid strong{{display:block;color:#f2fbf8;font-size:.82rem;margin-top:3px;word-break:break-word}}
.kyre-v198418-team{{background:#0a1317;border:1px solid #3f6e67;border-radius:10px;padding:9px;color:#dbece8;font-size:.66rem;line-height:1.5;margin-top:8px}}
.kyre-v198418-team b{{color:#87e4d1}}
.kyre-v198418-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#14242a;border:1px solid #477b72;color:#f1fbf8;font-size:.68rem;font-weight:850}}
.kyre-v198418-note{{color:#78958f;font-size:.57rem;line-height:1.42;margin-top:7px}}
@media(max-width:760px){{.kyre-v198418-head{{align-items:flex-start;flex-direction:column}}}}
</style>
<div class="kyre-v198418-step8">
<div class="kyre-v198418-head"><span>STEP 8 • INJURIES + LINEUP / ROTATION EFFECTS</span><span class="kyre-v198418-grade {grade_class}">{escape(grade)}</span></div>
<div class="kyre-v198418-status"><b>Player roster designation</b> • {escape(player_status)}<br><b>Protected role/status</b> • {escape(protected_role)}<br><b>Lineup / starter confirmation</b> • {escape(lineup_state)}<br><b>Status interpretation</b> • {escape(status_note)}</div>
<div class="kyre-v198418-grid">
<div><small>PROJECTED MIN</small><strong>{_fmt(proj_min)}</strong></div><div><small>RECENT ROTATION MIN</small><strong>{_fmt(recent_min)}</strong></div>
<div><small>MIN DELTA VS RECENT</small><strong>{_fmt(min_delta, signed=True)}</strong></div><div><small>SEASON MIN</small><strong>{_fmt(season_min)}</strong></div>
<div><small>SEASON USAGE</small><strong>{_pct(season_usg)}</strong></div><div><small>L10 USAGE</small><strong>{_pct(l10_usg)}</strong></div>
<div><small>L5 USAGE</small><strong>{_pct(l5_usg)}</strong></div><div><small>RECENT USAGE Δ</small><strong>{_pct(usage_delta, signed=True)}</strong></div>
<div><small>TEAMMATE STATUS</small><strong>{escape(teammate_state)}</strong></div><div><small>LINEUP SOURCE</small><strong>{escape(lineup_source)}</strong></div>
</div>
<div class="kyre-v198418-team"><b>Explicit teammate availability flags</b> • {teammate_text}<br><b>Roster source</b> • {escape(roster_source)}<br><b>Usage redistribution</b> • NOT ASSUMED — Step 8 does not credit extra usage/minutes to this player unless the protected Points runtime already did so.</div>
<div class="kyre-v198418-verdict">Points availability / rotation context • {escape(verdict)}</div>
<div class="kyre-v198418-note">Audit/context only • Step 8 displays explicit current-roster designations plus protected role, minutes and usage signals. It does not invent injury severity, a confirmed starter, teammate usage redistribution or a new scoring adjustment. Projection, Monte Carlo probability and Top-5 ordering remain unchanged.</div>
</div>
"""
    return _compact_html(html)


def _step7_plus_step8(day: str, data: dict) -> str:
    return _BASE_STEP7_BLOCK(day, data) + _step8_block(day, data)


def _install() -> None:
    # Keep V1.9.8.4.17's Step-7 source-window-label repair active first.
    prior._install()
    # V1.9.8.4.16's renderer resolves this module global at render time; assign
    # the fixed combined function on every rerun instead of wrapping recursively.
    v416._step7_block = _step7_plus_step8


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🩺 Points V1.9.8.4.18 • Step 8 injury + lineup/rotation audit ACTIVE • "
        "explicit roster designations only • no invented redistribution • protected model/ranking unchanged"
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
