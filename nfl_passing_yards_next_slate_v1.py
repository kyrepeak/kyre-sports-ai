"""NFL Passing Yards rolling next-game-date resolver.

This module owns date selection only. It prefers the repository's existing
nflverse schedule snapshot for the calendar and uses the frozen ESPN slate
loader only as a fallback when the schedule snapshot is unavailable.

It does not change projections, probabilities, markets, grades, or wagering.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable

MAX_LOOKAHEAD_DAYS = 370


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


def _normalize_schedule_dates(values: Iterable[Any], start: date, end: date) -> list[date]:
    resolved: set[date] = set()
    for value in values or ():
        day = _coerce_date(value, start - timedelta(days=1))
        if start <= day <= end:
            resolved.add(day)
    return sorted(resolved)


def resolve_next_game_date(
    selected_day: date,
    primary_loader: Callable[[str], tuple[Any, dict[str, Any]]],
    *,
    schedule_date_loader: Callable[[date, date], Iterable[Any]] | None = None,
    max_lookahead_days: int = MAX_LOOKAHEAD_DAYS,
) -> dict[str, Any]:
    """Return selected day when it has games, otherwise the next known game day."""
    selected = _coerce_date(selected_day, date.today())
    end = selected + timedelta(days=max(0, int(max_lookahead_days)))

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

    if schedule_date_loader is not None:
        try:
            dates = _normalize_schedule_dates(schedule_date_loader(selected, end), selected, end)
        except Exception:
            dates = []
        if dates:
            resolved = dates[0]
            return {
                "state": "FOUND",
                "selected_date": selected,
                "resolved_date": resolved,
                "advanced": resolved != selected,
                "source": "schedule",
            }

    # Schedule calendar unavailable: bounded fallback scan through the existing
    # verified loader. Provider failures do not invent dates.
    for offset in range(1, max(0, int(max_lookahead_days)) + 1):
        candidate = selected + timedelta(days=offset)
        games, diag = primary_loader(candidate.isoformat())
        diag = diag if isinstance(diag, dict) else {}
        if not diag.get("request_ok"):
            continue
        if _verified_games_present(games):
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


def nflverse_schedule_dates(start: date, end: date) -> list[date]:
    """Read known NFL schedule dates from the repository's cached nflverse feed."""
    from sports_api import nfl_data_nflverse_v1 as nflverse

    frame = nflverse._load_games_csv()
    if frame is None or getattr(frame, "empty", True) or "gameday" not in frame.columns:
        return []

    values = frame["gameday"].dropna().astype(str).tolist()
    return _normalize_schedule_dates(values, start, end)


__all__ = [
    "MAX_LOOKAHEAD_DAYS",
    "nflverse_schedule_dates",
    "resolve_next_game_date",
]
