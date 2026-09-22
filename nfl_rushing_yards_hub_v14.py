"""NFL Rushing Yards V14 — tier badges and favorable-first detailed player stacks.

V14 is additive over certified V13. It moves the already-certified opponent
run-defense matchup classification onto the detailed player stack users actually
read and sorts those full stacks FAVORABLE -> MEDIUM -> TOUGH.

No projection math, market semantics, probability, EV, recommendation, staking,
or wager behavior changes. The classification still uses only verified exact-ID
opponent run-front context from V13. Sportsbook projection influence stays 0.0%.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_rushing_yards_hub_v4 as compact_page
import nfl_rushing_yards_hub_v9 as final_page
import nfl_rushing_yards_hub_v13 as prior

MODEL_VERSION = "NFL RUSHING YARDS V14 • DETAILED STACK TIERS • FAVORABLE FIRST"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v13"
DISPLAY_ONLY = True
MATCHUP_CLASSIFICATION_ONLY = True
BETTING_GRADE_ENABLED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_COMPACT_BOARD_V4 = compact_page._compact_board_html
_ORIGINAL_FINAL_CARD_V9 = final_page._compact_player_card_v9

_TIER_STACK_CSS = r'''
<style>
.krush14-player{min-width:0;display:flex;flex-direction:column;gap:6px}
.krush14-ribbon{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid #8b742a;border-radius:10px;background:linear-gradient(180deg,#271f0a 0%,#171306 100%);padding:6px 8px;margin:0 1px}
.krush14-ribbon.favorable{border-color:#37814b;background:linear-gradient(180deg,#102819 0%,#0b1d12 100%)}
.krush14-ribbon.tough{border-color:#8b4141;background:linear-gradient(180deg,#2a1111 0%,#1d0c0c 100%)}
.krush14-tier{font-size:.48rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;white-space:nowrap}.krush14-tier.favorable{color:#82e09a}.krush14-tier.medium{color:#e8cf65}.krush14-tier.tough{color:#ef8a8a}
.krush14-copy{color:#8b927f;font-size:.42rem;font-weight:800;line-height:1.35;text-align:right}.krush14-copy strong{color:#d8dece}
@media(max-width:760px){.krush14-ribbon{align-items:flex-start;flex-direction:column;gap:3px}.krush14-copy{text-align:left}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _grade_for_team_opponent(team: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any]:
    grade = prior._matchup_tier(team, opponent)
    tier = str(grade.get("tier") or "MEDIUM").upper()
    if tier not in prior.TIER_ORDER:
        tier = "MEDIUM"
    return {**grade, "tier": tier}


def _sorted_projection_result(result: Any, context: dict[str, Any]) -> Any:
    if not isinstance(result, dict) or result.get("ready") is not True:
        return result
    projections = [row for row in result.get("projections") or [] if isinstance(row, dict)]
    if not projections:
        return result

    teams = compact_page._team_map(context)
    original_order = {id(row): index for index, row in enumerate(projections)}

    def key(row: dict[str, Any]) -> tuple[int, int]:
        team_id = _safe(row.get("official_team_id"))
        opponent_id = _safe(row.get("opponent_official_team_id"))
        team = teams.get(team_id, {})
        opponent = teams.get(opponent_id, {})
        grade = _grade_for_team_opponent(team, opponent)
        return (
            prior.TIER_ORDER.get(str(grade.get("tier") or "MEDIUM"), 1),
            original_order[id(row)],
        )

    sorted_rows = sorted(projections, key=key)
    return {**result, "projections": sorted_rows}


def _compact_board_html_v14(context: dict[str, Any], event_id: str) -> str:
    """Reuse frozen V4 board rendering with only the projection-row order changed."""
    original_builder = compact_page.step3.projection.build_event_projections

    def sorted_builder(inner_context: dict[str, Any]) -> Any:
        result = original_builder(inner_context)
        return _sorted_projection_result(result, inner_context)

    compact_page.step3.projection.build_event_projections = sorted_builder
    try:
        return _ORIGINAL_COMPACT_BOARD_V4(context, event_id)
    finally:
        compact_page.step3.projection.build_event_projections = original_builder


def _detailed_player_card_v14(
    projection_row: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
    market_row: dict[str, Any],
) -> str:
    stack = _ORIGINAL_FINAL_CARD_V9(projection_row, team, opponent, market_row)
    grade = _grade_for_team_opponent(team, opponent)
    tier = str(grade.get("tier") or "MEDIUM").upper()
    tier_class = tier.lower()
    score = int(grade.get("score") or 0)
    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()
    if grade.get("available") is True:
        detail = (
            f'vs {opponent_abbr} • matchup score {score:+d} • '
            f'{int(grade.get("favorable_signals") or 0)} favorable / '
            f'{int(grade.get("tough_signals") or 0)} tough signals'
        )
    else:
        detail = f'vs {opponent_abbr} • {_safe(grade.get("reason"), "verified context unavailable")}'

    ribbon = (
        f'<div class="krush14-ribbon {escape(tier_class)}" '
        f'data-detailed-matchup-tier="{escape(tier)}" data-detailed-matchup-score="{score:+d}">'
        f'<span class="krush14-tier {escape(tier_class)}">{escape(tier)}</span>'
        f'<span class="krush14-copy">{escape(detail)} • <strong>matchup classification only</strong></span>'
        '</div>'
    )
    athlete_id = _safe(projection_row.get("official_athlete_id"))
    return (
        f'<section class="krush14-player" data-athlete-id="{escape(athlete_id)}" '
        f'data-matchup-tier="{escape(tier)}">{ribbon}{stack}</section>'
    )


def render_nfl_rushing_yards_hub() -> None:
    st.markdown(_TIER_STACK_CSS, unsafe_allow_html=True)
    original_board = compact_page._compact_board_html
    original_final_card = final_page._compact_player_card_v9
    compact_page._compact_board_html = _compact_board_html_v14
    final_page._compact_player_card_v9 = _detailed_player_card_v14
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        compact_page._compact_board_html = original_board
        final_page._compact_player_card_v9 = original_final_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V14 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "BETTING_GRADE_ENABLED",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MATCHUP_CLASSIFICATION_ONLY",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_compact_board_html_v14",
    "_detailed_player_card_v14",
    "_grade_for_team_opponent",
    "_sorted_projection_result",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
