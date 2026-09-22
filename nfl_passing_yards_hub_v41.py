"""NFL Passing Yards V41 — rolling next-game-date guard.

Additive controller wrapper over frozen V40. Before the certified Passing Yards
surface renders, the selected slate date is checked for NFL games. Empty dates
advance to the first future date with games. ESPN remains the primary verified
schedule source; nflverse is a field-level fallback only when the primary route
cannot prove a usable date.

Frozen:
- V40 Phoenix matchup-selector display;
- V39 presentation grades;
- V38 Phoenix kickoff display;
- V37 smart-slate behavior;
- all projection/probability/market/edge calculations;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

MODEL_VERSION = "NFL PASSING YARDS V41 • ROLLING NEXT GAME DATE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v40"
PRIMARY_SCHEDULE_SOURCE = "ESPN NFL scoreboard"
FALLBACK_SCHEDULE_SOURCE = "nflverse games.csv"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MAX_LOOKAHEAD_DAYS = 7

V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"
V8_MATCHUP_KEY = "nfl_passing_yards_v8_matchup"
ROLLING_RESOLVED_KEY = "nfl_passing_yards_v41_resolved_date"
ROLLING_WIDGET_KEY_PREFIX = "nfl_passing_yards_v41_date_input"

ET = ZoneInfo("America/New_York")


def _coerce_date(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _default_primary_finder(start_day: date, max_forward_days: int):
    import nfl_passing_yards_hub_v12 as auto_slate

    return auto_slate.find_next_verified_slate(
        start_day,
        max_forward_days=max_forward_days,
    )


def _default_fallback_finder(start_day: date, max_forward_days: int) -> date | None:
    """Return the first nflverse schedule date in the bounded forward window."""
    try:
        from sports_api import nfl_data_nflverse_v1 as nflverse

        frame = nflverse._load_games_csv()
    except Exception:
        return None

    if frame is None or getattr(frame, "empty", True) or "gameday" not in frame.columns:
        return None

    end_day = start_day + timedelta(days=max(0, int(max_forward_days)))
    found: list[date] = []
    for raw in frame["gameday"].dropna().astype(str).tolist():
        try:
            game_day = date.fromisoformat(raw[:10])
        except Exception:
            continue
        if start_day <= game_day <= end_day:
            found.append(game_day)

    return min(found) if found else None


def resolve_next_play_date(
    selected_day: date,
    *,
    primary_finder: Callable[[date, int], tuple[date, int | None, str]] | None = None,
    fallback_finder: Callable[[date, int], date | None] | None = None,
    max_lookahead_days: int = MAX_LOOKAHEAD_DAYS,
) -> dict[str, Any]:
    """Resolve a selected date to the first non-empty NFL game date."""
    selected = _coerce_date(selected_day, datetime.now(ET).date())
    lookahead = max(0, int(max_lookahead_days))
    primary = primary_finder or _default_primary_finder
    fallback = fallback_finder or _default_fallback_finder

    primary_status = "verification_failed"
    try:
        resolved, offset, status = primary(selected, lookahead)
        resolved = _coerce_date(resolved, selected)
        primary_status = str(status or "").strip().lower()
        if primary_status == "verified":
            return {
                "state": "FOUND",
                "selected_date": selected,
                "resolved_date": resolved,
                "advanced": resolved != selected or bool((offset or 0) > 0),
                "source": PRIMARY_SCHEDULE_SOURCE,
                "primary_status": primary_status,
            }
    except Exception:
        primary_status = "verification_failed"

    try:
        fallback_date = fallback(selected, lookahead)
    except Exception:
        fallback_date = None

    if fallback_date is not None:
        fallback_date = _coerce_date(fallback_date, selected)
        end_day = selected + timedelta(days=lookahead)
        if selected <= fallback_date <= end_day:
            return {
                "state": "FOUND",
                "selected_date": selected,
                "resolved_date": fallback_date,
                "advanced": fallback_date != selected,
                "source": FALLBACK_SCHEDULE_SOURCE,
                "primary_status": primary_status,
            }

    return {
        "state": "PROVIDER_ERROR" if primary_status == "verification_failed" else "NO_GAMES",
        "selected_date": selected,
        "resolved_date": selected,
        "advanced": False,
        "source": "",
        "primary_status": primary_status,
    }


def _selected_date() -> date:
    import streamlit as st

    today_et = datetime.now(ET).date()
    # V8_DATE_INPUT_KEY belongs to the legacy Streamlit widget and may be
    # replayed by an already-open browser session. V41 owns the canonical
    # selected slate through V8_DATE_KEY instead.
    value = st.session_state.get(V8_DATE_KEY, today_et)
    return _coerce_date(value, today_et)


def _rolling_widget_key(day: date) -> str:
    resolved = _coerce_date(day, datetime.now(ET).date())
    return f"{ROLLING_WIDGET_KEY_PREFIX}_{resolved.isoformat()}"


def _date_input_proxy(resolved_day: date, original_date_input):
    """Give only the Passing Yards slate widget a fresh, date-versioned key."""
    widget_key = _rolling_widget_key(resolved_day)

    def wrapped(label, *args, **kwargs):
        if (
            str(label) == "NFL Passing Yards slate date"
            and kwargs.get("key") == V8_DATE_INPUT_KEY
        ):
            kwargs["key"] = widget_key
            kwargs["value"] = resolved_day
        return original_date_input(label, *args, **kwargs)

    return wrapped


def _prime_next_game_date(
    *,
    primary_finder: Callable[[date, int], tuple[date, int | None, str]] | None = None,
    fallback_finder: Callable[[date, int], date | None] | None = None,
) -> dict[str, Any]:
    import streamlit as st

    selected = _selected_date()
    result = resolve_next_play_date(
        selected,
        primary_finder=primary_finder,
        fallback_finder=fallback_finder,
        max_lookahead_days=MAX_LOOKAHEAD_DAYS,
    )

    if result.get("state") == "FOUND":
        resolved = _coerce_date(result.get("resolved_date"), selected)
        st.session_state[ROLLING_RESOLVED_KEY] = resolved.isoformat()
        st.session_state[V8_DATE_KEY] = resolved

        # Retire the legacy widget key before V40/V8 render. An already-open
        # browser can replay that old widget value (the observed 2026-09-19
        # production failure) even after the server resolved a newer slate.
        st.session_state.pop(V8_DATE_INPUT_KEY, None)

        if resolved != selected:
            st.session_state.pop(V8_MATCHUP_KEY, None)

    return result


def render_nfl_passing_yards_hub() -> None:
    result = _prime_next_game_date()

    import streamlit as st
    import nfl_passing_yards_hub_v40 as prior

    selected = _selected_date()
    resolved = _coerce_date(result.get("resolved_date"), selected)
    original_date_input = st.date_input
    st.date_input = _date_input_proxy(resolved, original_date_input)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        st.date_input = original_date_input


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V41 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "ET",
    "FALLBACK_SCHEDULE_SOURCE",
    "FROZEN_PRIOR",
    "MAX_LOOKAHEAD_DAYS",
    "MODEL_VERSION",
    "PRIMARY_SCHEDULE_SOURCE",
    "ROLLING_RESOLVED_KEY",
    "ROLLING_WIDGET_KEY_PREFIX",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "V8_MATCHUP_KEY",
    "_date_input_proxy",
    "_prime_next_game_date",
    "_rolling_widget_key",
    "resolve_next_play_date",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
