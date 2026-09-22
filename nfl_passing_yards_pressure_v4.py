"""NFL Passing Yards pressure V4 — bounded exact-ID early-season rescue.

Additive replacement for the active V3 Step 4 builder. V4 preserves V3's
UTC-safe ESPN completed-game selection and the certified V1 pressure math, but
tightens when prior-season evidence is allowed to enter Step 4:

* current-season verified pressure/protection evidence always wins;
* the existing five-game recent window is the only early-season window;
* prior evidence is requested only for regular-season analysis while that
  existing window is incomplete;
* a prior baseline can rescue an incomplete current baseline only when both
  returned ESPN team IDs exactly equal the requested IDs;
* explicit prior season-type metadata, when present, must identify the regular
  season;
* outside that existing window, an incomplete current profile stays fail-closed.

No fuzzy/name matching, synthetic identity, projection math, probability, market,
or sportsbook behavior is introduced. Projection adjustment remains 0.0 and
sportsbook influence remains 0.0%.
"""
from __future__ import annotations

import math
from typing import Any

import nfl_passing_yards_early_season_v1 as early
import nfl_passing_yards_pressure_v1 as base
import nfl_passing_yards_pressure_v3 as utc_bridge

MODEL_VERSION = "NFL PASSING YARDS PRESSURE V4 • BOUNDED EXACT-ID EARLY-SEASON RESCUE"
FROZEN_PRIOR = "nfl_passing_yards_pressure_v3"

# This is not a new threshold. V2 already used the certified recent-five window
# (`len(... ) < 5`) when deciding whether prior-season context could be loaded.
FROZEN_RECENT_WINDOW = 5


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


def _within_existing_early_window(off_recent: list[dict], def_recent: list[dict]) -> bool:
    """Reuse V2's certified recent-five opening-season window exactly."""
    return len(off_recent) < FROZEN_RECENT_WINDOW or len(def_recent) < FROZEN_RECENT_WINDOW


def _metadata_says_regular_season(row: dict) -> bool:
    """Fail closed only when explicit season-type metadata contradicts regular."""
    if not isinstance(row, dict):
        return False

    id_fields = ("season_type", "seasonType", "season_type_id", "seasonTypeId")
    label_fields = ("season_type_name", "seasonTypeName", "season_label", "seasonLabel")

    for key in id_fields:
        if key not in row or row.get(key) in (None, ""):
            continue
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get("id") or value.get("type") or value.get("name") or value.get("displayName")
        text = _safe(value).lower()
        try:
            if int(float(text)) != 2:
                return False
            continue
        except Exception:
            pass
        if "regular" not in text:
            return False

    for key in label_fields:
        if key not in row or row.get(key) in (None, ""):
            continue
        if "regular" not in _safe(row.get(key)).lower():
            return False

    # No explicit metadata is acceptable because this module itself requests
    # ESPN season type 2. Explicit contradictory metadata is never acceptable.
    return True


def _prior_identity_is_exact_regular(
    prior: dict,
    offense_team_id: str,
    defense_team_id: str,
) -> bool:
    if not isinstance(prior, dict):
        return False
    return bool(
        _safe(prior.get("offense_team_id")) == _safe(offense_team_id)
        and _safe(prior.get("defense_team_id")) == _safe(defense_team_id)
        and _metadata_says_regular_season(prior)
    )


def _build_utc_base(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    return dict(
        utc_bridge._with_utc_defense(
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


def build_pressure_matchup(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    current = _build_utc_base(
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
    prior: dict = {}

    in_early_window = (
        early.allow_prior_regular_fallback(season_type)
        and _within_existing_early_window(current_off_recent, current_def_recent)
    )

    if in_early_window:
        prior_year = early.prior_regular_year(year)
        candidate = _build_utc_base(
            offense_team_id,
            offense_team_name,
            defense_team_id,
            defense_team_name,
            prior_year,
            2,
            cutoff_date,
        )
        if _prior_identity_is_exact_regular(candidate, offense_team_id, defense_team_id):
            prior = candidate

            if not current.get("ready") and prior.get("ready"):
                for key in ("offense", "defense", "pressure_label", "pressure_basis", "blitz_state"):
                    if key in prior:
                        current[key] = prior[key]
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
                list(prior.get("recent_offense") or []),
                limit=FROZEN_RECENT_WINDOW,
            )
            def_recent = early.merge_recent_rows(
                current_def_recent,
                list(prior.get("recent_defense") or []),
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
