"""NFL Spread smart next-slate resolver.

Fast calendar discovery may look across the full upcoming NFL horizon, while
network fallback stays deliberately bounded. The current selected day is checked
once through the frozen authoritative slate loader; nflverse is date discovery
only and never fabricates a renderable game.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable

from nfl_passing_yards_next_slate_v1 import nflverse_schedule_dates

CALENDAR_LOOKAHEAD_DAYS = 370
NETWORK_FALLBACK_DAYS = 21


def _coerce_date(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _verified_games_present(games: Any) -> bool:
    return bool(games is not None and hasattr(games, "empty") and not games.empty)


def _normalized_future_dates(values: Iterable[Any], selected: date, end: date) -> list[date]:
    resolved: set[date] = set()
    for value in values or ():
        day = _coerce_date(value, selected)
        if selected < day <= end:
            resolved.add(day)
    return sorted(resolved)


def resolve_spread_slate_date(
    selected_day: date,
    primary_loader: Callable[[str], tuple[Any, dict[str, Any]]],
    *,
    calendar_lookahead_days: int = CALENDAR_LOOKAHEAD_DAYS,
    network_fallback_days: int = NETWORK_FALLBACK_DAYS,
) -> dict[str, Any]:
    """Keep a verified selected day, else resolve the next real NFL slate fast."""
    selected = _coerce_date(selected_day, date.today())

    games, diag = primary_loader(selected.isoformat())
    diag = diag if isinstance(diag, dict) else {}
    if diag.get("request_ok") and _verified_games_present(games):
        return {
            "state": "FOUND",
            "selected_date": selected,
            "resolved_date": selected,
            "advanced": False,
            "source": "primary",
        }

    calendar_end = selected + timedelta(days=max(0, int(calendar_lookahead_days)))
    try:
        known_dates = _normalized_future_dates(
            nflverse_schedule_dates(selected, calendar_end), selected, calendar_end
        )
    except Exception:
        known_dates = []
    if known_dates:
        return {
            "state": "FOUND",
            "selected_date": selected,
            "resolved_date": known_dates[0],
            "advanced": True,
            "source": "schedule",
        }

    # Calendar unavailable: bounded network fallback only. Never scan the full
    # 370-day calendar horizon over the network.
    for offset in range(1, max(0, int(network_fallback_days)) + 1):
        candidate = selected + timedelta(days=offset)
        games, diag = primary_loader(candidate.isoformat())
        diag = diag if isinstance(diag, dict) else {}
        if diag.get("request_ok") and _verified_games_present(games):
            return {
                "state": "FOUND",
                "selected_date": selected,
                "resolved_date": candidate,
                "advanced": True,
                "source": "primary_scan",
            }

    return {
        "state": "NO_GAMES",
        "selected_date": selected,
        "resolved_date": selected,
        "advanced": False,
        "source": "none",
    }


__all__ = [
    "CALENDAR_LOOKAHEAD_DAYS",
    "NETWORK_FALLBACK_DAYS",
    "resolve_spread_slate_date",
]
