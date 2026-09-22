"""NFL Passing Yards pressure V5 — live ESPN source-shape recovery.

Additive successor to certified V4. V5 fixes the two live ESPN source-shape gaps
visible on the Sep. 13, 2026 Tampa Bay @ Cincinnati production slate:

1) ESPN game-summary box scores can expose composite sack stats with a placeholder
   primary ``value`` and the usable ``displayValue``. V5 reuses the already-
   certified V3 display-value fallback for Step 4 recent sack rows.
2) ESPN team all-splits statistics expose defensive sack totals but do not expose
   opponent pass attempts for the 2025 regular season. When that exact shape is
   encountered, V5 reuses the certified exact-event box-score season aggregate
   from pass-defense V3 to recover opponent pass attempts, then combines those
   attempts with the verified ESPN defensive sack total to compute sack rate.

Current-season evidence still wins. V4's exact-ID, regular-season-only, bounded
recent-five early-season gate is preserved. No fuzzy/name identity authority,
synthetic IDs, estimates, sportsbook projection input, projection math, or stake
sizing is introduced. Sportsbook influence remains exactly 0.0%.
"""
from __future__ import annotations

import math
from typing import Any

import nfl_passing_yards_defense_v3 as defense_v3
import nfl_passing_yards_early_season_v1 as early
import nfl_passing_yards_pressure_v1 as base
import nfl_passing_yards_pressure_v4 as prior

MODEL_VERSION = "NFL PASSING YARDS PRESSURE V5 • LIVE ESPN SOURCE-SHAPE RECOVERY"
FROZEN_PRIOR = "nfl_passing_yards_pressure_v4"
FROZEN_RECENT_WINDOW = prior.FROZEN_RECENT_WINDOW


def _safe(value: Any) -> str:
    return str(value if value is not None else "").strip()


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
    values = [value for value in values if _finite(value)]
    return sum(values) / len(values) if values else math.nan


class _LiveDefenseProxy:
    """Forward V1 defense reads except the two already-certified source parsers."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "_completed_event_rows":
            return defense_v3._completed_event_rows_utc
        if name == "_box_stat":
            return defense_v3._box_stat_v3
        return getattr(self._wrapped, name)


def _with_live_defense(func, *args, **kwargs):
    original = base.defense
    base.defense = _LiveDefenseProxy(original)
    try:
        return func(*args, **kwargs)
    finally:
        base.defense = original


def _recover_defensive_pressure(
    row: dict,
    defense_team_id: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    """Recover only missing opponent attempts from exact verified ESPN events."""
    pressure = dict(row.get("defense") or {})
    if pressure.get("ready"):
        return row

    games = _num(pressure.get("games"))
    sacks = _num(pressure.get("sacks_made"))
    attempts = _num(pressure.get("opponent_pass_attempts"))
    if not (
        int(season_type) == 2
        and _finite(games)
        and games > 0
        and _finite(sacks)
        and sacks >= 0
        and not (_finite(attempts) and attempts > 0)
    ):
        return row

    recovered, _, diag = defense_v3._verified_boxscore_season(
        _safe(defense_team_id),
        int(year),
        int(season_type),
        cutoff_date,
        partial_season={"sacks": sacks},
    )
    row["pressure_aggregate_diag"] = dict(diag or {})
    recovered_attempts = _num((recovered or {}).get("passing_attempts_allowed"))
    recovered_games = _num((recovered or {}).get("games"))
    if not (
        (recovered or {}).get("ready")
        and _finite(recovered_attempts)
        and recovered_attempts > 0
        and _finite(recovered_games)
        and recovered_games > 0
    ):
        return row

    pressure_dropbacks = recovered_attempts + sacks
    pressure.update(
        {
            "ready": True,
            "games": recovered_games,
            "sacks_made": sacks,
            "sacks_per_game": sacks / recovered_games,
            "opponent_pass_attempts": recovered_attempts,
            "pressure_dropbacks": pressure_dropbacks,
            "sack_rate_generated": (100.0 * sacks / pressure_dropbacks) if pressure_dropbacks > 0 else math.nan,
            "source": "ESPN TEAM SACKS + VERIFIED ESPN EVENT BOXSCORE ATTEMPTS",
        }
    )
    row["defense"] = pressure
    label, basis = base.pressure_label(dict(row.get("offense") or {}), pressure)
    row["pressure_label"] = label
    row["pressure_basis"] = basis
    row["ready"] = bool((row.get("offense") or {}).get("ready") and pressure.get("ready"))
    row["reason"] = "" if row["ready"] else "verified season pass-protection or defensive sack evidence is incomplete"
    row["pressure_source_recovery"] = "verified ESPN opponent attempts from exact regular-season event box scores"
    return row


def _build_live_base(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    row = dict(
        _with_live_defense(
            base.build_pressure_matchup,
            offense_team_id,
            offense_team_name,
            defense_team_id,
            defense_team_name,
            year,
            season_type,
            cutoff_date,
        )
        or {}
    )
    row = _recover_defensive_pressure(
        row,
        defense_team_id,
        year,
        season_type,
        cutoff_date,
    )
    row["season_type"] = int(season_type)
    row["source_year"] = int(year)
    row["timezone_normalization"] = "UTC"
    row["boxscore_value_fallback"] = "ESPN DISPLAY VALUE FOR PLACEHOLDER PRIMARY VALUES"
    row["projection_adjustment"] = 0.0
    row["sportsbook_influence"] = 0.0
    return row


def build_pressure_matchup(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    current = _build_live_base(
        offense_team_id,
        offense_team_name,
        defense_team_id,
        defense_team_name,
        year,
        season_type,
        cutoff_date,
    )
    current_off_recent = list(current.get("recent_offense") or [])
    current_def_recent = list(current.get("recent_defense") or [])
    off_recent = list(current_off_recent)
    def_recent = list(current_def_recent)

    source_year = int(year)
    fallback_used = False
    prior_row: dict = {}

    in_early_window = (
        early.allow_prior_regular_fallback(season_type)
        and prior._within_existing_early_window(current_off_recent, current_def_recent)
    )

    if in_early_window:
        prior_year = early.prior_regular_year(year)
        candidate = _build_live_base(
            offense_team_id,
            offense_team_name,
            defense_team_id,
            defense_team_name,
            prior_year,
            2,
            cutoff_date,
        )
        if prior._prior_identity_is_exact_regular(candidate, offense_team_id, defense_team_id):
            prior_row = candidate

            if not current.get("ready") and prior_row.get("ready"):
                for key in (
                    "offense",
                    "defense",
                    "pressure_label",
                    "pressure_basis",
                    "blitz_state",
                    "pressure_aggregate_diag",
                    "pressure_source_recovery",
                    "boxscore_value_fallback",
                ):
                    if key in prior_row:
                        current[key] = prior_row[key]
                current["pressure_basis"] = (
                    f"{current.get('pressure_basis') or 'prior regular-season baseline'}"
                    " • early-season fallback"
                )
                current["ready"] = True
                current["reason"] = ""
                source_year = prior_year
                fallback_used = True

            off_recent = early.merge_recent_rows(
                current_off_recent,
                list(prior_row.get("recent_offense") or []),
                limit=FROZEN_RECENT_WINDOW,
            )
            def_recent = early.merge_recent_rows(
                current_def_recent,
                list(prior_row.get("recent_defense") or []),
                limit=FROZEN_RECENT_WINDOW,
            )
            current["recent_offense"] = off_recent
            current["recent_defense"] = def_recent
            current["recent3_sacks_allowed"] = _avg(off_recent[:3], "sacks_taken")
            current["recent5_sacks_allowed"] = _avg(off_recent[:5], "sacks_taken")
            current["recent3_sack_rate_allowed"] = _avg(off_recent[:3], "sack_rate")
            current["recent3_sacks_made"] = _avg(def_recent[:3], "sacks_made")
            current["recent5_sacks_made"] = _avg(def_recent[:5], "sacks_made")
            current["recent3_sack_rate_generated"] = _avg(def_recent[:3], "sack_rate_generated")
            current["prior_recent_offense_games_used"] = max(
                0,
                len(off_recent) - min(len(current_off_recent), FROZEN_RECENT_WINDOW),
            )
            current["prior_recent_defense_games_used"] = max(
                0,
                len(def_recent) - min(len(current_def_recent), FROZEN_RECENT_WINDOW),
            )

    current.update(
        early.provenance(
            bool(current.get("ready") and not fallback_used),
            fallback_used,
            int(year),
            source_year,
        )
    )
    current["requested_season_year"] = int(year)
    current["timezone_normalization"] = "UTC"
    current["projection_adjustment"] = 0.0
    current["sportsbook_influence"] = 0.0
    return current


parse_defensive_pressure = base.parse_defensive_pressure
parse_offense_protection = base.parse_offense_protection
parse_recent_sacks_made = base.parse_recent_sacks_made
parse_recent_sacks_taken = base.parse_recent_sacks_taken
pressure_label = base.pressure_label

__all__ = [
    "FROZEN_PRIOR",
    "FROZEN_RECENT_WINDOW",
    "MODEL_VERSION",
    "build_pressure_matchup",
    "parse_defensive_pressure",
    "parse_offense_protection",
    "parse_recent_sacks_made",
    "parse_recent_sacks_taken",
    "pressure_label",
]
