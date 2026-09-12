"""NFL Passing Yards pass-defense V3 — timezone-safe verified event bridge.

Additive wrapper over V2. ESPN schedule event timestamps are offset-aware ISO
values (for example ``...Z``), while a selected slate/cutoff date is commonly a
plain calendar date. V1 compared those values without normalizing timezones,
which can raise a pandas tz-aware/tz-naive comparison error before the verified
prior-season box-score bridge can run.

V3 changes only schedule timestamp normalization. It preserves exact ESPN event
IDs, verified-source fail-closed behavior, all Step 3 math/evidence, sportsbook
projection influence 0.0%, and every projection contract downstream.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import nfl_passing_yards_defense_v1 as base
import nfl_passing_yards_defense_v2 as prior

MODEL_VERSION = "NFL PASSING YARDS PASS DEFENSE V3 • UTC-SAFE VERIFIED EVENT BRIDGE"


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _completed_event_rows_utc(payload: dict, cutoff_date: str, max_games: int = 5) -> list[dict]:
    """Return completed exact ESPN events using one UTC comparison domain."""
    cutoff = pd.to_datetime(cutoff_date, errors="coerce", utc=True)
    rows: list[dict] = []
    for event in (payload or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _safe(event.get("id"))
        event_date = pd.to_datetime(event.get("date"), errors="coerce", utc=True)
        competitions = event.get("competitions") or []
        comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
        status = ((comp.get("status") or {}).get("type") or {}) if isinstance(comp, dict) else {}
        completed = bool(status.get("completed")) or _safe(status.get("state")).lower() == "post"
        if not event_id.isdigit() or pd.isna(event_date) or not completed:
            continue
        if pd.notna(cutoff) and event_date.normalize() >= cutoff.normalize():
            continue
        rows.append({"event_id": event_id, "date": event_date})
    rows.sort(key=lambda row: row["date"], reverse=True)
    return rows[: max(0, int(max_games))]


def _with_utc_event_rows(func, *args, **kwargs):
    original = base._completed_event_rows
    base._completed_event_rows = _completed_event_rows_utc
    try:
        return func(*args, **kwargs)
    finally:
        base._completed_event_rows = original


def build_pass_defense_profile(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str) -> dict:
    """Run certified V2 with timezone-safe schedule filtering only."""
    row = dict(
        _with_utc_event_rows(
            prior.build_pass_defense_profile,
            team_id,
            team_name,
            year,
            season_type,
            cutoff_date,
        )
        or {}
    )
    row["timezone_normalization"] = "UTC"
    row["sportsbook_influence"] = 0.0
    return row


def _verified_boxscore_season(
    team_id: str,
    year: int,
    season_type: int,
    cutoff_date: str,
    partial_season: dict | None = None,
):
    """Expose V2's verified aggregate through the same UTC-safe event filter."""
    return _with_utc_event_rows(
        prior._verified_boxscore_season,
        team_id,
        year,
        season_type,
        cutoff_date,
        partial_season,
    )


matchup_grade = prior.matchup_grade
parse_recent_defense_game = prior.parse_recent_defense_game
parse_season_pass_defense = prior.parse_season_pass_defense

__all__ = [
    "MODEL_VERSION",
    "build_pass_defense_profile",
    "matchup_grade",
    "parse_recent_defense_game",
    "parse_season_pass_defense",
]
