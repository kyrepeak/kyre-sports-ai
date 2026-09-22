"""Pure navigation helper for NFL Game Totals mobile empty-slate recovery."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

DEFAULT_LOOKAHEAD_DAYS = 14


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def find_next_game_day(
    start_date: date | datetime | str,
    load_slate: Callable[[str], tuple[Any, dict[str, Any]]],
    *,
    max_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> dict[str, Any]:
    """Return the first verified non-empty NFL slate strictly after start_date.

    Provider failures fail closed immediately. Empty, successfully verified dates
    are skipped until the first non-empty slate or the bounded lookahead expires.
    """
    start = _as_date(start_date)
    horizon = max(1, int(max_days))

    for offset in range(1, horizon + 1):
        candidate = start + timedelta(days=offset)
        day_str = candidate.isoformat()
        games, diag = load_slate(day_str)
        diagnostics = diag if isinstance(diag, dict) else {}
        if diagnostics.get("request_ok") is not True:
            return {
                "ready": False,
                "date": None,
                "day_str": None,
                "provider_failed": True,
                "reason": "NFL schedule provider failed while searching for the next game day.",
            }
        try:
            game_count = len(games)
        except TypeError:
            game_count = 0
        if game_count > 0:
            return {
                "ready": True,
                "date": candidate,
                "day_str": day_str,
                "provider_failed": False,
                "reason": "",
            }

    return {
        "ready": False,
        "date": None,
        "day_str": None,
        "provider_failed": False,
        "reason": f"No verified NFL games were found in the next {horizon} days.",
    }


__all__ = ["DEFAULT_LOOKAHEAD_DAYS", "find_next_game_day"]
