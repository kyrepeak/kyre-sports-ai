"""Pure exact-ID helpers for Receiving Yards Matchup Tiers 2.0."""
from __future__ import annotations

import math
import re
from typing import Any, Callable


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def find_exact_player(team: dict[str, Any], athlete_id: Any) -> dict[str, Any] | None:
    """Return only an exact ESPN athlete-ID match; names are never keys."""
    target = _safe(athlete_id)
    if not target.isdigit() or not isinstance(team, dict):
        return None
    for player in team.get("players") or []:
        if not isinstance(player, dict):
            continue
        if _safe(player.get("official_athlete_id")) == target:
            return player
    return None


def projection_yards_for_athlete(
    context: dict[str, Any],
    team: dict[str, Any],
    athlete_id: Any,
    builder: Callable[..., dict[str, Any]],
) -> float | None:
    """Expose the frozen projection result without adding any market inputs."""
    player = find_exact_player(team, athlete_id)
    if player is None:
        return None
    event_id = _safe(
        player.get("official_event_id"),
        _safe((context or {}).get("official_event_id")),
    )
    try:
        result = builder(official_event_id=event_id, team=team, player=player)
    except Exception:
        return None
    if not isinstance(result, dict) or result.get("ready") is not True:
        return None
    try:
        value = float(result.get("projection_yards"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def headshot_url(athlete_id: Any) -> str:
    athlete = _safe(athlete_id)
    if not athlete.isdigit():
        return ""
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete}.png"


def team_logo_url(team_abbreviation: Any) -> str:
    token = re.sub(r"[^a-z0-9]", "", _safe(team_abbreviation).lower())
    if not token:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{token}.png"


__all__ = [
    "find_exact_player",
    "headshot_url",
    "projection_yards_for_athlete",
    "team_logo_url",
]
