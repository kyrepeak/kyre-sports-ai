"""Universal NFL future-navigation guard V1.

Shared presentation/runtime policy for active NFL pages:
- only pregame games whose kickoff is still in the future may surface;
- live/final/unknown/stale-pregame games fail closed;
- game selectors are filtered to the allowed future matchup set;
- player/team/market selector values are otherwise untouched.

No projection, probability, market, sportsbook, or stake math is modified here.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import re
import sys
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd

MODEL_VERSION = "API2 NFL UNIVERSAL FUTURE NAVIGATION V1"
PREGAME_STATES = frozenset({"pre", "scheduled", "created"})
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
_ET = ZoneInfo("America/New_York")
_GAME_LABEL_TOKENS = ("matchup", "choose game", "verified game", "game selector")


def _state(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _as_utc(value: Any) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        ts = pd.to_datetime(value, utc=True)
    except Exception:
        return None
    try:
        return ts.to_pydatetime().astimezone(timezone.utc)
    except Exception:
        return None


def _row_kickoff_utc(row: Mapping[str, Any]) -> datetime | None:
    for key in ("date_utc", "kickoff_utc", "kickoff_at", "start_time", "event_time", "date"):
        parsed = _as_utc(row.get(key))
        if parsed is not None:
            return parsed

    day_raw = str(row.get("game_date") or "").strip()
    tip_raw = str(row.get("tip_et") or "").strip().upper().replace(" ET", "")
    if not day_raw:
        return None
    if tip_raw and tip_raw not in {"TBD", "—", "-"}:
        try:
            local = pd.to_datetime(f"{day_raw} {tip_raw}")
            if local.tzinfo is None:
                local = local.tz_localize(_ET)
            return local.tz_convert("UTC").to_pydatetime()
        except Exception:
            pass
    return None


def future_only_games(games: Any, *, now_utc: datetime | None = None):
    """Return only not-yet-started NFL games, preserving DataFrame shape/order."""
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(games, pd.DataFrame):
        return games
    if games.empty:
        return games.copy()

    keep: list[bool] = []
    now_et_date = now.astimezone(_ET).date()
    for _, series in games.iterrows():
        row = series.to_dict()
        if _state(row.get("state")) not in PREGAME_STATES:
            keep.append(False)
            continue
        kickoff = _row_kickoff_utc(row)
        if kickoff is not None:
            keep.append(kickoff > now)
            continue
        try:
            game_day = pd.to_datetime(row.get("game_date")).date()
        except Exception:
            keep.append(False)
            continue
        keep.append(game_day > now_et_date)
    return games.loc[keep].copy().reset_index(drop=True)


def make_future_only_loader(loader: Callable[[str], tuple[Any, Mapping[str, Any]]], *, now_provider: Callable[[], datetime] | None = None):
    """Wrap the existing NFL slate loader without changing provider ownership."""
    provider = now_provider or (lambda: datetime.now(timezone.utc))

    def wrapped(day_str: str):
        games, diag = loader(day_str)
        filtered = future_only_games(games, now_utc=provider())
        out_diag = dict(diag or {})
        if isinstance(filtered, pd.DataFrame):
            out_diag["games"] = int(len(filtered))
            out_diag["future_only"] = True
        return filtered, out_diag

    if hasattr(loader, "clear"):
        wrapped.clear = loader.clear
    return wrapped


@contextmanager
def install_future_only_nfl_loader(original_loader, future_loader):
    """Patch direct-import loader aliases for the active NFL render, then restore."""
    patched: list[tuple[Any, Any]] = []
    for module in tuple(sys.modules.values()):
        if module is None:
            continue
        try:
            current = getattr(module, "load_nfl_slate", None)
        except Exception:
            continue
        if current is original_loader:
            try:
                setattr(module, "load_nfl_slate", future_loader)
                patched.append((module, current))
            except Exception:
                continue
    try:
        yield
    finally:
        for module, previous in reversed(patched):
            try:
                setattr(module, "load_nfl_slate", previous)
            except Exception:
                pass


def _matchup_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.split("•", 1)[0].strip()
    text = re.sub(r"\s+at\s+", " @ ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def allowed_matchups(games: Any) -> set[str]:
    if not isinstance(games, pd.DataFrame) or games.empty:
        return set()
    values: set[str] = set()
    for _, row in games.iterrows():
        away = str(row.get("away_team") or "").strip()
        home = str(row.get("home_team") or "").strip()
        away_abbr = str(row.get("away_abbr") or "").strip()
        home_abbr = str(row.get("home_abbr") or "").strip()
        if away and home:
            values.add(f"{away} @ {home}")
        if away_abbr and home_abbr:
            values.add(f"{away_abbr} @ {home_abbr}")
    return values


def _is_game_selector(label: Any) -> bool:
    text = str(label or "").strip().lower()
    return text in {"game", "games", "choose game"} or any(token in text for token in _GAME_LABEL_TOKENS)


def filter_selector_options(label: Any, options: Iterable[Any], *, allowed_matchups: set[str], format_func: Callable[[Any], Any] = str) -> list[Any]:
    values = list(options)
    if not _is_game_selector(label):
        return values
    normalized_allowed = {_matchup_text(value) for value in allowed_matchups if str(value).strip()}
    if not normalized_allowed:
        return []
    filtered: list[Any] = []
    for value in values:
        shown = _matchup_text(format_func(value))
        if any(allowed == shown or allowed in shown or shown in allowed for allowed in normalized_allowed):
            filtered.append(value)
    return filtered


def _active_day(session: Mapping[str, Any]) -> str | None:
    value = session.get("nfl_v1_date") or session.get("nfl_active_slate_date")
    if value is None:
        return None
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return None


@contextmanager
def install_nfl_future_selector_bridge(session, *, future_loader: Callable[[str], tuple[Any, Mapping[str, Any]]]):
    """Filter only NFL game/matchup selectboxes; preserve all other selector values."""
    import streamlit as st

    parent = st.selectbox

    def bridge(label, options, *args, **kwargs):
        if not _is_game_selector(label):
            return parent(label, options, *args, **kwargs)
        day = _active_day(session)
        if not day:
            return parent(label, [], *args, **kwargs)
        try:
            games, diag = future_loader(day)
        except Exception:
            return parent(label, [], *args, **kwargs)
        if not isinstance(diag, Mapping) or diag.get("request_ok") is not True:
            return parent(label, [], *args, **kwargs)
        allowed = allowed_matchups(games)
        format_func = kwargs.get("format_func", str)
        filtered = filter_selector_options(label, options, allowed_matchups=allowed, format_func=format_func)
        call_kwargs = dict(kwargs)
        if filtered and isinstance(call_kwargs.get("index"), int):
            call_kwargs["index"] = min(max(0, call_kwargs["index"]), len(filtered) - 1)
        elif not filtered:
            call_kwargs["index"] = None
        return parent(label, filtered, *args, **call_kwargs)

    st.selectbox = bridge
    try:
        yield
    finally:
        st.selectbox = parent


__all__ = [
    "MAY_MODIFY_MARKET_MATH", "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION", "PREGAME_STATES", "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED",
    "allowed_matchups", "filter_selector_options", "future_only_games",
    "install_future_only_nfl_loader", "install_nfl_future_selector_bridge", "make_future_only_loader",
]
