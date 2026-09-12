"""NFL Passing Yards Step 2 — descriptive quarterback passing profile.

This compatibility surface preserves the certified Step 2 contract while the
implementation lives in ``nfl_passing_yards_profile_v1_impl``. Step 2 remains
descriptive evidence and does not itself create a passing-yards projection.

The early-season bridge is verified-source only: current regular-season data
always wins, and the immediately prior regular season is used only when the new
regular season has no usable sample. No sportsbook input is accepted here.

ESPN source-shape hardening:
* athlete all-splits payloads can expose ``gamesPlayed`` in ``general`` while
  passing totals live in ``passing``;
* the current web-v3 game-log payload stores per-game values under
  ``seasonTypes -> categories -> events`` and uses top-level ``names`` as the
  stat keys, while top-level ``events`` is a metadata map.

Only those exact verified ESPN shapes are recovered. No synthetic game rows or
statistics are created.
"""
from __future__ import annotations

import math

import pandas as pd

import nfl_passing_yards_profile_v1_impl as _impl

# Preserve the full public/private surface used by frozen tests and downstream
# modules without duplicating the implementation body.
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

_IMPL_BUILD_QB_PROFILE = _impl.build_qb_profile
_IMPL_PARSE_SEASON_PASSING = _impl.parse_season_passing
_IMPL_PARSE_RECENT_PASSING = _impl.parse_recent_passing


def _espn_games_played(payload: dict) -> float:
    """Read only a games-played stat across ESPN split categories."""
    splits = (payload or {}).get("splits") or {}
    categories = splits.get("categories") if isinstance(splits, dict) else None
    if not isinstance(categories, list):
        categories = (payload or {}).get("categories") or []

    aliases = {
        _impl._norm("gamesPlayed"),
        _impl._norm("teamGamesPlayed"),
        _impl._norm("games"),
        _impl._norm("GP"),
        _impl._norm("TGP"),
    }
    for category in categories:
        if not isinstance(category, dict):
            continue
        for stat in category.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            keys = {
                _impl._norm(stat.get("name")),
                _impl._norm(stat.get("displayName")),
                _impl._norm(stat.get("shortDisplayName")),
                _impl._norm(stat.get("abbreviation")),
            }
            if not (keys & aliases):
                continue
            for field in ("value", "displayValue"):
                value = _impl._num(stat.get(field))
                if _impl._finite(value) and value > 0:
                    return float(value)
    return math.nan


def parse_season_passing(payload: dict) -> dict:
    """Preserve certified passing parsing and recover ESPN's split games field."""
    row = dict(_IMPL_PARSE_SEASON_PASSING(payload) or {})
    if row.get("ready"):
        return row

    games = _espn_games_played(payload)
    if not _impl._finite(games) or games <= 0:
        return row

    completions = _impl._num(row.get("completions"))
    attempts = _impl._num(row.get("attempts"))
    yards = _impl._num(row.get("passing_yards"))
    row["games"] = games
    row["yards_per_game"] = yards / games if _impl._finite(yards) else math.nan
    row["attempts_per_game"] = attempts / games if _impl._finite(attempts) else math.nan
    row["completions_per_game"] = completions / games if _impl._finite(completions) else math.nan
    row["ready"] = bool(
        all(_impl._finite(x) for x in (games, completions, attempts, yards))
        and games > 0
        and attempts > 0
    )
    return row


def _pick_recent_stat(stat_lookup: dict, *aliases: str):
    for alias in aliases:
        key = _impl._norm(alias)
        if key in stat_lookup and _impl._finite(stat_lookup[key]):
            return float(stat_lookup[key])
    return math.nan


def _web_v3_recent_rows(payload: dict) -> list[dict]:
    """Parse ESPN's verified web-v3 seasonTypes game-log structure."""
    names = list((payload or {}).get("names") or [])
    season_types = list((payload or {}).get("seasonTypes") or [])
    event_meta = (payload or {}).get("events") or {}
    if not names or not season_types or not isinstance(event_meta, dict):
        return []

    norm_names = [_impl._norm(name) for name in names]
    rows: list[dict] = []
    seen: set[str] = set()

    for season_type in season_types:
        if not isinstance(season_type, dict):
            continue
        season_label = _impl._safe(season_type.get("displayName") or season_type.get("name")).lower()
        # Opening-week bridge is a regular-season evidence path. Avoid mixing
        # preseason/postseason when ESPN returns multiple season-type blocks.
        if season_label and "regular" not in season_label:
            continue
        for category in season_type.get("categories") or []:
            if not isinstance(category, dict) or _impl._safe(category.get("type")).lower() != "event":
                continue
            for event in category.get("events") or []:
                if not isinstance(event, dict):
                    continue
                event_id = _impl._safe(event.get("eventId") or event.get("id"))
                if not event_id.isdigit() or event_id in seen:
                    continue
                values = event.get("stats") or []
                if not isinstance(values, list) or not values:
                    continue
                stat_lookup = {
                    norm_names[i]: _impl._num(values[i])
                    for i in range(min(len(norm_names), len(values)))
                    if norm_names[i]
                }
                attempts = _pick_recent_stat(stat_lookup, "ATT", "passingAttempts", "passAttempts", "attempts")
                yards = _pick_recent_stat(stat_lookup, "YDS", "passingYards", "passYards", "yards")
                if not (_impl._finite(attempts) and _impl._finite(yards)):
                    continue

                meta = event_meta.get(event_id) or {}
                if not isinstance(meta, dict):
                    meta = {}
                opponent = meta.get("opponent") or {}
                if isinstance(opponent, dict):
                    opponent_name = _impl._safe(
                        opponent.get("abbreviation") or opponent.get("displayName") or opponent.get("name"),
                        "—",
                    )
                else:
                    opponent_name = _impl._safe(opponent, "—")
                date_value = meta.get("gameDate") or meta.get("date")
                try:
                    date_text = pd.to_datetime(date_value).strftime("%Y-%m-%d") if date_value else ""
                except Exception:
                    date_text = _impl._safe(date_value)
                site = _impl._safe(meta.get("atVs") or meta.get("homeAway")).lower()
                home_away = "away" if site in {"@", "away"} else ("home" if site in {"vs", "home"} else "")
                rows.append(
                    {
                        "event_id": event_id,
                        "date": date_text,
                        "opponent": opponent_name,
                        "home_away": home_away,
                        "completions": _pick_recent_stat(stat_lookup, "CMP", "completions"),
                        "attempts": attempts,
                        "passing_yards": yards,
                        "passing_tds": _pick_recent_stat(stat_lookup, "TD", "passingTouchdowns", "passTouchdowns"),
                        "interceptions": _pick_recent_stat(stat_lookup, "INT", "interceptions", "passingInterceptions"),
                    }
                )
                seen.add(event_id)

    def sort_key(row):
        stamp = pd.to_datetime(row.get("date"), errors="coerce")
        return stamp if pd.notna(stamp) else pd.Timestamp.min

    rows.sort(key=sort_key, reverse=True)
    return rows


def parse_recent_passing(payload: dict) -> list[dict]:
    """Parse certified legacy shape first, then current ESPN web-v3 shape."""
    legacy = list(_IMPL_PARSE_RECENT_PASSING(payload) or [])
    if legacy:
        return legacy
    return _web_v3_recent_rows(payload)


def build_qb_profile(athlete_id: str, qb_name: str, year: int, season_type: int = 2) -> dict:
    """Delegate while honoring loader hooks and verified ESPN shape recovery."""
    original_season_loader = _impl._season_stats_payload
    original_gamelog_loader = _impl._gamelog_payload
    original_season_parser = _impl.parse_season_passing
    original_recent_parser = _impl.parse_recent_passing
    _impl._season_stats_payload = globals()["_season_stats_payload"]
    _impl._gamelog_payload = globals()["_gamelog_payload"]
    _impl.parse_season_passing = parse_season_passing
    _impl.parse_recent_passing = parse_recent_passing
    try:
        return _IMPL_BUILD_QB_PROFILE(athlete_id, qb_name, year, season_type)
    finally:
        _impl._season_stats_payload = original_season_loader
        _impl._gamelog_payload = original_gamelog_loader
        _impl.parse_season_passing = original_season_parser
        _impl.parse_recent_passing = original_recent_parser


__all__ = [
    "MODEL_VERSION",
    "build_qb_profile",
    "parse_recent_passing",
    "parse_season_passing",
]
