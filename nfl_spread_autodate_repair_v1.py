"""Pure session-state helper for NFL Spread empty-date auto-advance.

The V5 implementation was intentionally one-shot. This repair keeps the fast
resolver but re-checks whenever the visible date changes, including manual date
changes, while caching a verified unchanged date so normal rerenders stay fast.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, MutableMapping

from nfl_active_slate_runtime_v1 import is_manual_mode


_CHECKED_DATE_KEY = "_nfl_spread_v6_checked_date"
_CHECKED_RESULT_KEY = "_nfl_spread_v6_checked_result"


def _coerce_day(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _current_selected_day(session: MutableMapping[str, Any], today: date) -> date:
    raw = session.get("nfl_spread_v4_date_input")
    if raw is None:
        raw = session.get("nfl_v1_date")
    return _coerce_day(raw, today)


def apply_spread_autodate(
    session: MutableMapping[str, Any],
    today: date,
    resolver: Callable[[date], dict[str, Any]],
) -> dict[str, Any]:
    """Advance an empty visible date and keep verified same-date rerenders fast."""
    selected = _current_selected_day(session, today)
    if is_manual_mode(session):
        return {
            "state": "MANUAL",
            "resolved_date": selected,
            "source": "universal_manual",
            "reason": "manual_override",
            "advanced": False,
        }

    cached_day = _coerce_day(session.get(_CHECKED_DATE_KEY), date.min)
    cached = session.get(_CHECKED_RESULT_KEY)

    if cached_day == selected and isinstance(cached, dict):
        return dict(cached)

    result = dict(resolver(selected) or {})
    target = _coerce_day(result.get("resolved_date"), selected)
    found = str(result.get("state") or "") == "FOUND"

    if found:
        session["nfl_v1_date"] = target
        session["nfl_spread_v4_date_input"] = target
        session[_CHECKED_DATE_KEY] = target.isoformat()
        session[_CHECKED_RESULT_KEY] = dict(result)

        if target != selected:
            session["nfl_spread_v6_feedback"] = (
                f"📅 {selected.isoformat()} has no NFL games. "
                f"Opened the next verified slate: {target.isoformat()}."
            )
    else:
        # Do not permanently cache a fail-closed NO_GAMES result; a transient
        # calendar/provider outage should be allowed to recover on a rerender.
        session.pop(_CHECKED_DATE_KEY, None)
        session.pop(_CHECKED_RESULT_KEY, None)

    return result


__all__ = ["apply_spread_autodate"]
