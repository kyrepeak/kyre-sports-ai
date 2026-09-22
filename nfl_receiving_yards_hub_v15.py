"""NFL Receiving Yards V15 — compact player-vs-defense history card.

Additive display-only wrapper over frozen V14. It reuses the certified V5
exact-ID history loader and promotes the newest verified player-vs-opponent
receiving game into a compact card above the existing deep evidence.
No history, projection, market, probability, EV, staking, or wager math changes.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v5 as history_page
import nfl_receiving_yards_hub_v14 as prior
from nfl_receiving_yards_history_card_v1 import format_last_vs_summary, latest_exact_game

MODEL_VERSION = "NFL RECEIVING YARDS V15 • PLAYER VS DEFENSE HISTORY"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v14"
FROZEN_HISTORY_PAGE = "nfl_receiving_yards_hub_v5"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V14 = prior._player_card_v14
_HISTORY_INSERT_MARKER = '<div class="krecv14-deep">DEEP EVIDENCE</div>'

_STEP15_CSS = r'''
<style>
.krecv15-history{border:1px solid #4a5d72;border-radius:11px;background:linear-gradient(145deg,#111923,#0e141c);padding:8px 9px;margin:0 0 7px}.krecv15-title{color:#8bc5ef;font-size:.36rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.krecv15-line{color:#f5f7fa;font-size:.58rem;font-weight:950;margin-top:3px}.krecv15-meta{color:#798697;font-size:.36rem;font-weight:800;margin-top:3px;line-height:1.35}.krecv15-empty{border-style:dashed;color:#8f9aa8}
@media(max-width:760px){.krecv15-line{font-size:.53rem}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _history_card_html(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    athlete_id = _safe(player.get("official_athlete_id"))
    player_team_id = _safe(player.get("official_team_id"))
    team_id = _safe(team.get("official_team_id"))
    opponent_id = _safe(team.get("opponent_official_team_id"))
    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()

    if (
        not athlete_id.isdigit()
        or not player_team_id.isdigit()
        or not team_id.isdigit()
        or not opponent_id.isdigit()
        or player_team_id != team_id
        or team_id == opponent_id
    ):
        return (
            '<section class="krecv15-history krecv15-empty" aria-label="Player vs defense history">'
            '<div class="krecv15-title">PLAYER VS DEFENSE HISTORY</div>'
            '<div class="krecv15-meta">Exact ESPN identity unavailable. No history row was guessed.</div>'
            '</section>'
        )

    anchor_raw = player.get("baseline_season") or team.get("player_baseline_season")
    try:
        anchor_season = int(anchor_raw)
    except (TypeError, ValueError):
        anchor_season = 0

    history = history_page._load_history(
        athlete_id,
        team_id,
        opponent_id,
        anchor_season,
    )
    game = latest_exact_game(
        history if isinstance(history, dict) else {},
        athlete_id=athlete_id,
        team_id=team_id,
        opponent_id=opponent_id,
    )
    if game is None:
        reason = _safe((history or {}).get("reason") if isinstance(history, dict) else "", "No verified prior receiving game book")
        return (
            '<section class="krecv15-history krecv15-empty" aria-label="Player vs defense history">'
            '<div class="krecv15-title">PLAYER VS DEFENSE HISTORY</div>'
            f'<div class="krecv15-meta">No verified Last vs {escape(opponent_abbr)} row: {escape(reason)}. No fallback was invented.</div>'
            '</section>'
        )

    summary = format_last_vs_summary(game, opponent_abbr)
    event_id = _safe(game.get("official_event_id"), "—")
    date = _safe(game.get("date"), "verified completed game")
    return (
        '<section class="krecv15-history" aria-label="Player vs defense history">'
        '<div class="krecv15-title">PLAYER VS DEFENSE HISTORY</div>'
        f'<div class="krecv15-line">{escape(summary)}</div>'
        f'<div class="krecv15-meta">{escape(date)} • ESPN event {escape(event_id)} • exact-ID completed game book</div>'
        '</section>'
    )


def _player_card_v15(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    stack = _ORIGINAL_PLAYER_CARD_V14(player, team, opponent)
    history_card = _history_card_html(player, team, opponent)
    if _HISTORY_INSERT_MARKER in stack:
        return stack.replace(
            _HISTORY_INSERT_MARKER,
            history_card + _HISTORY_INSERT_MARKER,
            1,
        )
    return f"{stack}{history_card}"


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP15_CSS, unsafe_allow_html=True)
    original_card = prior._player_card_v14
    prior._player_card_v14 = _player_card_v15
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._player_card_v14 = original_card


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V15 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_HISTORY_PAGE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_history_card_html",
    "_player_card_v15",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
