from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Iterable, Mapping


ACTIVE_STATES = frozenset({
    "pre",
    "scheduled",
    "in",
    "live",
    "in_progress",
    "in-progress",
    "halftime",
})
FINAL_STATES = frozenset({"post", "final", "completed", "closed"})


def _normalize_state(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def classify_loaded_slate(games: Any, diag: Mapping[str, Any]) -> str:
    if not isinstance(diag, Mapping) or diag.get("request_ok") is not True:
        return "UNAVAILABLE"
    if games is None:
        return "UNAVAILABLE"
    try:
        if len(games) == 0:
            return "EMPTY"
    except Exception:
        return "UNAVAILABLE"

    try:
        raw_states = list(games["state"])
    except Exception:
        try:
            raw_states = [row.get("state") for row in games]
        except Exception:
            return "UNAVAILABLE"

    states = [_normalize_state(value) for value in raw_states]
    if not states or any(not state for state in states):
        return "UNAVAILABLE"
    if any(state not in ACTIVE_STATES and state not in FINAL_STATES for state in states):
        return "UNAVAILABLE"
    if any(state in ACTIVE_STATES for state in states):
        return "ACTIVE"
    if all(state in FINAL_STATES for state in states):
        return "EXHAUSTED"
    return "UNAVAILABLE"


def _safe_load(primary_loader: Callable[[str], tuple[Any, Mapping[str, Any]]], day: date):
    try:
        games, diag = primary_loader(day.isoformat())
    except Exception as exc:
        return None, {"request_ok": False, "error": str(exc)}
    return games, diag


def _result(*, state: str, resolved_date: date | None, source: str, reason: str, today_et: date) -> dict[str, Any]:
    return {
        "state": state,
        "resolved_date": resolved_date,
        "source": source,
        "reason": reason,
        "advanced": resolved_date is not None and resolved_date != today_et,
    }


def resolve_active_slate(
    today_et: date,
    primary_loader: Callable[[str], tuple[Any, Mapping[str, Any]]],
    calendar_dates: Callable[[date, date], Iterable[date]],
    *,
    calendar_lookahead_days: int = 370,
    network_fallback_days: int = 21,
) -> dict[str, Any]:
    games, diag = _safe_load(primary_loader, today_et)
    current_state = classify_loaded_slate(games, diag)
    if current_state == "ACTIVE":
        return _result(
            state="FOUND",
            resolved_date=today_et,
            source="current_verified",
            reason="current_slate_active",
            today_et=today_et,
        )
    if current_state == "UNAVAILABLE":
        return _result(
            state="UNAVAILABLE",
            resolved_date=None,
            source="primary",
            reason="current_slate_unavailable",
            today_et=today_et,
        )

    checked: set[date] = {today_et}
    end = today_et + timedelta(days=max(0, int(calendar_lookahead_days)))
    calendar_ok = True
    try:
        candidates = sorted({candidate for candidate in calendar_dates(today_et + timedelta(days=1), end) if isinstance(candidate, date) and today_et < candidate <= end})
    except Exception:
        candidates = []
        calendar_ok = False

    for candidate in candidates:
        checked.add(candidate)
        candidate_games, candidate_diag = _safe_load(primary_loader, candidate)
        candidate_state = classify_loaded_slate(candidate_games, candidate_diag)
        if candidate_state == "ACTIVE":
            return _result(
                state="FOUND",
                resolved_date=candidate,
                source="calendar_verified",
                reason="next_verified_calendar_slate",
                today_et=today_et,
            )
        if candidate_state == "UNAVAILABLE":
            return _result(
                state="UNAVAILABLE",
                resolved_date=None,
                source="calendar_candidate",
                reason="candidate_unavailable",
                today_et=today_et,
            )

    for offset in range(1, max(0, int(network_fallback_days)) + 1):
        candidate = today_et + timedelta(days=offset)
        if candidate in checked:
            continue
        candidate_games, candidate_diag = _safe_load(primary_loader, candidate)
        candidate_state = classify_loaded_slate(candidate_games, candidate_diag)
        if candidate_state == "ACTIVE":
            return _result(
                state="FOUND",
                resolved_date=candidate,
                source="primary_fallback",
                reason="next_verified_primary_slate",
                today_et=today_et,
            )
        if candidate_state == "UNAVAILABLE":
            return _result(
                state="UNAVAILABLE",
                resolved_date=None,
                source="primary_fallback",
                reason="fallback_unavailable",
                today_et=today_et,
            )

    return _result(
        state="UNAVAILABLE",
        resolved_date=None,
        source="calendar" if calendar_ok else "primary_fallback",
        reason="no_verified_future_slate",
        today_et=today_et,
    )


__all__ = ["classify_loaded_slate", "resolve_active_slate"]
