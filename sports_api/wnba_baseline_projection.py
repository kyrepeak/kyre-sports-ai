"""Step 5A: WNBA opportunity/role baseline player projection.

This is the first projection layer in the WNBA pipeline. It consumes a Step 4X
readiness report with the frozen Step 4W snapshot included. A NOT_READY gate is
a hard stop.

Step 5A intentionally stays narrow:
- projects minutes, points, rebounds, assists, and PRA;
- uses observed official GameRotation minutes plus official starter/bench rates;
- does not apply matchup, pace, travel, officiating, teammate-redistribution,
  sportsbook, or Monte Carlo adjustments yet.

The projection is conditional on the player being active/available to play.
Questionable/Doubtful/Probable designations are surfaced through readiness
warnings; Step 5A does not invent an injury penalty or minutes reduction.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5A baseline projection engine"
MODEL_VERSION = "wnba_step_5a_baseline_v1"
MODEL_FAMILY = "opportunity_role_rate_baseline"
MAX_RECENT_GAMES = 20
MAX_REGULATION_MINUTES = 40.0
ROTATION_MEDIAN_WEIGHT = 0.60
ROTATION_MEAN_WEIGHT = 0.40
STAT_KEYS = ("points", "rebounds", "assists")


class WNBABaselineProjectionNotReadyError(RuntimeError):
    """Raised when Step 4X blocks projection execution."""


class WNBABaselineProjectionNotFoundError(LookupError):
    """Raised when required player/game evidence cannot be found."""


class WNBABaselineProjectionUpstreamError(RuntimeError):
    """Raised when Step 4X or required snapshot inputs are malformed."""


class WNBABaselineProjectionModelInputError(RuntimeError):
    """Raised when 5A-specific model inputs are insufficient or invalid."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RECENT_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _max_snapshot_age(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1440:
        raise ValueError("WNBA max_snapshot_age_minutes must be an integer from 1 through 1440.")
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _finite_nonnegative(value: Any, label: str) -> float:
    number = _to_float(value)
    if number is None or number < 0 or number != number or number in (float("inf"), float("-inf")):
        raise WNBABaselineProjectionModelInputError(f"Step 5A requires a valid nonnegative {label}.")
    return number


def _readiness_snapshot(readiness: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(readiness, dict):
        raise ValueError("WNBA Step 5A readiness report must be an object.")
    state = _clean(readiness.get("readiness"))
    if state == "NOT_READY" or readiness.get("can_start_projection") is False:
        blocker_ids = _dig(readiness, "summary", "blocker_ids")
        raise WNBABaselineProjectionNotReadyError(
            "Step 4X marked the player/game input package NOT_READY"
            + (f"; blockers: {', '.join(str(x) for x in blocker_ids)}" if isinstance(blocker_ids, list) and blocker_ids else "")
            + "."
        )
    if state not in {"READY", "READY_WITH_WARNINGS"} or readiness.get("can_start_projection") is not True:
        raise WNBABaselineProjectionUpstreamError(
            "Step 4X readiness report has an invalid readiness state."
        )
    snapshot = readiness.get("snapshot")
    if readiness.get("snapshot_included") is not True or not isinstance(snapshot, dict):
        raise WNBABaselineProjectionUpstreamError(
            "Step 5A requires Step 4X to include the frozen Step 4W snapshot."
        )
    reference = readiness.get("snapshot_reference")
    if not isinstance(reference, dict):
        raise WNBABaselineProjectionUpstreamError(
            "Step 4X readiness report is missing snapshot_reference."
        )
    for key in ("snapshot_id", "content_sha256", "game_id", "player_id", "recent_window_games"):
        if reference.get(key) != snapshot.get(key):
            raise WNBABaselineProjectionUpstreamError(
                f"Step 4X snapshot reference disagrees with included snapshot for {key}."
            )
    return snapshot


def _validate_identity(snapshot: dict[str, Any]) -> tuple[int, str, str, str]:
    player_id = _to_int(snapshot.get("player_id"))
    game_id = _clean(snapshot.get("game_id"))
    focal = snapshot.get("focal_identity")
    if player_id is None or player_id <= 0 or game_id is None or len(game_id) != 10 or not game_id.isdigit():
        raise WNBABaselineProjectionUpstreamError("Step 4W snapshot has invalid player/game identity.")
    if not isinstance(focal, dict):
        raise WNBABaselineProjectionUpstreamError("Step 4W snapshot is missing focal identity.")
    if _to_int(focal.get("player_id")) != player_id:
        raise WNBABaselineProjectionUpstreamError("Step 4W focal identity has the wrong player ID.")
    team_key = _clean(focal.get("team_key"))
    opponent_key = _clean(focal.get("opponent_team_key"))
    side = _clean(focal.get("side"))
    if not team_key or not opponent_key or team_key == opponent_key or side not in {"away", "home"}:
        raise WNBABaselineProjectionUpstreamError("Step 4W focal team/opponent identity is invalid.")
    return player_id, game_id, team_key, opponent_key


def _opportunity(snapshot: dict[str, Any], player_id: int, team_key: str) -> dict[str, Any]:
    opportunity = _dig(snapshot, "inputs", "player_opportunity_context")
    if not isinstance(opportunity, dict):
        raise WNBABaselineProjectionModelInputError(
            "Step 5A requires Step 4V player opportunity context."
        )
    if _to_int(opportunity.get("player_id")) != player_id:
        raise WNBABaselineProjectionUpstreamError("Step 4V opportunity context has the wrong player ID.")
    if _clean(opportunity.get("latest_observed_team_key")) != team_key:
        raise WNBABaselineProjectionUpstreamError("Step 4V opportunity context has the wrong focal team.")
    return opportunity


def _minutes_projection(opportunity: dict[str, Any]) -> dict[str, Any]:
    stability = _dig(
        opportunity,
        "observed_minutes_opportunity",
        "tracked_minutes",
        "stability",
    )
    if not isinstance(stability, dict):
        raise WNBABaselineProjectionModelInputError(
            "Step 5A requires Step 4R rotation stability inputs."
        )
    mean_minutes = _finite_nonnegative(stability.get("tracked_minutes_mean"), "recent mean minutes")
    median_minutes = _finite_nonnegative(stability.get("tracked_minutes_median"), "recent median minutes")
    stddev = _finite_nonnegative(
        stability.get("tracked_minutes_population_stddev"),
        "recent minutes population standard deviation",
    )
    minimum = _finite_nonnegative(stability.get("tracked_minutes_min"), "recent minimum minutes")
    maximum = _finite_nonnegative(stability.get("tracked_minutes_max"), "recent maximum minutes")
    game_count = _to_int(stability.get("rotation_game_count"))
    if game_count is None or game_count <= 0:
        raise WNBABaselineProjectionModelInputError("Step 5A requires at least one observed rotation game.")
    if minimum > maximum:
        raise WNBABaselineProjectionUpstreamError("Step 4R rotation minimum minutes exceeds maximum minutes.")

    raw = ROTATION_MEDIAN_WEIGHT * median_minutes + ROTATION_MEAN_WEIGHT * mean_minutes
    projected = min(MAX_REGULATION_MINUTES, max(0.0, raw))
    low = min(projected, max(0.0, projected - stddev))
    high = max(projected, min(MAX_REGULATION_MINUTES, projected + stddev))
    return {
        "expected_minutes": round(projected, 4),
        "raw_weighted_minutes_before_regulation_cap": round(raw, 4),
        "sensitivity_low_minutes": round(low, 4),
        "sensitivity_high_minutes": round(high, 4),
        "recent_mean_minutes": round(mean_minutes, 4),
        "recent_median_minutes": round(median_minutes, 4),
        "recent_min_minutes": round(minimum, 4),
        "recent_max_minutes": round(maximum, 4),
        "recent_minutes_population_stddev": round(stddev, 4),
        "rotation_game_count": game_count,
        "weights": {
            "median": ROTATION_MEDIAN_WEIGHT,
            "mean": ROTATION_MEAN_WEIGHT,
        },
        "cap_minutes": MAX_REGULATION_MINUTES,
        "semantics": (
            "Expected minutes are a transparent Step-5A baseline from observed official GameRotation history. "
            "They are not injury-adjusted, lineup-redistributed, matchup-adjusted, or overtime-adjusted."
        ),
    }


def _role_row_rate(
    row: dict[str, Any] | None,
    stat_key: str,
    expected_team_key: str,
) -> dict[str, Any] | None:
    if row is None:
        return None
    if not isinstance(row, dict):
        raise WNBABaselineProjectionUpstreamError("Step 4V role split row is malformed.")
    team_key = _clean(row.get("team_key"))
    if team_key is not None and team_key != expected_team_key:
        raise WNBABaselineProjectionUpstreamError("Step 4V role split row has conflicting team identity.")
    games = _to_int(row.get("games_played"))
    stats = row.get("stats")
    if games is None or games <= 0 or not isinstance(stats, dict):
        return None
    minutes = _finite_nonnegative(stats.get("minutes"), f"{row.get('role')} role minutes")
    stat = _finite_nonnegative(stats.get(stat_key), f"{row.get('role')} role {stat_key}")
    if minutes <= 0:
        return None
    return {
        "role": _clean(row.get("role")),
        "games_played": games,
        "minutes_per_game": round(minutes, 6),
        "stat_per_game": round(stat, 6),
        "stat_per_minute": round(stat / minutes, 8),
    }


def _role_rates(opportunity: dict[str, Any], expected_team_key: str) -> dict[str, Any]:
    context = opportunity.get("observed_role_context")
    if not isinstance(context, dict) or context.get("available") is not True:
        raise WNBABaselineProjectionModelInputError(
            "Step 5A requires official starter/bench role context from Step 4G."
        )
    summary = context.get("role_summary")
    if not isinstance(summary, dict):
        raise WNBABaselineProjectionModelInputError("Step 5A role context is missing role_summary.")
    start_share = _to_float(summary.get("starter_game_share"))
    if start_share is not None and not 0.0 <= start_share <= 1.0:
        raise WNBABaselineProjectionUpstreamError("Step 4G starter_game_share is outside 0..1.")

    result: dict[str, Any] = {
        "starter_game_share": start_share,
        "primary_observed_role": summary.get("primary_observed_role"),
        "observed_role_band": context.get("observed_role_band"),
        "stats": {},
    }
    for stat_key in STAT_KEYS:
        starter = _role_row_rate(context.get("starter"), stat_key, expected_team_key)
        bench = _role_row_rate(context.get("bench"), stat_key, expected_team_key)
        if starter is not None and bench is not None:
            if start_share is None:
                raise WNBABaselineProjectionModelInputError(
                    "Step 5A cannot blend starter/bench rates without starter_game_share."
                )
            rate = start_share * starter["stat_per_minute"] + (1.0 - start_share) * bench["stat_per_minute"]
            method = "starter_bench_rate_blend_by_observed_start_share"
            weights = {"starter": round(start_share, 6), "bench": round(1.0 - start_share, 6)}
        elif starter is not None:
            rate = starter["stat_per_minute"]
            method = "starter_rate_only_available_role_split"
            weights = {"starter": 1.0, "bench": 0.0}
        elif bench is not None:
            rate = bench["stat_per_minute"]
            method = "bench_rate_only_available_role_split"
            weights = {"starter": 0.0, "bench": 1.0}
        else:
            raise WNBABaselineProjectionModelInputError(
                f"Step 5A has no valid official role rate for {stat_key}."
            )
        result["stats"][stat_key] = {
            "rate_per_minute": round(rate, 8),
            "method": method,
            "weights": weights,
            "starter_source": starter,
            "bench_source": bench,
        }
    return result


def _stat_projection(rate: float, minutes: dict[str, Any]) -> dict[str, Any]:
    expected = rate * minutes["expected_minutes"]
    low = rate * minutes["sensitivity_low_minutes"]
    high = rate * minutes["sensitivity_high_minutes"]
    return {
        "expected": round(expected, 4),
        "rate_per_minute": round(rate, 8),
        "minutes_sensitivity_low": round(low, 4),
        "minutes_sensitivity_high": round(high, 4),
        "sensitivity_semantics": (
            "Low/high values vary only the Step-5A minutes input by one observed population standard deviation. "
            "They are not confidence intervals or probability bounds."
        ),
    }


def _event_quality_diagnostics(opportunity: dict[str, Any]) -> dict[str, Any]:
    event = opportunity.get("observed_event_opportunity")
    if not isinstance(event, dict):
        return {"available": False}
    return {
        "available": True,
        "feature_game_count": event.get("feature_game_count"),
        "missing_feature_game_ids": deepcopy(event.get("missing_feature_game_ids")),
        "data_quality": deepcopy(event.get("data_quality")),
        "own_event_counts_per_feature_game": deepcopy(event.get("own_event_counts_per_feature_game")),
        "usage_in_step_5a": (
            "diagnostic_only; Step 5A does not scale feature-eligible event counts into full-game box-score totals"
        ),
    }


def _availability_condition(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw = _dig(snapshot, "inputs", "game_availability")
    focal = snapshot.get("focal_identity")
    player_id = _to_int(snapshot.get("player_id"))
    if not isinstance(raw, dict) or not isinstance(focal, dict):
        return {
            "availability_captured": False,
            "conditional_on_player_active": True,
            "focal_player_status": None,
        }
    side = focal.get("side")
    team = raw.get(side) if side in {"away", "home"} else None
    players = team.get("players") if isinstance(team, dict) else None
    row = next(
        (
            item for item in players
            if isinstance(item, dict) and _to_int(item.get("player_id")) == player_id
        ),
        None,
    ) if isinstance(players, list) else None
    return {
        "availability_captured": True,
        "conditional_on_player_active": True,
        "focal_player_status": deepcopy(row),
        "automatic_injury_minutes_penalty_applied": False,
        "automatic_teammate_opportunity_redistribution_applied": False,
    }


def project_from_readiness_report(readiness: dict[str, Any]) -> dict[str, Any]:
    snapshot = _readiness_snapshot(readiness)
    player_id, game_id, team_key, opponent_key = _validate_identity(snapshot)
    opportunity = _opportunity(snapshot, player_id, team_key)
    minutes = _minutes_projection(opportunity)
    role = _role_rates(opportunity, team_key)

    stats = {
        key: _stat_projection(role["stats"][key]["rate_per_minute"], minutes)
        for key in STAT_KEYS
    }
    pra_expected = sum(stats[key]["expected"] for key in STAT_KEYS)
    pra_low = sum(stats[key]["minutes_sensitivity_low"] for key in STAT_KEYS)
    pra_high = sum(stats[key]["minutes_sensitivity_high"] for key in STAT_KEYS)
    stats["pra"] = {
        "expected": round(pra_expected, 4),
        "minutes_sensitivity_low": round(pra_low, 4),
        "minutes_sensitivity_high": round(pra_high, 4),
        "composition": "points + rebounds + assists",
        "sensitivity_semantics": "Component low/high values share the same minutes-only sensitivity scenario.",
    }

    model_config = {
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "rotation_median_weight": ROTATION_MEDIAN_WEIGHT,
        "rotation_mean_weight": ROTATION_MEAN_WEIGHT,
        "max_regulation_minutes": MAX_REGULATION_MINUTES,
        "role_rate_method": "official starter/bench per-minute rate blended by observed starter-game share",
        "matchup_adjustment": False,
        "pace_adjustment": False,
        "travel_adjustment": False,
        "officiating_adjustment": False,
        "injury_minutes_penalty": False,
        "teammate_opportunity_redistribution": False,
    }
    fingerprint_payload = {
        "snapshot_content_sha256": snapshot.get("content_sha256"),
        "readiness": readiness.get("readiness"),
        "model_config": model_config,
        "minutes": minutes,
        "role_rates": role,
    }
    projection_hash = _canonical_hash(fingerprint_payload)
    warning_ids = _dig(readiness, "summary", "warning_ids")
    if not isinstance(warning_ids, list):
        warning_ids = []

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_independent_baseline_player_stat_projection",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "projection_id": f"wnba-5a-{game_id}-{player_id}-{projection_hash[:16]}",
        "projection_fingerprint_sha256": projection_hash,
        "season": snapshot.get("season"),
        "season_type": snapshot.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "side": _dig(snapshot, "focal_identity", "side"),
        "readiness": {
            "state": readiness.get("readiness"),
            "can_start_projection": True,
            "diagnostic_data_quality_score": readiness.get("diagnostic_data_quality_score"),
            "warning_ids": deepcopy(warning_ids),
            "blocker_ids": [],
            "projection_allowed_with_warnings": readiness.get("readiness") == "READY_WITH_WARNINGS",
        },
        "snapshot_reference": deepcopy(readiness.get("snapshot_reference")),
        "game_identity": deepcopy(snapshot.get("game_identity")),
        "availability_condition": _availability_condition(snapshot),
        "model_inputs": {
            "minutes": minutes,
            "role_rates": role,
            "event_quality_diagnostics": _event_quality_diagnostics(opportunity),
        },
        "projection": {
            "minutes": {
                "expected": minutes["expected_minutes"],
                "sensitivity_low": minutes["sensitivity_low_minutes"],
                "sensitivity_high": minutes["sensitivity_high_minutes"],
            },
            **stats,
        },
        "model_config": model_config,
        "projection_semantics": {
            "conditional_on_player_active": True,
            "independent_of_sportsbook_market": True,
            "baseline_before_matchup_adjustments": True,
            "minutes_sensitivity_is_not_probability_interval": True,
            "pra_is_sum_of_component_expectations": True,
        },
        "guardrails": {
            "step_4x_not_ready_blocks_projection": True,
            "step_4w_snapshot_reference_must_match_included_snapshot": True,
            "official_gamerotation_drives_minutes_baseline": True,
            "official_starter_bench_rates_drive_stat_baseline": True,
            "step_4u_event_counts_are_diagnostic_not_treated_as_complete_box_score": True,
            "no_matchup_adjustment_created": True,
            "no_pace_adjustment_created": True,
            "no_travel_adjustment_created": True,
            "no_officiating_adjustment_created": True,
            "no_injury_minutes_penalty_created": True,
            "no_missing_teammate_opportunity_redistribution_created": True,
            "no_sportsbook_data_used": True,
            "no_betting_probability_created": True,
            "no_monte_carlo_created": True,
            "no_defender_assignment_inferred": True,
        },
        "verification": {
            "projection_started_only_after_step_4x_gate": True,
            "snapshot_player_game_identity_checked": True,
            "step_4v_player_team_identity_checked": True,
            "minutes_model_parameters_versioned": True,
            "role_rate_sources_exposed": True,
            "projection_fingerprint_created": True,
        },
    }


def get_player_game_baseline_projection(
    player_id: int,
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    require_current_availability = _bool(require_current_availability, "require_current_availability")
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)
    try:
        readiness = get_player_game_model_input_readiness(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            require_current_availability=require_current_availability,
            include_shot_context=False,
            include_advanced_context=False,
            include_officiating_context=False,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            include_snapshot=True,
        )
    except WNBAModelInputReadinessNotFoundError as exc:
        raise WNBABaselineProjectionNotFoundError(str(exc)) from exc
    except WNBAModelInputReadinessUpstreamError as exc:
        raise WNBABaselineProjectionUpstreamError(str(exc)) from exc
    return project_from_readiness_report(readiness)
