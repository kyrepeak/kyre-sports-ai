"""NFL Passing Yards pass-defense V2 — early-season verified bridge.

Wraps certified V1. Current-season pass-defense evidence always wins. If the
selected regular season has no usable season sample yet, V2 uses the immediately
prior regular season as a labelled baseline and fills the recent-five window with
verified prior-season game summaries. No sportsbook data or fuzzy identity.
"""
from __future__ import annotations

import math
from typing import Any

import nfl_passing_yards_defense_v1 as base
import nfl_passing_yards_early_season_v1 as early

MODEL_VERSION = "NFL PASSING YARDS PASS DEFENSE V2 • EARLY SEASON BRIDGE"


def _num(value: Any):
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _avg(rows: list[dict], key: str):
    values = [_num(row.get(key)) for row in rows]
    values = [x for x in values if _finite(x)]
    return sum(values) / len(values) if values else math.nan


def build_pass_defense_profile(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str) -> dict:
    current = dict(base.build_pass_defense_profile(team_id, team_name, year, season_type, cutoff_date) or {})
    current_recent = list(current.get("recent_games") or [])
    source_year = int(year)
    fallback_used = False
    prior: dict = {}

    if early.allow_prior_regular_fallback(season_type) and (not current.get("ready") or len(current_recent) < 5):
        prior_year = early.prior_regular_year(year)
        prior = dict(base.build_pass_defense_profile(team_id, team_name, prior_year, 2, cutoff_date) or {})
        if not current.get("ready") and prior.get("ready"):
            current["season"] = dict(prior.get("season") or {})
            current["matchup_grade"] = prior.get("matchup_grade")
            current["grade_basis"] = f"{prior.get('grade_basis') or 'prior regular-season baseline'} • early-season fallback"
            current["ready"] = True
            current["reason"] = ""
            source_year = prior_year
            fallback_used = True

        prior_recent = list(prior.get("recent_games") or [])
        recent = early.merge_recent_rows(current_recent, prior_recent, limit=5)
        current["recent_games"] = recent
        current["recent3_yards_allowed"] = _avg(recent[:3], "passing_yards_allowed")
        current["recent5_yards_allowed"] = _avg(recent[:5], "passing_yards_allowed")
        current["recent3_completion_pct_allowed"] = _avg(recent[:3], "completion_pct_allowed")
        current["recent3_ypa_allowed"] = _avg(recent[:3], "yards_per_attempt_allowed")
        current["recent_verified_games"] = len(recent)
        current["prior_recent_games_used"] = max(0, len(recent) - len(current_recent[:5]))

    current.update(early.provenance(bool(current.get("ready") and not fallback_used), fallback_used, int(year), source_year))
    current["requested_season_year"] = int(year)
    current["sportsbook_influence"] = 0.0
    return current


# Re-export parser helpers used by tests/consumers without changing V1 contracts.
matchup_grade = base.matchup_grade
parse_recent_defense_game = base.parse_recent_defense_game
parse_season_pass_defense = base.parse_season_pass_defense

__all__ = [
    "MODEL_VERSION",
    "build_pass_defense_profile",
    "matchup_grade",
    "parse_recent_defense_game",
    "parse_season_pass_defense",
]
