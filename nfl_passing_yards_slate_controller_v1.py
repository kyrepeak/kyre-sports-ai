"""Passing Yards smart-slate controller.

Small adapter around the frozen V12 verified-slate finder. It does not fetch
schedule data itself and owns no projection, probability, market, or model math.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable


def _coerce_date(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def resolve_next_verified_slate_date(
    selected_day: date,
    finder: Callable[..., tuple[date, int | None, str]],
    *,
    max_lookahead_days: int = 7,
) -> dict[str, Any]:
    """Adapt the frozen V12 finder into an explicit UI-controller state."""
    selected = _coerce_date(selected_day, date.today())
    resolved, offset, status = finder(
        selected,
        max_forward_days=max(0, int(max_lookahead_days)),
    )
    resolved = _coerce_date(resolved, selected)
    status = str(status or "").strip().lower()

    if status == "verified":
        return {
            "state": "FOUND",
            "selected_date": selected,
            "resolved_date": resolved,
            "advanced": bool((offset or 0) > 0 or resolved != selected),
        }
    if status == "verification_failed":
        return {
            "state": "PROVIDER_ERROR",
            "selected_date": selected,
            "resolved_date": selected,
            "advanced": False,
        }
    return {
        "state": "NO_GAMES",
        "selected_date": selected,
        "resolved_date": selected,
        "advanced": False,
    }


def is_empty_slate_notice(value: Any) -> bool:
    """Match only obsolete empty-slate informational notices, never errors."""
    text = " ".join(str(value or "").strip().lower().split())
    if not text or "schedule verification failed" in text:
        return False
    return any(
        marker in text
        for marker in (
            "no nfl games are scheduled on",
            "no verified nfl games were returned for this et date",
            "no nfl games were returned for this selected et calendar date",
        )
    )


__all__ = ["is_empty_slate_notice", "resolve_next_verified_slate_date"]
