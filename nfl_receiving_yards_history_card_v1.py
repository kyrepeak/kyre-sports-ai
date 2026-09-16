"""Pure display helper for the Receiving Yards player-vs-defense history card.

The source history payload is already certified by nfl_receiving_yards_history_v1.
This helper only validates exact IDs, preserves the source's newest-first order,
and formats the first verified row for display. Names are never matching keys.
"""
from __future__ import annotations

import math
from typing import Any


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _int_text(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return str(int(number))


def latest_exact_game(
    history: dict[str, Any],
    *,
    athlete_id: str,
    team_id: str,
    opponent_id: str,
) -> dict[str, Any] | None:
    """Return the first newest-first row that passes exact ESPN identity."""
    if not isinstance(history, dict) or history.get("ready") is not True:
        return None
    athlete_id = _text(athlete_id)
    team_id = _text(team_id)
    opponent_id = _text(opponent_id)
    if (
        not athlete_id.isdigit()
        or not team_id.isdigit()
        or not opponent_id.isdigit()
        or team_id == opponent_id
    ):
        return None

    games = history.get("games")
    if not isinstance(games, list):
        return None
    for game in games:
        if not isinstance(game, dict):
            continue
        event_id = _text(game.get("official_event_id"))
        if (
            not event_id.isdigit()
            or _text(game.get("official_athlete_id")) != athlete_id
            or _text(game.get("official_team_id")) != team_id
            or _text(game.get("opponent_official_team_id")) != opponent_id
        ):
            continue
        return game
    return None


def format_last_vs_summary(game: dict[str, Any], opponent_abbr: str) -> str:
    """Format one already-verified history row without inventing target data."""
    opponent = _text(opponent_abbr).upper() or "OPP"
    receptions = _int_text(game.get("receptions"))
    yards = _int_text(game.get("receiving_yards"))
    touchdowns = _int_text(game.get("receiving_touchdowns"))
    targets = (
        _int_text(game.get("targets"))
        if game.get("targets_data_available") is True
        else "—"
    )
    return (
        f"Last vs {opponent} • {receptions} REC • {yards} YDS • "
        f"{touchdowns} TD • {targets} TGT"
    )


__all__ = ["format_last_vs_summary", "latest_exact_game"]
