"""NFL Passing Yards pressure V2 — early-season verified bridge.

Wraps certified V1. Current-season pressure/protection data always wins. If the
regular season has no usable sample yet, V2 uses the previous regular season as a
clearly-labelled baseline and fills recent-five sack context with verified prior
season summaries. No sportsbook data or fuzzy identity is introduced.
"""
from __future__ import annotations

import math
from typing import Any

import nfl_passing_yards_early_season_v1 as early
import nfl_passing_yards_pressure_v1 as base

MODEL_VERSION = "NFL PASSING YARDS PRESSURE V2 • EARLY SEASON BRIDGE"


def _num(value: Any):
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _avg(rows: list[dict], key: str):
    vals = [_num(row.get(key)) for row in rows]
    vals = [x for x in vals if _finite(x)]
    return sum(vals) / len(vals) if vals else math.nan


def build_pressure_matchup(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    current = dict(base.build_pressure_matchup(
        offense_team_id,
        offense_team_name,
        defense_team_id,
        defense_team_name,
        year,
        season_type,
        cutoff_date,
    ) or {})
    off_recent = list(current.get("recent_offense") or [])
    def_recent = list(current.get("recent_defense") or [])
    source_year = int(year)
    fallback_used = False
    prior: dict = {}

    if early.allow_prior_regular_fallback(season_type) and (
        not current.get("ready") or len(off_recent) < 5 or len(def_recent) < 5
    ):
        prior_year = early.prior_regular_year(year)
        prior = dict(base.build_pressure_matchup(
            offense_team_id,
            offense_team_name,
            defense_team_id,
            defense_team_name,
            prior_year,
            2,
            cutoff_date,
        ) or {})
        if not current.get("ready") and prior.get("ready"):
            for key in ("offense", "defense", "pressure_label", "pressure_basis", "blitz_state"):
                if key in prior:
                    current[key] = prior[key]
            current["pressure_basis"] = f"{current.get('pressure_basis') or 'prior regular-season baseline'} • early-season fallback"
            current["ready"] = True
            current["reason"] = ""
            source_year = prior_year
            fallback_used = True

        off_recent = early.merge_recent_rows(off_recent, list(prior.get("recent_offense") or []), limit=5)
        def_recent = early.merge_recent_rows(def_recent, list(prior.get("recent_defense") or []), limit=5)
        current["recent_offense"] = off_recent
        current["recent_defense"] = def_recent
        current["recent3_sacks_allowed"] = _avg(off_recent[:3], "sacks_taken")
        current["recent5_sacks_allowed"] = _avg(off_recent[:5], "sacks_taken")
        current["recent3_sack_rate_allowed"] = _avg(off_recent[:3], "sack_rate")
        current["recent3_sacks_made"] = _avg(def_recent[:3], "sacks_made")
        current["recent5_sacks_made"] = _avg(def_recent[:5], "sacks_made")
        current["recent3_sack_rate_generated"] = _avg(def_recent[:3], "sack_rate_generated")
        current["prior_recent_offense_games_used"] = max(0, len(off_recent) - len((current.get("recent_offense") or [])[:5]))

    current.update(early.provenance(bool(current.get("ready") and not fallback_used), fallback_used, int(year), source_year))
    current["requested_season_year"] = int(year)
    current["projection_adjustment"] = 0.0
    current["sportsbook_influence"] = 0.0
    return current


parse_defensive_pressure = base.parse_defensive_pressure
parse_offense_protection = base.parse_offense_protection
parse_recent_sacks_made = base.parse_recent_sacks_made
parse_recent_sacks_taken = base.parse_recent_sacks_taken
pressure_label = base.pressure_label

__all__ = [
    "MODEL_VERSION",
    "build_pressure_matchup",
    "parse_defensive_pressure",
    "parse_offense_protection",
    "parse_recent_sacks_made",
    "parse_recent_sacks_taken",
    "pressure_label",
]
