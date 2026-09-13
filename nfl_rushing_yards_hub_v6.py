from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st
import nfl_rushing_yards_hub_v5 as prior

MODEL_VERSION = "NFL RUSHING YARDS V6 • PAGE BUILD STEP 3 • WORKLOAD + EFFICIENCY PROFILE"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v5"
PAGE_BUILD_STEP = 3
PAGE_BUILD_TOTAL = 6

_ORIGINAL_COMPACT_PLAYER_CARD_V5 = prior._compact_player_card_v5

_PROFILE_CSS = r'''
<style>
.krush6-profile{border:1px solid #203729;border-radius:11px;background:#08130e;padding:7px 8px 8px;margin:0 2px 2px;min-width:0}
.krush6-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
.krush6-title{color:#dfeae2;font-size:.54rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.krush6-meta{color:#6f8477;font-size:.42rem;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush6-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
.krush6-stat{min-width:0;border-top:1px solid #1a2e22;padding:6px 4px 1px}
.krush6-stat b{display:block;color:#eef6f0;font-size:.65rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush6-stat span{display:block;color:#607468;font-size:.37rem;font-weight:900;text-transform:uppercase;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush6-grade{display:inline-flex;align-items:center;border:1px solid #315640;border-radius:999px;background:#0d2016;color:#91d3a6;padding:2px 5px;font-size:.38rem;font-weight:950;text-transform:uppercase}
.krush6-grade.watch{border-color:#625739;background:#211c11;color:#d9bd69}
@media(max-width:760px){.krush6-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.krush6-head{align-items:flex-start;flex-direction:column;gap:3px}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _number(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _fmt(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def _exact_player(team: dict[str, Any], athlete_id: str) -> dict[str, Any]:
    if not athlete_id.isdigit():
        return {}
    team_id = _safe(team.get("official_team_id"), "")
    if not team_id.isdigit():
        return {}
    for player in team.get("players") or []:
        if not isinstance(player, dict):
            continue
        if _safe(player.get("official_athlete_id"), "") == athlete_id and _safe(player.get("official_team_id"), "") == team_id:
            return player
    return {}


def _workload_efficiency_html(projection_row: dict[str, Any], team: dict[str, Any]) -> str:
    athlete_id = _safe(projection_row.get("official_athlete_id"), "")
    player = _exact_player(team, athlete_id)
    if not player:
        return ""
    season = _safe(player.get("baseline_season"), _safe(projection_row.get("baseline_season"), "—"))
    sample_games = _fmt(player.get("sample_games"), 0)
    grade = _safe(projection_row.get("coverage_grade"), "CHECK").upper()
    grade_class = "" if grade == "GREEN" else " watch"
    stats = (
        ("Carries", _fmt(player.get("carries"), 0)),
        ("Rush Yards", _fmt(player.get("rushing_yards"), 0)),
        ("Carries / Game", _fmt(player.get("carries_per_game"), 1)),
        ("Rush Yards / Game", _fmt(player.get("rushing_yards_per_game"), 1)),
        ("Yards / Carry", _fmt(player.get("yards_per_carry"), 2)),
        ("Rush TDs", _fmt(player.get("rushing_touchdowns"), 0)),
        ("Sample Games", sample_games),
    )
    return (
        '<section class="krush6-profile" aria-label="Rusher workload and efficiency profile">'
        '<div class="krush6-head"><div>'
        '<div class="krush6-title">Workload + Efficiency Profile</div>'
        f'<div class="krush6-meta">Verified player baseline • season {escape(season)} • exact ESPN athlete {escape(athlete_id)}</div>'
        '</div>'
        f'<span class="krush6-grade{grade_class}">{escape(grade)} sample</span></div>'
        '<div class="krush6-grid">'
        + "".join(f'<div class="krush6-stat"><b>{escape(value)}</b><span>{escape(label)}</span></div>' for label, value in stats)
        + '</div></section>'
    )


def _compact_player_card_v6(projection_row: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any], market_row: dict[str, Any]) -> str:
    stack = _ORIGINAL_COMPACT_PLAYER_CARD_V5(projection_row, team, opponent, market_row)
    profile = _workload_efficiency_html(projection_row, team)
    return f'<div class="krush6-player">{stack}{profile}</div>' if profile else stack


def render_nfl_rushing_yards_hub() -> None:
    st.markdown(_PROFILE_CSS, unsafe_allow_html=True)
    original_card = prior._compact_player_card_v5
    prior._compact_player_card_v5 = _compact_player_card_v6
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._compact_player_card_v5 = original_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V6 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()
