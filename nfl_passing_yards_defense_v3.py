"""NFL Passing Yards pass-defense V3 — verified event bridge hardening.

Additive wrapper over V2. It fixes two source-shape issues exposed by live ESPN
opening-week certification:

1) ESPN schedule event timestamps are offset-aware ISO values while a selected
   slate/cutoff date may be a plain calendar date. V3 normalizes comparisons to
   UTC.
2) ESPN team box scores can return composite stats such as ``completionAttempts``
   with ``value='-'`` while the verified ``displayValue`` contains ``24/35``.
   V1 treated the placeholder as the value and therefore lost attempts. V3 uses
   the display value only when the primary value is empty/placeholder.

This changes source parsing only. Exact ESPN IDs, fail-closed behavior, Step 3
math/evidence, sportsbook projection influence 0.0%, and downstream projection
contracts remain unchanged.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

import nfl_passing_yards_defense_v1 as base
import nfl_passing_yards_defense_v2 as prior

MODEL_VERSION = "NFL PASSING YARDS PASS DEFENSE V3 • UTC + BOXSCORE SOURCE-SHAPE HARDENING"


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


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


def _box_stat_v3(team_row: dict, aliases: tuple[str, ...]):
    """Read ESPN box-score values without accepting '-' as usable data."""
    lookup = {}
    for item in (team_row or {}).get("statistics") or []:
        if not isinstance(item, dict):
            continue
        for key in (base._norm(item.get("name")), base._norm(item.get("label")), base._norm(item.get("abbreviation"))):
            if key:
                lookup[key] = item
    for alias in aliases:
        row = lookup.get(base._norm(alias))
        if not row:
            continue
        raw = row.get("value")
        if raw is not None and _safe(raw) not in {"", "-", "—", "--"}:
            return raw
        display = row.get("displayValue")
        if display is not None and _safe(display) not in {"", "-", "—", "--"}:
            return display
    return None


def parse_recent_defense_game(summary: dict, defense_team_id: str) -> dict:
    """Parse what the exact opponent produced against the verified defense."""
    teams = ((summary or {}).get("boxscore") or {}).get("teams") or []
    opponent = None
    for row in teams:
        if not isinstance(row, dict):
            continue
        if _safe((row.get("team") or {}).get("id")) != _safe(defense_team_id):
            opponent = row
            break
    if not opponent:
        return {}

    yards = _num(_box_stat_v3(opponent, ("passingYards", "Pass Yards", "netPassingYards", "Passing")))
    comp_att = _safe(_box_stat_v3(opponent, ("completionAttempts", "completionsAttempts", "C/ATT", "Comp-Att", "Comp/Att")))
    completions = attempts = math.nan
    if "/" in comp_att:
        left, right = comp_att.split("/", 1)
        completions, attempts = _num(left), _num(right)
    elif "-" in comp_att:
        left, right = comp_att.split("-", 1)
        completions, attempts = _num(left), _num(right)

    if not _finite(yards):
        return {}
    return {
        "passing_yards_allowed": yards,
        "completions_allowed": completions,
        "attempts_allowed": attempts,
        "completion_pct_allowed": (100.0 * completions / attempts) if _finite(completions) and _finite(attempts) and attempts > 0 else math.nan,
        "yards_per_attempt_allowed": (yards / attempts) if _finite(attempts) and attempts > 0 else math.nan,
    }


def _with_verified_event_parser(func, *args, **kwargs):
    original_rows = base._completed_event_rows
    original_parser = base.parse_recent_defense_game
    base._completed_event_rows = _completed_event_rows_utc
    base.parse_recent_defense_game = parse_recent_defense_game
    try:
        return func(*args, **kwargs)
    finally:
        base._completed_event_rows = original_rows
        base.parse_recent_defense_game = original_parser


def build_pass_defense_profile(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str) -> dict:
    """Run certified V2 with UTC-safe filtering and live ESPN boxscore parsing."""
    row = dict(
        _with_verified_event_parser(
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
    row["boxscore_parser"] = "ESPN VALUE WITH DISPLAY FALLBACK FOR PLACEHOLDERS"
    row["sportsbook_influence"] = 0.0
    return row


def _verified_boxscore_season(
    team_id: str,
    year: int,
    season_type: int,
    cutoff_date: str,
    partial_season: dict | None = None,
):
    """Expose V2's verified aggregate through the hardened event parser."""
    return _with_verified_event_parser(
        prior._verified_boxscore_season,
        team_id,
        year,
        season_type,
        cutoff_date,
        partial_season,
    )


matchup_grade = prior.matchup_grade
parse_season_pass_defense = prior.parse_season_pass_defense

__all__ = [
    "MODEL_VERSION",
    "build_pass_defense_profile",
    "matchup_grade",
    "parse_recent_defense_game",
    "parse_season_pass_defense",
]
