"""Step 8B neutral deterministic WNBA projection core.

Consumes a certified Step-8A handoff plus the live-certified Step-8B official
recent-box baseline. The projection is intentionally neutral: complete official
P/R/A per-minute rates are multiplied by the recent official mean-minute anchor,
with a 40-minute regulation cap. No current matchup, role redistribution,
injury-driven minutes change, Monte Carlo, sportsbook probability, or persistence
is applied here. Those belong to later Step-8 layers.

The module independently revalidates the Step-8B baseline content hash before
allowing a projection to be created.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Mapping

from sports_api.wnba_step8_official_box_baseline import (
    BASELINE_RELEASE_ID,
    SCHEMA_VERSION as BASELINE_SCHEMA_VERSION,
    build_step8_official_box_baseline,
)
from sports_api.wnba_step8_projection_handoff import (
    HANDOFF_RELEASE_ID,
    SCHEMA_VERSION as HANDOFF_SCHEMA_VERSION,
    get_player_game_step8_projection_handoff,
)

SOURCE = "Kyre Sports API WNBA Step 8B neutral deterministic projection core"
SCHEMA_VERSION = "wnba_step_8b_core_projection_v1"
MODEL_VERSION = "wnba_step8b_neutral_official_box_rate_projection_2026_regular_v1"
STEP8_CORE_PROJECTION_ENABLED_ENV = "WNBA_STEP8_CORE_PROJECTION_ENABLED"
CERTIFIED_SEASON = 2026
CERTIFIED_SEASON_TYPE = "Regular Season"
EXPECTED_GAME_COUNT = 5
REGULATION_MINUTES_CAP = 40.0

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep8CoreProjectionDisabledError(RuntimeError):
    """Raised when the isolated Step-8B projection core is not explicitly enabled."""


class WNBAStep8CoreProjectionNotReadyError(RuntimeError):
    """Raised when certified input evidence does not authorize a neutral projection."""


class WNBAStep8CoreProjectionUpstreamError(RuntimeError):
    """Raised when certified Step-8A/8B evidence is malformed or contradictory."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step8_core_projection_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP8_CORE_PROJECTION_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [key for key in _OFF_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep8CoreProjectionDisabledError(
            "Step 8B projection core refuses production switches: " + ", ".join(bad)
        )
    if not _truthy(source.get("WNBA_STEP8_PROJECTION_HANDOFF_ENABLED")):
        raise WNBAStep8CoreProjectionDisabledError(
            "Step 8B projection core requires the certified Step-8A handoff flag."
        )
    if not step8_core_projection_enabled(source):
        raise WNBAStep8CoreProjectionDisabledError(
            f"Step 8B projection core requires {STEP8_CORE_PROJECTION_ENABLED_ENV}=true."
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStep8CoreProjectionUpstreamError(f"Step 8B {label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep8CoreProjectionUpstreamError(
            f"Step 8B {label} must be numeric."
        ) from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise WNBAStep8CoreProjectionUpstreamError(f"Step 8B {label} must be finite.")
    return result


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def recompute_step8_official_box_baseline_content_sha256(
    baseline: Mapping[str, Any],
) -> str:
    """Independently reconstruct the exact Step-8B official-box hash surface."""
    provenance = baseline.get("provenance")
    if not isinstance(provenance, Mapping):
        raise WNBAStep8CoreProjectionUpstreamError(
            "Step 8B official baseline provenance is malformed."
        )
    content = {
        "schema_version": baseline.get("schema_version"),
        "baseline_release_id": baseline.get("baseline_release_id"),
        "step8a_handoff_content_sha256": provenance.get("step8a_handoff_content_sha256"),
        "step4w_snapshot_content_sha256": provenance.get("step4w_snapshot_content_sha256"),
        "requested_game_id": baseline.get("requested_game_id"),
        "player_id": baseline.get("player_id"),
        "selected_game_ids": baseline.get("selected_game_ids"),
        "games": baseline.get("games"),
        "summary": baseline.get("summary"),
    }
    return _canonical_hash(content)


def _validate_handoff(handoff: Mapping[str, Any]) -> tuple[int, str, dict[str, Any], dict[str, Any]]:
    if not isinstance(handoff, Mapping):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core requires a Step-8A handoff object.")
    if handoff.get("data_type") != "certified_pre_projection_model_handoff":
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core received the wrong handoff data type.")
    if handoff.get("schema_version") != HANDOFF_SCHEMA_VERSION or handoff.get("handoff_release_id") != HANDOFF_RELEASE_ID:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core received an unsupported Step-8A contract.")
    if handoff.get("projection_execution_authorized") is not True:
        raise WNBAStep8CoreProjectionNotReadyError("Step 8A does not authorize projection execution.")
    if handoff.get("production_activation_allowed") is not False:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8A unexpectedly allows production activation.")
    snapshot = handoff.get("snapshot")
    reference = handoff.get("snapshot_reference")
    if not isinstance(snapshot, dict) or not isinstance(reference, dict):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8A snapshot/reference is malformed.")
    try:
        player_id = int(snapshot.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8A player ID is invalid.") from exc
    game_id = _clean(snapshot.get("game_id"))
    if player_id <= 0 or game_id is None:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8A game/player identity is invalid.")
    if snapshot.get("season") != CERTIFIED_SEASON or snapshot.get("season_type") != CERTIFIED_SEASON_TYPE:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core accepts only certified 2026 Regular Season handoffs.")
    if snapshot.get("recent_window_games") != EXPECTED_GAME_COUNT:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core requires the certified five-game handoff window.")
    if reference.get("player_id") != player_id or _clean(reference.get("game_id")) != game_id:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8A snapshot reference identity disagrees with its snapshot.")
    return player_id, game_id, snapshot, reference


def _validate_current_availability(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    summary = snapshot.get("availability_summary")
    if not isinstance(summary, dict):
        raise WNBAStep8CoreProjectionNotReadyError(
            "Step 8B core requires the certified current-availability summary."
        )
    if summary.get("focal_player_current_roster_match") is not True:
        raise WNBAStep8CoreProjectionNotReadyError(
            "Step 8B focal player is not verified on the current roster."
        )
    focal = summary.get("focal_player_availability")
    if not isinstance(focal, dict):
        raise WNBAStep8CoreProjectionNotReadyError(
            "Step 8B current focal-player availability is malformed."
        )
    if focal.get("availability_blocking") is True:
        raise WNBAStep8CoreProjectionNotReadyError(
            "Step 8B refuses a neutral projection for a blocking current availability state."
        )
    return {
        "availability_class": focal.get("availability_class"),
        "listed_on_injury_report": bool(focal.get("listed_on_injury_report")),
        "availability_uncertain": bool(focal.get("availability_uncertain")),
        "availability_blocking": bool(focal.get("availability_blocking")),
        "current_roster_match": True,
    }


def _validate_rotation_alignment(snapshot: Mapping[str, Any], official_mean_minutes: float) -> dict[str, Any]:
    inputs = snapshot.get("inputs")
    opportunity = inputs.get("player_opportunity_context") if isinstance(inputs, dict) else None
    minutes_obj = opportunity.get("observed_minutes_opportunity") if isinstance(opportunity, dict) else None
    tracked = minutes_obj.get("tracked_minutes") if isinstance(minutes_obj, dict) else None
    stability = tracked.get("stability") if isinstance(tracked, dict) else None
    if not isinstance(stability, dict):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B handoff is missing rotation stability evidence.")
    game_count = stability.get("rotation_game_count")
    if game_count != EXPECTED_GAME_COUNT:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B rotation evidence is not the exact five-game window.")
    rotation_mean = _number(stability.get("tracked_minutes_mean"), "rotation mean minutes")
    if abs(rotation_mean - official_mean_minutes) > 0.02:
        raise WNBAStep8CoreProjectionUpstreamError(
            "Step 8B official box and certified rotation mean minutes disagree."
        )
    return {
        "rotation_game_count": game_count,
        "rotation_mean_minutes": round(rotation_mean, 6),
        "box_rotation_mean_minutes_difference": round(official_mean_minutes - rotation_mean, 6),
        "tracked_minutes_population_stddev": stability.get("tracked_minutes_population_stddev"),
        "tracked_minutes_coefficient_of_variation": stability.get("tracked_minutes_coefficient_of_variation"),
    }


def _validate_baseline(
    baseline: Mapping[str, Any],
    handoff: Mapping[str, Any],
    *,
    player_id: int,
    game_id: str,
    snapshot: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> tuple[dict[str, Any], float, dict[str, float]]:
    if not isinstance(baseline, Mapping):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core requires an official-box baseline object.")
    if baseline.get("data_type") != "official_recent_player_box_stat_baseline":
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core received the wrong baseline data type.")
    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION or baseline.get("baseline_release_id") != BASELINE_RELEASE_ID:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B core received an unsupported official-box baseline contract.")
    if baseline.get("player_id") != player_id or _clean(baseline.get("requested_game_id")) != game_id:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline game/player identity disagrees with Step 8A.")
    focal_team = _clean((snapshot.get("focal_identity") or {}).get("team_key"))
    if _clean(baseline.get("current_team_key")) != focal_team:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline current team disagrees with the handoff.")

    provenance = baseline.get("provenance")
    if not isinstance(provenance, Mapping):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline provenance is malformed.")
    if provenance.get("step8a_handoff_content_sha256") != handoff.get("handoff_content_sha256"):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline is bound to a different Step-8A handoff.")
    if provenance.get("step4w_snapshot_content_sha256") != reference.get("content_sha256"):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline is bound to a different Step-4W snapshot.")
    if provenance.get("game_ids_from_certified_handoff_player_advanced") is not True or provenance.get("boxes_reloaded_from_official_wnba_com") is not True:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline provenance verification is incomplete.")

    verification = baseline.get("verification")
    if not isinstance(verification, Mapping):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline verification is malformed.")
    for key in (
        "step8a_handoff_identity_verified",
        "advanced_selected_game_ids_used_exactly",
        "all_game_ids_unique_certified_regular_family",
        "player_resolved_exactly_once_per_box",
        "box_player_team_identity_matches_handoff_evidence",
        "advanced_and_box_average_minutes_match",
        "most_recent_team_matches_current_focal_team",
        "no_projection_created",
    ):
        if verification.get(key) is not True:
            raise WNBAStep8CoreProjectionUpstreamError(f"Step 8B baseline verification {key!r} is not true.")
    if verification.get("third_party_sources_used") is not False:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline unexpectedly used third-party data.")

    provided_hash = _clean(baseline.get("baseline_content_sha256"))
    recomputed_hash = recompute_step8_official_box_baseline_content_sha256(baseline)
    if provided_hash is None or provided_hash != recomputed_hash:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline content hash failed independent verification.")

    game_ids = baseline.get("selected_game_ids")
    if not isinstance(game_ids, list) or len(game_ids) != EXPECTED_GAME_COUNT or len(set(game_ids)) != EXPECTED_GAME_COUNT:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline does not contain five unique games.")
    summary = baseline.get("summary")
    if not isinstance(summary, dict) or summary.get("game_count") != EXPECTED_GAME_COUNT:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline summary is malformed.")
    minutes = summary.get("minutes")
    rates = summary.get("official_per_minute_rates")
    if not isinstance(minutes, dict) or not isinstance(rates, dict):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B baseline is missing minutes/rate summary.")
    official_mean_minutes = _number(minutes.get("mean"), "official box mean minutes")
    if official_mean_minutes <= 0.0 or official_mean_minutes > 60.0:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B official mean minutes are implausible.")

    rate_values = {
        stat: _number(rates.get(stat), f"official {stat} per-minute rate")
        for stat in ("points", "rebounds", "assists", "points_rebounds_assists")
    }
    if any(value < 0.0 for value in rate_values.values()):
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B official per-minute rates cannot be negative.")
    component_rate_sum = rate_values["points"] + rate_values["rebounds"] + rate_values["assists"]
    if abs(component_rate_sum - rate_values["points_rebounds_assists"]) > 1e-6:
        raise WNBAStep8CoreProjectionUpstreamError("Step 8B official PRA rate disagrees with P+R+A rates.")
    return summary, official_mean_minutes, rate_values


def build_step8_core_projection(
    handoff: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the neutral deterministic Step-8B projection from certified inputs."""
    player_id, game_id, snapshot, reference = _validate_handoff(handoff)
    availability = _validate_current_availability(snapshot)
    summary, official_mean_minutes, rates = _validate_baseline(
        baseline,
        handoff,
        player_id=player_id,
        game_id=game_id,
        snapshot=snapshot,
        reference=reference,
    )
    rotation = _validate_rotation_alignment(snapshot, official_mean_minutes)

    neutral_minutes = min(official_mean_minutes, REGULATION_MINUTES_CAP)
    if neutral_minutes <= 0.0:
        raise WNBAStep8CoreProjectionNotReadyError("Step 8B neutral minutes anchor is not positive.")
    projection = {
        "minutes": round(neutral_minutes, 6),
        "points": round(rates["points"] * neutral_minutes, 6),
        "rebounds": round(rates["rebounds"] * neutral_minutes, 6),
        "assists": round(rates["assists"] * neutral_minutes, 6),
    }
    projection["points_rebounds_assists"] = round(
        projection["points"] + projection["rebounds"] + projection["assists"], 6
    )

    dispersion = {
        stat: {
            "recent_mean": (summary.get(stat) or {}).get("mean"),
            "recent_median": (summary.get(stat) or {}).get("median"),
            "recent_population_stddev": (summary.get(stat) or {}).get("population_stddev"),
        }
        for stat in ("minutes", "points", "rebounds", "assists", "points_rebounds_assists")
    }
    content = {
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "step8a_handoff_content_sha256": handoff.get("handoff_content_sha256"),
        "step8b_baseline_content_sha256": baseline.get("baseline_content_sha256"),
        "game_id": game_id,
        "player_id": player_id,
        "neutral_regulation_minutes_anchor": round(neutral_minutes, 6),
        "official_per_minute_rates": rates,
        "projection": projection,
    }
    digest = _canonical_hash(content)
    return {
        "source": SOURCE,
        "data_type": "neutral_deterministic_player_projection",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "projection_id": f"wnba-8b-core-{game_id}-{player_id}-{digest[:16]}",
        "projection_content_sha256": digest,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": CERTIFIED_SEASON,
        "season_type": CERTIFIED_SEASON_TYPE,
        "game_id": game_id,
        "player_id": player_id,
        "team_key": _clean((snapshot.get("focal_identity") or {}).get("team_key")),
        "opponent_team_key": _clean((snapshot.get("focal_identity") or {}).get("opponent_team_key")),
        "neutral_regulation_minutes_anchor": round(neutral_minutes, 6),
        "regulation_minutes_cap": REGULATION_MINUTES_CAP,
        "regulation_cap_applied": official_mean_minutes > REGULATION_MINUTES_CAP,
        "official_recent_mean_minutes": round(official_mean_minutes, 6),
        "official_per_minute_rates": rates,
        "projection": projection,
        "historical_dispersion": dispersion,
        "current_availability": availability,
        "rotation_alignment": rotation,
        "provenance": {
            "step8a_handoff_id": handoff.get("handoff_id"),
            "step8a_handoff_content_sha256": handoff.get("handoff_content_sha256"),
            "step4w_snapshot_id": reference.get("snapshot_id"),
            "step4w_snapshot_content_sha256": reference.get("content_sha256"),
            "step8b_baseline_id": baseline.get("baseline_id"),
            "step8b_baseline_content_sha256": baseline.get("baseline_content_sha256"),
            "official_box_baseline_hash_recomputed": True,
        },
        "semantics": {
            "projection_is_neutral_recent_form_anchor": True,
            "minutes_anchor_is_recent_official_box_mean": True,
            "minutes_anchor_is_capped_at_wnba_regulation_minutes": True,
            "points_rebounds_assists_use_complete_official_box_rates": True,
            "pbp_feature_counts_are_not_used_as_box_stat_baseline": True,
            "current_matchup_adjustment_applied": False,
            "current_role_adjustment_applied": False,
            "current_injury_minutes_adjustment_applied": False,
            "teammate_opportunity_redistribution_applied": False,
        },
        "guardrails": {
            "deterministic_projection_created": True,
            "no_matchup_adjustment_created": True,
            "no_role_redistribution_created": True,
            "no_projected_starter_created": True,
            "no_monte_carlo_created": True,
            "no_sportsbook_data_created": True,
            "no_betting_probability_created": True,
            "no_persistence_created": True,
            "production_activation_allowed": False,
        },
        "verification": {
            "step8a_handoff_projection_authorized": True,
            "step8b_official_baseline_hash_verified": True,
            "step8b_official_baseline_identity_verified": True,
            "official_box_rotation_minutes_aligned": True,
            "current_roster_identity_verified": True,
            "current_availability_not_blocking": True,
            "component_pra_rate_consistency_verified": True,
            "third_party_sources_used": False,
        },
    }


def get_player_game_step8_core_projection(
    player_id: int,
    game_id: str,
) -> dict[str, Any]:
    """OFF-by-default live wrapper for the neutral Step-8B projection core."""
    _assert_safe_environment()
    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    baseline = build_step8_official_box_baseline(handoff)
    return build_step8_core_projection(handoff, baseline)


__all__ = [
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "STEP8_CORE_PROJECTION_ENABLED_ENV",
    "WNBAStep8CoreProjectionDisabledError",
    "WNBAStep8CoreProjectionNotReadyError",
    "WNBAStep8CoreProjectionUpstreamError",
    "build_step8_core_projection",
    "get_player_game_step8_core_projection",
    "recompute_step8_official_box_baseline_content_sha256",
    "step8_core_projection_enabled",
]
