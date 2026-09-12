"""NFL Passing Yards Step 2 — descriptive quarterback passing profile.

This compatibility surface preserves the certified Step 2 contract while the
implementation lives in ``nfl_passing_yards_profile_v1_impl``. Step 2 remains
descriptive evidence and does not itself create a passing-yards projection.

The early-season bridge is verified-source only: current regular-season data
always wins, and the immediately prior regular season is used only when the new
regular season has no usable sample. No sportsbook input is accepted here.

ESPN shape note: athlete all-splits payloads can expose ``gamesPlayed`` in the
``general`` category while the passing totals live in ``passing``. The parser
therefore recovers only the games-played field across categories; every passing
metric still comes strictly from the passing category so abbreviations such as
YDS/TD/AVG cannot collide with rushing or receiving statistics.
"""
from __future__ import annotations

import math

import nfl_passing_yards_profile_v1_impl as _impl

# Preserve the full public/private surface used by frozen tests and downstream
# modules without duplicating the implementation body.
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

_IMPL_BUILD_QB_PROFILE = _impl.build_qb_profile
_IMPL_PARSE_SEASON_PASSING = _impl.parse_season_passing


def _espn_games_played(payload: dict) -> float:
    """Read only a games-played stat across ESPN split categories.

    Passing totals remain category-scoped in the certified implementation. This
    helper intentionally refuses to flatten unrelated stat categories because
    ESPN reuses abbreviations such as YDS, TD and AVG across stat families.
    """
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


def build_qb_profile(athlete_id: str, qb_name: str, year: int, season_type: int = 2) -> dict:
    """Delegate while honoring monkeypatched loader hooks and ESPN split shape."""
    original_season_loader = _impl._season_stats_payload
    original_gamelog_loader = _impl._gamelog_payload
    original_season_parser = _impl.parse_season_passing
    _impl._season_stats_payload = globals()["_season_stats_payload"]
    _impl._gamelog_payload = globals()["_gamelog_payload"]
    _impl.parse_season_passing = parse_season_passing
    try:
        return _IMPL_BUILD_QB_PROFILE(athlete_id, qb_name, year, season_type)
    finally:
        _impl._season_stats_payload = original_season_loader
        _impl._gamelog_payload = original_gamelog_loader
        _impl.parse_season_passing = original_season_parser


__all__ = [
    "MODEL_VERSION",
    "build_qb_profile",
    "parse_recent_passing",
    "parse_season_passing",
]
