"""Universal CFB next-slate navigation V1.

Presentation/navigation-only helper. Resolves the nearest CFB date with at least
one verified future scheduled game, then replaces CFB date_input controls with a
read-only auto-selected slate label. It never modifies model or market math.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping

import requests

MODEL_VERSION = "API2 CFB UNIVERSAL NEXT SLATE NAVIGATION V1"
SESSION_DATE_KEY = "cfb_universal_next_slate_date"
MAX_SCAN_DAYS = 14

_PREGAME = {"scheduled", "pre", "created", "pregame", "not started"}
_TERMINAL_OR_LIVE = {
    "final", "closed", "completed", "complete", "in progress", "live", "halftime",
    "postponed", "cancelled", "canceled",
}


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("CFB slate date is required")
    return datetime.fromisoformat(text[:10]).date()


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _status(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def game_is_future_pregame(game: Mapping[str, Any], *, now_utc: datetime) -> bool:
    state = _status(game.get("status") or game.get("state"))
    if state in _TERMINAL_OR_LIVE:
        return False
    if state and state not in _PREGAME:
        return False
    kickoff = _as_utc(game.get("kickoff_iso") or game.get("date") or game.get("start_time"))
    return kickoff is not None and kickoff > now_utc.astimezone(timezone.utc)


def resolve_next_cfb_slate_date(
    start_date: Any,
    games_loader: Callable[[date], Iterable[Mapping[str, Any]]],
    *,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    max_days: int = MAX_SCAN_DAYS,
) -> date | None:
    start = _as_date(start_date)
    now_utc = now_provider()
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_utc = now_utc.astimezone(timezone.utc)
    for offset in range(max(0, int(max_days)) + 1):
        day = start + timedelta(days=offset)
        try:
            games = list(games_loader(day) or [])
        except Exception:
            continue
        if any(game_is_future_pregame(game, now_utc=now_utc) for game in games if isinstance(game, Mapping)):
            return day
    return None


def espn_navigation_games_for_date(target_date: Any) -> list[dict[str, Any]]:
    """Read-only FBS navigation fallback used only when the primary schedule is empty."""
    day = _as_date(target_date)
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
    try:
        response = requests.get(
            url,
            params={"dates": day.strftime("%Y%m%d"), "limit": 500, "groups": 80},
            timeout=8,
            headers={"User-Agent": "KyreSportsAI/CFB-Next-Slate-V1", "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return []
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        status_type = (event.get("status") or {}).get("type") or {}
        rows.append({
            "status": status_type.get("state") or status_type.get("description") or "",
            "kickoff_iso": event.get("date") or "",
        })
    return rows


def resolve_runtime_cfb_slate_date(
    *,
    games_loader: Callable[[date], Iterable[Mapping[str, Any]]],
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    max_days: int = MAX_SCAN_DAYS,
) -> date | None:
    now = now_provider()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    def resilient_loader(day: date):
        try:
            primary = list(games_loader(day) or [])
        except Exception:
            primary = []
        return primary or espn_navigation_games_for_date(day)

    return resolve_next_cfb_slate_date(
        now.date(),
        resilient_loader,
        now_provider=lambda: now,
        max_days=max_days,
    )


@contextmanager
def install_cfb_next_slate_date_bridge(resolved_date: date | None):
    import streamlit as st

    native = st.date_input

    def bridge(label, *args, **kwargs):
        if resolved_date is None:
            st.caption("📅 Next CFB slate • unavailable — no verified upcoming slate found")
            value = kwargs.get("value")
            if value is None and args:
                value = args[0]
            return _as_date(value or datetime.now(timezone.utc).date())
        st.caption(f"📅 Next CFB slate • {resolved_date.strftime('%a %b %d, %Y')}")
        return resolved_date

    st.date_input = bridge
    try:
        yield
    finally:
        st.date_input = native


__all__ = [
    "MAX_SCAN_DAYS", "MODEL_VERSION", "SESSION_DATE_KEY", "game_is_future_pregame",
    "espn_navigation_games_for_date", "install_cfb_next_slate_date_bridge", "resolve_next_cfb_slate_date",
    "resolve_runtime_cfb_slate_date",
]
