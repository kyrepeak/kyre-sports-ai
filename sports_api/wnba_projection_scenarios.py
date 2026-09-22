"""Step 5C: deterministic WNBA projection scenario and uncertainty envelope.

Consumes the exact Step 4X readiness report used by frozen Step 5B. Step 5C
never shifts the Step 5B central projection. LOW/HIGH are deterministic stress
scenarios built from observed minutes sensitivity plus explicitly versioned
availability/context uncertainty. They are not empirical standard deviations,
confidence intervals, probabilities, Monte Carlo quantiles, or betting edges.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_matchup_adjusted_projection import (
    MODEL_VERSION as MATCHUP_MODEL_VERSION,
    WNBAMatchupAdjustedProjectionModelInputError,
    WNBAMatchupAdjustedProjectionNotReadyError,
    WNBAMatchupAdjustedProjectionUpstreamError,
    project_matchup_adjusted_from_readiness,
)
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5C projection scenario engine"
MODEL_VERSION = "wnba_step_5c_scenarios_v1"
MODEL_FAMILY = "deterministic_projection_scenario_envelope"
MAX_RECENT_GAMES = 20
STAT_KEYS = ("points", "rebounds", "assists")

FOCAL_STATUS_LOW_MINUTES_STRESS = {
    "probable": 0.025,
    "questionable": 0.075,
    "doubtful": 0.150,
}
GENERIC_UNCERTAIN_LOW_MINUTES_STRESS = 0.050
MAX_AVAILABILITY_LOW_MINUTES_STRESS = 0.150
PARTIAL_MATCHUP_CONTEXT_SPREAD = 0.020
LINEUP_BLOCKING_SPREAD_PER_FULL_SHARE = 0.030
LINEUP_UNCERTAIN_SPREAD_PER_FULL_SHARE = 0.015
MAX_LINEUP_CONTEXT_SPREAD = 0.040
SHOT_ZONE_UNAVAILABLE_POINTS_SPREAD = 0.015
SHOT_ZONE_LOW_SAMPLE_POINTS_SPREAD = 0.010
MAX_CONTEXT_SPREAD_PER_STAT = 0.080
TIGHT_SCENARIO_HALF_WIDTH = 0.10
MODERATE_SCENARIO_HALF_WIDTH = 0.20


class WNBAProjectionScenarioNotReadyError(RuntimeError):
    pass


class WNBAProjectionScenarioNotFoundError(LookupError):
    pass


class WNBAProjectionScenarioUpstreamError(RuntimeError):
    pass


class WNBAProjectionScenarioModelInputError(RuntimeError):
    pass


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
        number = float(text)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


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
    resolved = lookup.get(str(value).strip().casefold())
    if resolved is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return resolved


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _max_snapshot_age(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1440:
        raise ValueError("WNBA max_snapshot_age_minutes must be an integer from 1 through 1440.")
    return value


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _readiness_snapshot(readiness: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(readiness, dict):
        raise ValueError("WNBA Step 5C readiness report must be an object.")
    state = _clean(readiness.get("readiness"))
    if state == "NOT_READY" or readiness.get("can_start_projection") is False:
        blockers = _dig(readiness, "summary", "blocker_ids")
        detail = ", ".join(str(item) for item in blockers) if isinstance(blockers, list) else ""
        raise WNBAProjectionScenarioNotReadyError(
            "Step 4X marked the player/game input package NOT_READY"
            + (f"; blockers: {detail}" if detail else "")
            + "."
        )
    if state not in {"READY", "READY_WITH_WARNINGS"} or readiness.get("can_start_projection") is not True:
        raise WNBAProjectionScenarioUpstreamError("Step 4X readiness state is invalid.")
    snapshot = readiness.get("snapshot")
    reference = readiness.get("snapshot_reference")
    if readiness.get("snapshot_included") is not True or not isinstance(snapshot, dict):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5C requires Step 4X to include the frozen Step 4W snapshot."
        )
    if not isinstance(reference, dict):
        raise WNBAProjectionScenarioUpstreamError("Step 4X snapshot reference is missing.")
    for key in ("snapshot_id", "content_sha256", "game_id", "player_id", "recent_window_games"):
        if reference.get(key) != snapshot.get(key):
            raise WNBAProjectionScenarioUpstreamError(
                f"Step 4X snapshot reference disagrees with included snapshot for {key}."
            )
    return snapshot


def _focal_availability(snapshot: dict[str, Any], player_id: int, side: str) -> dict[str, Any] | None:
    raw = _dig(snapshot, "inputs", "game_availability")
    if not isinstance(raw, dict):
        return None
    team = raw.get(side)
    players = team.get("players") if isinstance(team, dict) else None
    if not isinstance(players, list):
        return None
    rows = [
        row for row in players
        if isinstance(row, dict) and _to_int(row.get("player_id")) == player_id
    ]
    if len(rows) > 1:
        raise WNBAProjectionScenarioUpstreamError(
            "Step 4W hash-covered availability contains duplicate focal-player rows."
        )
    return rows[0] if rows else None


def _availability_low_minutes_stress(focal_row: dict[str, Any] | None) -> dict[str, Any]:
    if focal_row is None:
        return {
            "available": False,
            "status": None,
            "low_minutes_stress_pct": 0.0,
            "reason": "focal_availability_row_unavailable",
        }
    status = (_clean(focal_row.get("injury_report_status")) or "").casefold()
    availability_class = (_clean(focal_row.get("availability_class")) or "").casefold()
    blocking = (
        focal_row.get("availability_blocking") is True
        or status == "out"
        or availability_class == "unavailable"
    )
    if blocking:
        raise WNBAProjectionScenarioNotReadyError(
            "Step 5C received a focal player marked unavailable/Out after the Step 4X gate."
        )
    uncertain = (
        focal_row.get("availability_uncertain") is True
        or status in {"questionable", "doubtful", "probable"}
        or availability_class in {"uncertain", "probable"}
    )
    stress = FOCAL_STATUS_LOW_MINUTES_STRESS.get(status, 0.0)
    if uncertain and stress == 0.0:
        stress = GENERIC_UNCERTAIN_LOW_MINUTES_STRESS
    stress = _clamp(stress, 0.0, MAX_AVAILABILITY_LOW_MINUTES_STRESS)
    return {
        "available": True,
        "status": _clean(focal_row.get("injury_report_status")),
        "availability_class": _clean(focal_row.get("availability_class")),
        "availability_uncertain": uncertain,
        "low_minutes_stress_pct": round(stress, 8),
        "scenario_only": True,
        "central_projection_penalty_applied": False,
        "semantics": (
            "Availability stress affects only deterministic LOW. It is not an injury "
            "probability and does not change the Step-5B central mean."
        ),
    }


def _adjustments(matchup: dict[str, Any]) -> dict[str, Any]:
    value = matchup.get("adjustments")
    if not isinstance(value, dict):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B projection is missing its adjustment object."
        )
    return value


def _lineup_context_spread(matchup: dict[str, Any]) -> dict[str, Any]:
    adjustments = _adjustments(matchup)
    lineup = adjustments.get("lineup_continuity")
    if not isinstance(lineup, dict):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B projection is missing lineup_continuity evidence."
        )
    if lineup.get("available") is not True:
        return {
            "available": False,
            "spread_pct": 0.0,
            "blocking_share": None,
            "uncertain_share": None,
            "reason": "lineup_continuity_unavailable",
        }
    blocking = _to_float(lineup.get("blocking_lineup_share_of_returned_minutes"))
    uncertain = _to_float(lineup.get("uncertain_lineup_share_of_returned_minutes"))
    for label, value in (("blocking", blocking), ("uncertain", uncertain)):
        if value is not None and not 0.0 <= value <= 1.0:
            raise WNBAProjectionScenarioUpstreamError(
                f"Step 5B lineup {label} share is outside 0..1."
            )
    blocking = blocking or 0.0
    uncertain = uncertain or 0.0
    raw = (
        LINEUP_BLOCKING_SPREAD_PER_FULL_SHARE * blocking
        + LINEUP_UNCERTAIN_SPREAD_PER_FULL_SHARE * uncertain
    )
    spread = _clamp(raw, 0.0, MAX_LINEUP_CONTEXT_SPREAD)
    return {
        "available": True,
        "blocking_share": round(blocking, 8),
        "uncertain_share": round(uncertain, 8),
        "raw_spread_pct": round(raw, 8),
        "spread_pct": round(spread, 8),
        "cap": MAX_LINEUP_CONTEXT_SPREAD,
        "central_projection_adjustment_applied": False,
        "semantics": (
            "Observed lineup disruption widens LOW/HIGH symmetrically without "
            "inferring how missing teammate opportunity redistributes."
        ),
    }


def _context_spreads(matchup: dict[str, Any]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    context = matchup.get("adjustment_context")
    if not isinstance(context, dict):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B projection is missing adjustment_context."
        )
    context_level = _clean(context.get("context_level"))
    if context_level not in {"full", "partial"}:
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B adjustment context level is invalid."
        )
    spreads = {key: 0.0 for key in STAT_KEYS}
    receipts: list[dict[str, Any]] = []
    if context_level == "partial":
        for key in STAT_KEYS:
            spreads[key] += PARTIAL_MATCHUP_CONTEXT_SPREAD
        receipts.append({
            "source": "partial_matchup_context",
            "applies_to": list(STAT_KEYS),
            "spread_pct": PARTIAL_MATCHUP_CONTEXT_SPREAD,
            "reason": "One or more requested Step-5B matchup components were unavailable.",
        })

    lineup = _lineup_context_spread(matchup)
    lineup_spread = _to_float(lineup.get("spread_pct")) or 0.0
    if lineup_spread > 0:
        for key in STAT_KEYS:
            spreads[key] += lineup_spread
        receipts.append({
            "source": "lineup_continuity",
            "applies_to": list(STAT_KEYS),
            "spread_pct": round(lineup_spread, 8),
            "evidence": lineup,
        })

    shot = _adjustments(matchup).get("shot_zone_fit")
    if not isinstance(shot, dict):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B projection is missing shot_zone_fit evidence."
        )
    shot_spread = 0.0
    shot_reason = None
    if shot.get("available") is False:
        shot_spread = SHOT_ZONE_UNAVAILABLE_POINTS_SPREAD
        shot_reason = "shot_zone_context_unavailable"
    elif shot.get("available") is True and shot.get("applied") is not True:
        shot_spread = SHOT_ZONE_LOW_SAMPLE_POINTS_SPREAD
        shot_reason = _clean(shot.get("reason")) or "shot_zone_adjustment_not_applied"
    if shot_spread > 0:
        spreads["points"] += shot_spread
        receipts.append({
            "source": "shot_zone_coverage",
            "applies_to": ["points"],
            "spread_pct": shot_spread,
            "reason": shot_reason,
        })

    for key in STAT_KEYS:
        spreads[key] = round(
            _clamp(spreads[key], 0.0, MAX_CONTEXT_SPREAD_PER_STAT), 8
        )
    return spreads, receipts


def _required_projection_value(projection: dict[str, Any], stat: str, key: str) -> float:
    row = projection.get(stat)
    if not isinstance(row, dict):
        raise WNBAProjectionScenarioUpstreamError(
            f"Step 5B projection is missing {stat}."
        )
    value = _to_float(row.get(key))
    if value is None or value < 0:
        raise WNBAProjectionScenarioUpstreamError(
            f"Step 5B projection has invalid {stat}.{key}."
        )
    return value


def _scenario_breadth(low: float, base: float, high: float) -> dict[str, Any]:
    if not low <= base <= high:
        raise WNBAProjectionScenarioUpstreamError("Step 5C scenario ordering is invalid.")
    if base > 0:
        downside = (base - low) / base
        upside = (high - base) / base
        half_width = max(downside, upside)
    else:
        downside = 0.0 if low == 0 else None
        upside = 0.0 if high == 0 else None
        half_width = 0.0 if low == high == 0 else None
    if half_width is None:
        tier = "UNRESOLVED"
    elif half_width <= TIGHT_SCENARIO_HALF_WIDTH:
        tier = "TIGHT"
    elif half_width <= MODERATE_SCENARIO_HALF_WIDTH:
        tier = "MODERATE"
    else:
        tier = "WIDE"
    return {
        "low": round(low, 4),
        "base": round(base, 4),
        "high": round(high, 4),
        "downside_from_base_pct": round(downside, 8) if downside is not None else None,
        "upside_from_base_pct": round(upside, 8) if upside is not None else None,
        "full_width": round(high - low, 4),
        "max_relative_half_width": round(half_width, 8) if half_width is not None else None,
        "breadth_tier": tier,
    }


def build_projection_scenarios(matchup: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    snapshot = _readiness_snapshot(readiness)
    if not isinstance(matchup, dict):
        raise ValueError("WNBA Step 5C matchup projection must be an object.")
    if matchup.get("model_version") != MATCHUP_MODEL_VERSION:
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5C received an unexpected Step 5B model version."
        )

    player_id = _to_int(snapshot.get("player_id"))
    game_id = _clean(snapshot.get("game_id"))
    focal = snapshot.get("focal_identity")
    if player_id is None or player_id <= 0 or game_id is None or not isinstance(focal, dict):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 4W player/game/focal identity is malformed."
        )
    team_key = _clean(focal.get("team_key"))
    opponent_key = _clean(focal.get("opponent_team_key"))
    side = _clean(focal.get("side"))
    if side not in {"away", "home"} or not team_key or not opponent_key:
        raise WNBAProjectionScenarioUpstreamError("Step 4W focal team/opponent identity is invalid.")
    if (
        _to_int(matchup.get("player_id")) != player_id
        or _clean(matchup.get("game_id")) != game_id
        or _clean(matchup.get("team_key")) != team_key
        or _clean(matchup.get("opponent_team_key")) != opponent_key
        or _clean(matchup.get("side")) != side
    ):
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B projection identity disagrees with the frozen Step 4W snapshot."
        )

    matchup_reference = matchup.get("snapshot_reference")
    readiness_reference = readiness.get("snapshot_reference")
    if not isinstance(matchup_reference, dict) or not isinstance(readiness_reference, dict):
        raise WNBAProjectionScenarioUpstreamError("Step 5B/4X snapshot reference is missing.")
    for key in ("snapshot_id", "content_sha256", "game_id", "player_id", "recent_window_games"):
        if matchup_reference.get(key) != readiness_reference.get(key):
            raise WNBAProjectionScenarioUpstreamError(
                f"Step 5B snapshot reference disagrees with Step 4X for {key}."
            )

    projection = matchup.get("projection")
    if not isinstance(projection, dict):
        raise WNBAProjectionScenarioUpstreamError("Step 5B projection object is missing.")
    base_minutes = _required_projection_value(projection, "minutes", "expected")
    observed_low_minutes = _required_projection_value(projection, "minutes", "sensitivity_low")
    observed_high_minutes = _required_projection_value(projection, "minutes", "sensitivity_high")
    if not observed_low_minutes <= base_minutes <= observed_high_minutes:
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B minutes sensitivity does not contain the central minutes projection."
        )

    availability = _availability_low_minutes_stress(
        _focal_availability(snapshot, player_id, side)
    )
    low_minutes_stress = _to_float(availability.get("low_minutes_stress_pct")) or 0.0
    low_minutes = observed_low_minutes * (1.0 - low_minutes_stress)
    high_minutes = observed_high_minutes
    context_spreads, spread_receipts = _context_spreads(matchup)

    stat_scenarios: dict[str, dict[str, Any]] = {}
    for stat in STAT_KEYS:
        base = _required_projection_value(projection, stat, "expected")
        observed_low = _required_projection_value(projection, stat, "minutes_sensitivity_low")
        observed_high = _required_projection_value(projection, stat, "minutes_sensitivity_high")
        if not observed_low <= base <= observed_high:
            raise WNBAProjectionScenarioUpstreamError(
                f"Step 5B {stat} minutes sensitivity does not contain the central projection."
            )
        spread = context_spreads[stat]
        low = observed_low * (1.0 - low_minutes_stress) * (1.0 - spread)
        high = observed_high * (1.0 + spread)
        stat_scenarios[stat] = {
            "low": round(max(0.0, low), 4),
            "base": round(base, 4),
            "high": round(max(base, high), 4),
            "observed_minutes_only_low_before_5c_stress": round(observed_low, 4),
            "observed_minutes_only_high_before_5c_stress": round(observed_high, 4),
            "availability_low_minutes_stress_pct": round(low_minutes_stress, 8),
            "context_spread_pct": round(spread, 8),
        }

    pra_low = sum(stat_scenarios[key]["low"] for key in STAT_KEYS)
    pra_base = sum(stat_scenarios[key]["base"] for key in STAT_KEYS)
    pra_high = sum(stat_scenarios[key]["high"] for key in STAT_KEYS)
    matchup_pra = _required_projection_value(projection, "pra", "expected")
    if abs(pra_base - matchup_pra) > 0.001:
        raise WNBAProjectionScenarioUpstreamError(
            "Step 5B PRA does not equal the sum of Step 5B P/R/A central projections."
        )
    stat_scenarios["pra"] = {
        "low": round(pra_low, 4),
        "base": round(pra_base, 4),
        "high": round(pra_high, 4),
        "composition": "points + rebounds + assists within each shared scenario",
    }

    breadth = {
        key: _scenario_breadth(
            stat_scenarios[key]["low"],
            stat_scenarios[key]["base"],
            stat_scenarios[key]["high"],
        )
        for key in (*STAT_KEYS, "pra")
    }
    tier_rank = {"TIGHT": 0, "MODERATE": 1, "WIDE": 2, "UNRESOLVED": 3}
    overall_tier = max(
        (breadth[key]["breadth_tier"] for key in STAT_KEYS),
        key=lambda value: tier_rank[value],
    )
    scenarios = {
        "low": {
            "scenario_type": "deterministic_downside_stress",
            "minutes": round(low_minutes, 4),
            **{key: stat_scenarios[key]["low"] for key in (*STAT_KEYS, "pra")},
            "assumptions": [
                "Observed low-minutes sensitivity from Step 5A/5B.",
                "Focal uncertain availability receives scenario-only downside minutes stress.",
                "Context uncertainty is applied adversely without changing the central mean.",
            ],
        },
        "base": {
            "scenario_type": "exact_frozen_step_5b_central_projection",
            "minutes": round(base_minutes, 4),
            **{key: stat_scenarios[key]["base"] for key in (*STAT_KEYS, "pra")},
            "assumptions": [
                "Exactly equals the frozen Step-5B central projection.",
                "No Step-5C uncertainty penalty or boost is applied to BASE.",
            ],
        },
        "high": {
            "scenario_type": "deterministic_upside_stress",
            "minutes": round(high_minutes, 4),
            **{key: stat_scenarios[key]["high"] for key in (*STAT_KEYS, "pra")},
            "assumptions": [
                "Observed high-minutes sensitivity from Step 5A/5B.",
                "Context uncertainty is applied favorably.",
                "Uncertain injury status does not create an upside minutes bonus.",
            ],
        },
    }

    warning_ids = _dig(readiness, "summary", "warning_ids")
    if not isinstance(warning_ids, list):
        warning_ids = []
    lineup_context = _lineup_context_spread(matchup)
    model_config = {
        "model_version": MODEL_VERSION,
        "matchup_model_version": MATCHUP_MODEL_VERSION,
        "focal_status_low_minutes_stress": FOCAL_STATUS_LOW_MINUTES_STRESS,
        "generic_uncertain_low_minutes_stress": GENERIC_UNCERTAIN_LOW_MINUTES_STRESS,
        "max_availability_low_minutes_stress": MAX_AVAILABILITY_LOW_MINUTES_STRESS,
        "partial_matchup_context_spread": PARTIAL_MATCHUP_CONTEXT_SPREAD,
        "lineup_blocking_spread_per_full_share": LINEUP_BLOCKING_SPREAD_PER_FULL_SHARE,
        "lineup_uncertain_spread_per_full_share": LINEUP_UNCERTAIN_SPREAD_PER_FULL_SHARE,
        "max_lineup_context_spread": MAX_LINEUP_CONTEXT_SPREAD,
        "shot_zone_unavailable_points_spread": SHOT_ZONE_UNAVAILABLE_POINTS_SPREAD,
        "shot_zone_low_sample_points_spread": SHOT_ZONE_LOW_SAMPLE_POINTS_SPREAD,
        "max_context_spread_per_stat": MAX_CONTEXT_SPREAD_PER_STAT,
        "central_projection_adjustment": False,
        "probability_model": False,
    }
    fingerprint_payload = {
        "snapshot_content_sha256": snapshot.get("content_sha256"),
        "step_5b_projection_fingerprint_sha256": matchup.get("projection_fingerprint_sha256"),
        "model_config": model_config,
        "availability_stress": availability,
        "context_spreads": context_spreads,
        "scenarios": scenarios,
    }
    scenario_hash = _canonical_hash(fingerprint_payload)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_deterministic_projection_scenario_envelope",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "scenario_id": f"wnba-5c-{game_id}-{player_id}-{scenario_hash[:16]}",
        "scenario_fingerprint_sha256": scenario_hash,
        "season": snapshot.get("season"),
        "season_type": snapshot.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "side": side,
        "readiness": deepcopy(matchup.get("readiness")),
        "snapshot_reference": deepcopy(readiness_reference),
        "step_5b_projection_reference": {
            "model_version": matchup.get("model_version"),
            "projection_id": matchup.get("projection_id"),
            "projection_fingerprint_sha256": matchup.get("projection_fingerprint_sha256"),
        },
        "central_projection": deepcopy(projection),
        "scenarios": scenarios,
        "scenario_components": {
            "observed_minutes": {
                "low_before_availability_stress": round(observed_low_minutes, 4),
                "base": round(base_minutes, 4),
                "high": round(observed_high_minutes, 4),
                "source": "Step 5A minutes sensitivity carried through Step 5B",
            },
            "focal_availability": availability,
            "lineup_continuity": lineup_context,
            "context_spread_pct_by_stat": context_spreads,
            "context_spread_receipts": spread_receipts,
            "readiness_warning_ids": deepcopy(warning_ids),
        },
        "scenario_breadth": {
            "by_stat": breadth,
            "overall_tier": overall_tier,
            "tier_semantics": (
                "Breadth tier describes deterministic LOW/HIGH width only; it is "
                "not confidence, calibration, or probability."
            ),
        },
        "model_config": model_config,
        "projection_semantics": {
            "central_projection_exactly_step_5b": True,
            "conditional_on_player_active": True,
            "low_high_are_deterministic_scenarios": True,
            "low_high_are_not_confidence_intervals": True,
            "low_high_are_not_probability_quantiles": True,
            "no_empirical_game_level_stat_variance_claimed": True,
            "pra_is_sum_of_scenario_component_stats": True,
        },
        "guardrails": {
            "step_4x_not_ready_blocks_5c": True,
            "step_5b_model_version_checked": True,
            "step_5b_and_step_4w_identity_must_match": True,
            "step_5b_and_step_4x_snapshot_reference_must_match": True,
            "required_step_5b_scenario_schema_fails_closed_if_missing": True,
            "step_5c_never_changes_step_5b_central_mean": True,
            "uncertain_availability_stress_is_scenario_only": True,
            "out_or_blocking_focal_player_fails_closed": True,
            "lineup_disruption_does_not_redistribute_teammate_opportunity": True,
            "no_empirical_standard_deviation_invented": True,
            "no_confidence_interval_created": True,
            "no_sportsbook_data_used": True,
            "no_betting_probability_created": True,
            "no_monte_carlo_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "central_step_5b_projection_preserved": True,
            "observed_minutes_sensitivity_preserved": True,
            "availability_stress_applied_only_to_low_scenario": True,
            "required_step_5b_scenario_objects_checked": True,
            "context_spreads_are_exposed_and_capped": True,
            "scenario_ordering_checked": True,
            "pra_component_sum_checked": True,
            "scenario_fingerprint_created": True,
        },
    }


def project_scenarios_from_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    _readiness_snapshot(readiness)
    try:
        matchup = project_matchup_adjusted_from_readiness(readiness)
    except WNBAMatchupAdjustedProjectionNotReadyError as exc:
        raise WNBAProjectionScenarioNotReadyError(str(exc)) from exc
    except WNBAMatchupAdjustedProjectionModelInputError as exc:
        raise WNBAProjectionScenarioModelInputError(str(exc)) from exc
    except WNBAMatchupAdjustedProjectionUpstreamError as exc:
        raise WNBAProjectionScenarioUpstreamError(str(exc)) from exc
    return build_projection_scenarios(matchup, readiness)


def get_player_game_projection_scenarios(
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
    require_current_availability = _bool(
        require_current_availability, "require_current_availability"
    )
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)
    try:
        readiness = get_player_game_model_input_readiness(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            require_current_availability=require_current_availability,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=False,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            include_snapshot=True,
        )
    except WNBAModelInputReadinessNotFoundError as exc:
        raise WNBAProjectionScenarioNotFoundError(str(exc)) from exc
    except WNBAModelInputReadinessUpstreamError as exc:
        raise WNBAProjectionScenarioUpstreamError(str(exc)) from exc
    return project_scenarios_from_readiness(readiness)
