from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st
import nfl_rushing_yards_hub_v6 as prior

MODEL_VERSION = "NFL RUSHING YARDS V7 • PAGE BUILD STEP 4 • OPPONENT RUN DEFENSE MATCHUP"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v6"
PAGE_BUILD_STEP = 4
PAGE_BUILD_TOTAL = 6

_ORIGINAL_COMPACT_PLAYER_CARD_V6 = prior._compact_player_card_v6

_MATCHUP_CSS = r'''
<style>
.krush7-matchup{border:1px solid #26384a;border-radius:11px;background:#09121a;padding:7px 8px 8px;margin:0 2px 2px;min-width:0}
.krush7-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
.krush7-title{color:#e2ebf5;font-size:.54rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.krush7-meta{color:#728497;font-size:.42rem;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush7-opponent{display:inline-flex;align-items:center;border:1px solid #3a5067;border-radius:999px;background:#101d29;color:#b7cce2;padding:2px 6px;font-size:.39rem;font-weight:950;text-transform:uppercase;white-space:nowrap}
.krush7-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
.krush7-stat{min-width:0;border-top:1px solid #213243;padding:6px 4px 1px}
.krush7-stat b{display:block;color:#f0f5fa;font-size:.65rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush7-stat span{display:block;color:#66798c;font-size:.37rem;font-weight:900;text-transform:uppercase;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:760px){.krush7-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.krush7-head{align-items:flex-start;flex-direction:column;gap:3px}}
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


def _verified_run_front(team: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any]:
    team_id = _safe(team.get("official_team_id"), "")
    opponent_id = _safe(team.get("opponent_official_team_id"), "")
    rendered_opponent_id = _safe(opponent.get("official_team_id"), "")
    if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
        return {}
    if rendered_opponent_id != opponent_id:
        return {}
    run_front = team.get("opponent_run_front") or {}
    if not isinstance(run_front, dict) or run_front.get("data_available") is not True:
        return {}
    if _safe(run_front.get("official_team_id"), "") != opponent_id:
        return {}
    return run_front


def _opponent_run_defense_html(team: dict[str, Any], opponent: dict[str, Any]) -> str:
    run_front = _verified_run_front(team, opponent)
    if not run_front:
        return ""

    opponent_id = _safe(opponent.get("official_team_id"), "")
    opponent_name = _safe(opponent.get("team_name"), _safe(opponent.get("team_abbreviation"), "NFL Opponent"))
    opponent_abbr = _safe(opponent.get("team_abbreviation"), opponent_name)
    stats = (
        ("Rush Att Allowed / Game", _fmt(run_front.get("rush_attempts_allowed_per_game"), 1)),
        ("Rush Yards Allowed / Game", _fmt(run_front.get("rush_yards_allowed_per_game"), 1)),
        ("Yards / Carry Allowed", _fmt(run_front.get("yards_per_carry_allowed"), 2)),
        ("Rush TDs Allowed / Game", _fmt(run_front.get("rushing_touchdowns_allowed_per_game"), 2)),
    )
    return (
        '<section class="krush7-matchup" aria-label="Opponent run defense matchup">'
        '<div class="krush7-head"><div>'
        '<div class="krush7-title">Opponent Run Defense Matchup</div>'
        f'<div class="krush7-meta">Verified run-front context • exact ESPN team {escape(opponent_id)} • {escape(opponent_name)}</div>'
        '</div>'
        f'<span class="krush7-opponent">vs {escape(opponent_abbr)}</span></div>'
        '<div class="krush7-grid">'
        + "".join(f'<div class="krush7-stat"><b>{escape(value)}</b><span>{escape(label)}</span></div>' for label, value in stats)
        + '</div></section>'
    )


def _compact_player_card_v7(projection_row: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any], market_row: dict[str, Any]) -> str:
    stack = _ORIGINAL_COMPACT_PLAYER_CARD_V6(projection_row, team, opponent, market_row)
    matchup = _opponent_run_defense_html(team, opponent)
    return f'<div class="krush7-player">{stack}{matchup}</div>' if matchup else stack


def render_nfl_rushing_yards_hub() -> None:
    st.markdown(_MATCHUP_CSS, unsafe_allow_html=True)
    original_card = prior._compact_player_card_v6
    prior._compact_player_card_v6 = _compact_player_card_v7
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._compact_player_card_v6 = original_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V7 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()
