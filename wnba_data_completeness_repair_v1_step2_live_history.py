"""Pure WNBA Step-2 history summarization for the live hydration repair.

This module performs no network I/O and no projection/model work. It converts
the repository-established ESPN WNBA athlete-gamelog contract into the existing
season/L10/L5 MIN/PTS/REB/AST/PRA columns consumed by the frozen role engine.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _usable_games(history: Mapping[str, Any] | None, cutoff_day: str) -> list[dict[str, Any]]:
    games = []
    raw_games = (history or {}).get("games") if isinstance(history, Mapping) else None
    for raw in raw_games or []:
        if not isinstance(raw, Mapping):
            continue
        day = str(raw.get("game_date") or "")[:10]
        if not day or day >= str(cutoff_day):
            continue
        values = {
            "game_date": day,
            "minutes": _number(raw.get("minutes")),
            "points": _number(raw.get("points")),
            "rebounds": _number(raw.get("rebounds")),
            "assists": _number(raw.get("assists")),
        }
        if all(values[key] is None for key in ("minutes", "points", "rebounds", "assists")):
            continue
        games.append(values)
    games.sort(key=lambda row: row["game_date"], reverse=True)
    return games


def _average(games: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in games if row.get(key) is not None]
    return sum(values) / len(values) if values else 0.0


def _window(games: list[dict[str, Any]], limit: int) -> dict[str, float | int]:
    use = games[: int(limit)] if int(limit) > 0 else games
    minutes = _average(use, "minutes")
    points = _average(use, "points")
    rebounds = _average(use, "rebounds")
    assists = _average(use, "assists")
    return {
        "GP": len(use),
        "MIN": minutes,
        "PTS": points,
        "REB": rebounds,
        "AST": assists,
        "PRA": points + rebounds + assists,
    }


def summarize_player_history(history: Mapping[str, Any] | None, cutoff_day: str) -> dict[str, Any]:
    """Build the role-engine season/L10/L5 contract before ``cutoff_day``."""
    games = _usable_games(history, str(cutoff_day))
    season = _window(games, 0)
    l10 = _window(games, 10)
    l5 = _window(games, 5)
    return {
        "GP": season["GP"],
        "MIN": season["MIN"],
        "PTS": season["PTS"],
        "REB": season["REB"],
        "AST": season["AST"],
        "PRA": season["PRA"],
        "L10_GP": l10["GP"],
        "L10_MIN": l10["MIN"],
        "L10_PTS": l10["PTS"],
        "L10_REB": l10["REB"],
        "L10_AST": l10["AST"],
        "L10_PRA": l10["PRA"],
        "L5_GP": l5["GP"],
        "L5_MIN": l5["MIN"],
        "L5_PTS": l5["PTS"],
        "L5_REB": l5["REB"],
        "L5_AST": l5["AST"],
        "L5_PRA": l5["PRA"],
        "LAST_GAME_DATE": games[0]["game_date"] if games else "—",
    }


__all__ = ["summarize_player_history"]
