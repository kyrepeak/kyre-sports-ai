"""Step 4X: WNBA model-input readiness and data-quality gate.

This layer evaluates a frozen Step 4W projection-input snapshot before any
projection model is allowed to run. It never repairs, imputes, redistributes,
or projects missing information. Readiness is rule-based:

- READY: no blockers and no warnings
- READY_WITH_WARNINGS: no blockers, one or more warnings
- NOT_READY: one or more blockers

A diagnostic score is also returned, but blockers always override that score.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_projection_input_snapshot import (
    WNBAProjectionInputSnapshotNotFoundError,
    WNBAProjectionInputSnapshotUpstreamError,
    get_player_game_projection_input_snapshot,
)

READINESS_SOURCE = "Kyre Sports API WNBA Step 4X model-input readiness gate"
READINESS_SCHEMA_VERSION = "wnba_step_4x_v1"
SNAPSHOT_SCHEMA_VERSION = "wnba_step_4w_v1"
READINESS_STATES = ("READY", "READY_WITH_WARNINGS", "NOT_READY")
MAX_RECENT_GAMES = 20
DEFAULT_MAX_SNAPSHOT_AGE_MINUTES = 15
MIN_CORE_GAME_COVERAGE = 0.60
PREFERRED_CORE_GAME_COVERAGE = 0.80
MIN_FEATURE_ELIGIBLE_SHARE = 0.60
PREFERRED_FEATURE_ELIGIBLE_SHARE = 0.80
NEAR_TIP_HOURS = 24.0
WARNING_INJURY_REPORT_AGE_HOURS = 8.0
BLOCKING_INJURY_REPORT_AGE_HOURS = 24.0
FUTURE_TIMESTAMP_TOLERANCE_MINUTES = 5.0


class WNBAModelInputReadinessUpstreamError(RuntimeError):
    """Raised when Step 4W cannot construct a trustworthy snapshot."""


class WNBAModelInputReadinessNotFoundError(LookupError):
    """Raised when required player/game evidence cannot be found."""


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    category: str,
    severity: str,
    message: str,
    *,
    observed: Any = None,
    threshold: Any = None,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "severity": severity,
            "blocking": severity == "blocker",
            "message": message,
            "observed": deepcopy(observed),
            "threshold": deepcopy(threshold),
        }
    )


def _coverage_check(
    checks: list[dict[str, Any]],
    *,
    check_prefix: str,
    label: str,
    observed_games: int | None,
    requested_games: int,
) -> float | None:
    coverage = _ratio(observed_games, requested_games)
    if observed_games is None or observed_games <= 0 or coverage is None:
        _check(
            checks,
            f"{check_prefix}_coverage",
            "historical_coverage",
            "blocker",
            f"{label} has no usable recent-game coverage.",
            observed={"observed_games": observed_games, "requested_games": requested_games},
            threshold={"minimum_coverage": MIN_CORE_GAME_COVERAGE},
        )
    elif coverage < MIN_CORE_GAME_COVERAGE:
        _check(
            checks,
            f"{check_prefix}_coverage",
            "historical_coverage",
            "blocker",
            f"{label} covers too little of the requested recent window.",
            observed={"observed_games": observed_games, "requested_games": requested_games, "coverage": coverage},
            threshold={"minimum_coverage": MIN_CORE_GAME_COVERAGE},
        )
    elif coverage < PREFERRED_CORE_GAME_COVERAGE:
        _check(
            checks,
            f"{check_prefix}_coverage",
            "historical_coverage",
            "warning",
            f"{label} covers less than the preferred recent-game window.",
            observed={"observed_games": observed_games, "requested_games": requested_games, "coverage": coverage},
            threshold={"preferred_coverage": PREFERRED_CORE_GAME_COVERAGE},
        )
    else:
        _check(
            checks,
            f"{check_prefix}_coverage",
            "historical_coverage",
            "pass",
            f"{label} recent-game coverage is sufficient.",
            observed={"observed_games": observed_games, "requested_games": requested_games, "coverage": coverage},
            threshold={"preferred_coverage": PREFERRED_CORE_GAME_COVERAGE},
        )
    return coverage


def _snapshot_hash_content(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": snapshot.get("schema_version"),
        "season": snapshot.get("season"),
        "season_type": snapshot.get("season_type"),
        "game_id": snapshot.get("game_id"),
        "player_id": snapshot.get("player_id"),
        "recent_window_games": snapshot.get("recent_window_games"),
        "game_identity": snapshot.get("game_identity"),
        "focal_identity": snapshot.get("focal_identity"),
        "component_status": snapshot.get("component_status"),
        "inputs": snapshot.get("inputs"),
    }


def _snapshot_age_checks(
    snapshot: dict[str, Any],
    checks: list[dict[str, Any]],
    evaluated_at: datetime,
    max_snapshot_age_minutes: int,
) -> None:
    captured = _parse_dt(snapshot.get("captured_at_utc"))
    finalized = _parse_dt(snapshot.get("finalized_at_utc"))
    if captured is None or finalized is None:
        _check(
            checks,
            "snapshot_timestamps_parse",
            "freshness",
            "blocker",
            "Step 4W snapshot capture/finalization timestamps are missing or invalid.",
            observed={"captured_at_utc": snapshot.get("captured_at_utc"), "finalized_at_utc": snapshot.get("finalized_at_utc")},
        )
        return
    if finalized < captured:
        _check(
            checks,
            "snapshot_timestamp_order",
            "freshness",
            "blocker",
            "Step 4W snapshot finalized before it was captured.",
            observed={"captured_at_utc": snapshot.get("captured_at_utc"), "finalized_at_utc": snapshot.get("finalized_at_utc")},
        )
    else:
        _check(
            checks,
            "snapshot_timestamp_order",
            "freshness",
            "pass",
            "Step 4W snapshot timestamp ordering is valid.",
        )
    future_minutes = (captured - evaluated_at).total_seconds() / 60.0
    if future_minutes > FUTURE_TIMESTAMP_TOLERANCE_MINUTES:
        _check(
            checks,
            "snapshot_clock_skew",
            "freshness",
            "blocker",
            "Step 4W snapshot capture time is implausibly in the future.",
            observed={"minutes_in_future": round(future_minutes, 3)},
            threshold={"tolerance_minutes": FUTURE_TIMESTAMP_TOLERANCE_MINUTES},
        )
    age_minutes = max(0.0, (evaluated_at - finalized).total_seconds() / 60.0)
    if age_minutes > max_snapshot_age_minutes:
        _check(
            checks,
            "snapshot_age",
            "freshness",
            "blocker",
            "Step 4W snapshot is older than the maximum model-input age.",
            observed={"age_minutes": round(age_minutes, 3)},
            threshold={"max_snapshot_age_minutes": max_snapshot_age_minutes},
        )
    else:
        _check(
            checks,
            "snapshot_age",
            "freshness",
            "pass",
            "Step 4W snapshot is fresh enough for model ingestion.",
            observed={"age_minutes": round(age_minutes, 3)},
            threshold={"max_snapshot_age_minutes": max_snapshot_age_minutes},
        )


def _game_identity_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]], evaluated_at: datetime) -> float | None:
    game = snapshot.get("game_identity")
    focal = snapshot.get("focal_identity")
    if not isinstance(game, dict) or not isinstance(focal, dict):
        _check(checks, "game_focal_identity_objects", "identity", "blocker", "Step 4W game/focal identity objects are missing or malformed.")
        return None
    away = _clean(game.get("away_team_key"))
    home = _clean(game.get("home_team_key"))
    team = _clean(focal.get("team_key"))
    opponent = _clean(focal.get("opponent_team_key"))
    side = _clean(focal.get("side"))
    player_id = _to_int(focal.get("player_id"))
    top_player_id = _to_int(snapshot.get("player_id"))
    valid = (
        away is not None and home is not None and away != home
        and team in {away, home}
        and opponent in {away, home}
        and team != opponent
        and side in {"away", "home"}
        and ((side == "away" and team == away and opponent == home) or (side == "home" and team == home and opponent == away))
        and player_id == top_player_id
    )
    _check(
        checks,
        "game_focal_identity_consistency",
        "identity",
        "pass" if valid else "blocker",
        "Step 4W player/team/opponent identity is internally consistent." if valid else "Step 4W player/team/opponent identity is inconsistent.",
        observed={"away_team_key": away, "home_team_key": home, "focal_team_key": team, "opponent_team_key": opponent, "side": side, "player_id": player_id},
    )

    schedule_change = game.get("schedule_change")
    if isinstance(schedule_change, dict) and (schedule_change.get("cancelled") or schedule_change.get("postponed")):
        _check(
            checks,
            "game_schedule_active",
            "game_status",
            "blocker",
            "Requested game is cancelled or postponed and is not ready for a pregame projection.",
            observed=deepcopy(schedule_change),
        )
    else:
        _check(checks, "game_schedule_active", "game_status", "pass", "Requested game is not marked cancelled/postponed.")

    category = (_clean(_dig(game, "status", "category")) or "unknown").casefold()
    if category in {"final", "live", "suspended"}:
        _check(
            checks,
            "pregame_status",
            "game_status",
            "blocker",
            f"Game status {category!r} is not eligible for this pregame model-input gate.",
            observed=category,
        )
    elif category == "delayed":
        _check(checks, "pregame_status", "game_status", "warning", "Game is delayed; re-capture inputs when timing is clarified.", observed=category)
    elif category in {"scheduled", "unknown"}:
        _check(
            checks,
            "pregame_status",
            "game_status",
            "pass" if category == "scheduled" else "warning",
            "Game is scheduled for pregame evaluation." if category == "scheduled" else "Game status is unknown; projection can proceed only with caution.",
            observed=category,
        )
    else:
        _check(checks, "pregame_status", "game_status", "warning", "Game status is not a standard scheduled state.", observed=category)

    tip = _parse_dt(game.get("game_datetime_utc"))
    if tip is None:
        _check(checks, "game_tip_time", "game_status", "blocker", "Official game tip time is missing or invalid.", observed=game.get("game_datetime_utc"))
        return None
    hours_to_tip = (tip - evaluated_at).total_seconds() / 3600.0
    _check(
        checks,
        "game_tip_time",
        "game_status",
        "pass",
        "Official game tip time is parseable.",
        observed={"game_datetime_utc": game.get("game_datetime_utc"), "hours_to_tip": round(hours_to_tip, 3)},
    )
    return hours_to_tip


def _required_core_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    verification = snapshot.get("verification")
    required_flags = (
        "required_step_4v_opportunity_available",
        "required_official_game_schedule_rest_travel_available",
        "focal_latest_observed_team_is_in_requested_game",
        "opponent_resolved_from_official_game_identity",
        "content_hash_created",
    )
    if not isinstance(verification, dict):
        _check(checks, "step_4w_required_verification", "required_core", "blocker", "Step 4W required verification object is missing.")
    else:
        bad = [name for name in required_flags if verification.get(name) is not True]
        _check(
            checks,
            "step_4w_required_verification",
            "required_core",
            "blocker" if bad else "pass",
            "Step 4W required verification flags failed." if bad else "Step 4W required verification flags passed.",
            observed={"failed_flags": bad},
        )

    guardrails = snapshot.get("guardrails")
    guardrail_flags = (
        "snapshot_is_pre_model_input_not_projection",
        "no_projected_minutes_created",
        "no_projected_starters_created",
        "no_missing_teammate_opportunity_redistribution_created",
        "no_monte_carlo_created",
        "no_sportsbook_data_created",
        "no_betting_probability_created",
        "court_context_is_not_defender_assignment",
        "official_wnba_player_defender_assignment_remains_unavailable",
    )
    if not isinstance(guardrails, dict):
        _check(checks, "pre_model_guardrails", "required_core", "blocker", "Step 4W pre-model guardrails are missing.")
    else:
        bad = [name for name in guardrail_flags if guardrails.get(name) is not True]
        _check(
            checks,
            "pre_model_guardrails",
            "required_core",
            "blocker" if bad else "pass",
            "Step 4W pre-model guardrails are incomplete." if bad else "Step 4W pre-model guardrails are intact.",
            observed={"failed_flags": bad},
        )


def _opportunity_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    requested = _to_int(snapshot.get("recent_window_games"))
    opportunity = _dig(snapshot, "inputs", "player_opportunity_context")
    if requested is None or requested <= 0:
        _check(checks, "recent_window", "historical_coverage", "blocker", "Step 4W recent window is invalid.", observed=snapshot.get("recent_window_games"))
        return
    if not isinstance(opportunity, dict):
        _check(checks, "player_opportunity_component", "required_core", "blocker", "Step 4V player opportunity context is missing from Step 4W inputs.")
        return
    if _to_int(opportunity.get("player_id")) != _to_int(snapshot.get("player_id")):
        _check(checks, "opportunity_player_identity", "identity", "blocker", "Step 4V opportunity player ID disagrees with Step 4W snapshot.")
    else:
        _check(checks, "opportunity_player_identity", "identity", "pass", "Step 4V opportunity player ID matches Step 4W snapshot.")
    if _clean(opportunity.get("latest_observed_team_key")) != _clean(_dig(snapshot, "focal_identity", "team_key")):
        _check(checks, "opportunity_team_identity", "identity", "blocker", "Step 4V latest observed team disagrees with the requested game focal team.")
    else:
        _check(checks, "opportunity_team_identity", "identity", "pass", "Step 4V latest observed team matches the requested game focal team.")

    components = opportunity.get("components")
    if not isinstance(components, dict):
        _check(checks, "opportunity_core_components", "required_core", "blocker", "Step 4V component status object is missing.")
    else:
        missing_core = [name for name in ("rotation", "event_features") if not isinstance(components.get(name), dict) or components[name].get("available") is not True]
        _check(
            checks,
            "opportunity_core_components",
            "required_core",
            "blocker" if missing_core else "pass",
            "Step 4V required rotation/event components are unavailable." if missing_core else "Step 4V required rotation/event components are available.",
            observed={"missing_core_components": missing_core},
        )
        for name, label in (("starter_bench_role", "Starter/bench role context"), ("five_player_lineups", "Five-player lineup context")):
            row = components.get(name)
            available = isinstance(row, dict) and row.get("available") is True
            _check(
                checks,
                f"optional_{name}",
                "role_lineup_context",
                "pass" if available else "warning",
                f"{label} is available." if available else f"{label} is unavailable; projection uncertainty should increase.",
                observed=deepcopy(row),
            )

    rotation_games = _to_int(_dig(opportunity, "observed_minutes_opportunity", "source_game_count"))
    rotation_coverage = _coverage_check(
        checks,
        check_prefix="rotation_game",
        label="Official GameRotation history",
        observed_games=rotation_games,
        requested_games=requested,
    )
    stability_games = _to_int(_dig(opportunity, "observed_minutes_opportunity", "tracked_minutes", "stability", "rotation_game_count"))
    if rotation_games is not None and stability_games is not None and rotation_games != stability_games:
        _check(
            checks,
            "rotation_internal_count_consistency",
            "historical_coverage",
            "blocker",
            "Step 4V rotation source-game count disagrees with rotation stability count.",
            observed={"source_game_count": rotation_games, "stability_rotation_game_count": stability_games},
        )
    else:
        _check(checks, "rotation_internal_count_consistency", "historical_coverage", "pass", "Step 4V rotation game counts are internally consistent.")

    feature_games = _to_int(_dig(opportunity, "observed_event_opportunity", "feature_game_count"))
    feature_coverage = _coverage_check(
        checks,
        check_prefix="event_feature_game",
        label="Step 4U event-feature history",
        observed_games=feature_games,
        requested_games=requested,
    )
    eligible_share = _to_float(_dig(opportunity, "observed_event_opportunity", "data_quality", "feature_eligible_share_of_selected_lineup_events"))
    if eligible_share is None:
        _check(checks, "feature_eligible_event_share", "event_quality", "blocker", "Step 4U feature-eligible event share is missing.")
    elif eligible_share < MIN_FEATURE_ELIGIBLE_SHARE:
        _check(
            checks,
            "feature_eligible_event_share",
            "event_quality",
            "blocker",
            "Too few selected-lineup events qualify for Step 4U player features.",
            observed=eligible_share,
            threshold={"minimum_share": MIN_FEATURE_ELIGIBLE_SHARE},
        )
    elif eligible_share < PREFERRED_FEATURE_ELIGIBLE_SHARE:
        _check(
            checks,
            "feature_eligible_event_share",
            "event_quality",
            "warning",
            "Step 4U feature-eligible event share is below the preferred level.",
            observed=eligible_share,
            threshold={"preferred_share": PREFERRED_FEATURE_ELIGIBLE_SHARE},
        )
    else:
        _check(
            checks,
            "feature_eligible_event_share",
            "event_quality",
            "pass",
            "Step 4U feature-eligible event share is sufficient.",
            observed=eligible_share,
            threshold={"preferred_share": PREFERRED_FEATURE_ELIGIBLE_SHARE},
        )

    minute_cv = _to_float(_dig(opportunity, "observed_minutes_opportunity", "tracked_minutes", "stability", "tracked_minutes_coefficient_of_variation"))
    if minute_cv is not None and minute_cv > 0.35:
        _check(
            checks,
            "observed_minutes_variability",
            "model_uncertainty",
            "warning",
            "Recent observed minutes are highly variable; this is valid data but increases projection uncertainty.",
            observed={"coefficient_of_variation": minute_cv},
            threshold={"warning_above": 0.35},
        )
    else:
        _check(checks, "observed_minutes_variability", "model_uncertainty", "pass", "Recent observed minute variability is not unusually high.", observed={"coefficient_of_variation": minute_cv})

    _ = rotation_coverage, feature_coverage


def _availability_checks(
    snapshot: dict[str, Any],
    checks: list[dict[str, Any]],
    evaluated_at: datetime,
    hours_to_tip: float | None,
    require_current_availability: bool,
) -> None:
    status = _dig(snapshot, "component_status", "game_availability")
    requested = isinstance(status, dict) and status.get("requested") is True
    available = isinstance(status, dict) and status.get("available") is True
    if require_current_availability and not requested:
        _check(checks, "current_availability_requested", "availability", "blocker", "Current game availability is required by this gate but was not requested.")
        return
    if require_current_availability and not available:
        _check(checks, "current_availability_available", "availability", "blocker", "Current game availability is required but unavailable.", observed=deepcopy(status))
        return
    if not require_current_availability and not available:
        _check(checks, "current_availability_available", "availability", "info", "Current game availability is not required by this gate.", observed=deepcopy(status))
        return
    _check(checks, "current_availability_available", "availability", "pass", "Current game availability context is available.")

    summary = snapshot.get("availability_summary")
    if not isinstance(summary, dict):
        _check(checks, "availability_summary", "availability", "blocker" if require_current_availability else "warning", "Step 4W availability summary is missing.")
        return
    roster_match = summary.get("focal_player_current_roster_match") is True
    _check(
        checks,
        "focal_current_roster_match",
        "availability",
        "pass" if roster_match else ("blocker" if require_current_availability else "warning"),
        "Focal player is verified on the current roster snapshot." if roster_match else "Focal player is not verified on the current roster snapshot.",
        observed=summary.get("focal_player_current_roster_match"),
    )

    focal = summary.get("focal_player_availability")
    if not isinstance(focal, dict):
        _check(checks, "focal_availability_row", "availability", "blocker" if require_current_availability else "warning", "Focal player availability row is missing from the current roster snapshot.")
    else:
        status_text = (_clean(focal.get("injury_report_status")) or "").casefold()
        availability_class = (_clean(focal.get("availability_class")) or "").casefold()
        blocking = focal.get("availability_blocking") is True or status_text == "out" or availability_class == "unavailable"
        uncertain = focal.get("availability_uncertain") is True or status_text in {"questionable", "doubtful", "probable"} or availability_class in {"uncertain", "probable"}
        if blocking:
            _check(checks, "focal_player_game_availability", "availability", "blocker", "Focal player is listed unavailable/Out for the game.", observed=deepcopy(focal))
        elif uncertain:
            _check(checks, "focal_player_game_availability", "availability", "warning", "Focal player carries a non-final availability designation.", observed=deepcopy(focal))
        else:
            _check(checks, "focal_player_game_availability", "availability", "pass", "Focal player is not listed with a blocking/uncertain availability designation.", observed=deepcopy(focal))

    game_availability = _dig(snapshot, "inputs", "game_availability")
    verification = game_availability.get("verification") if isinstance(game_availability, dict) else None
    near_tip = hours_to_tip is not None and hours_to_tip <= NEAR_TIP_HOURS
    if isinstance(verification, dict):
        report_present = verification.get("injury_report_game_present") is True
        submitted = verification.get("injury_report_submission_complete") is True
        for check_id, value, label in (
            ("injury_report_game_present", report_present, "Game is present in the official injury-report evidence"),
            ("injury_report_submission_complete", submitted, "Both teams have complete injury-report submission evidence"),
        ):
            severity = "pass" if value else ("blocker" if require_current_availability and near_tip else "warning")
            _check(
                checks,
                check_id,
                "availability",
                severity,
                f"{label}." if value else f"{label} is not confirmed.",
                observed=value,
                threshold={"blocking_when_hours_to_tip_lte": NEAR_TIP_HOURS} if not value else None,
            )
    else:
        _check(checks, "injury_report_verification", "availability", "blocker" if require_current_availability and near_tip else "warning", "Game-level injury-report verification object is missing.")

    report = summary.get("injury_report")
    report_timestamp = _parse_dt(report.get("report_timestamp_eastern")) if isinstance(report, dict) else None
    if report_timestamp is None:
        _check(
            checks,
            "injury_report_freshness",
            "freshness",
            "blocker" if require_current_availability and near_tip else "warning",
            "Official injury-report timestamp is missing or invalid.",
            observed=deepcopy(report),
        )
        return
    age_hours = (evaluated_at - report_timestamp).total_seconds() / 3600.0
    if age_hours < -(FUTURE_TIMESTAMP_TOLERANCE_MINUTES / 60.0):
        _check(checks, "injury_report_freshness", "freshness", "blocker", "Official injury-report timestamp is implausibly in the future.", observed={"age_hours": round(age_hours, 3)})
    elif near_tip and age_hours > BLOCKING_INJURY_REPORT_AGE_HOURS:
        _check(
            checks,
            "injury_report_freshness",
            "freshness",
            "blocker",
            "Official injury report is too old for a game inside the near-tip window.",
            observed={"age_hours": round(age_hours, 3), "hours_to_tip": round(hours_to_tip or 0.0, 3)},
            threshold={"blocking_age_hours": BLOCKING_INJURY_REPORT_AGE_HOURS, "near_tip_hours": NEAR_TIP_HOURS},
        )
    elif age_hours > WARNING_INJURY_REPORT_AGE_HOURS:
        _check(
            checks,
            "injury_report_freshness",
            "freshness",
            "warning",
            "Official injury report is older than the preferred freshness window.",
            observed={"age_hours": round(age_hours, 3), "hours_to_tip": round(hours_to_tip, 3) if hours_to_tip is not None else None},
            threshold={"warning_age_hours": WARNING_INJURY_REPORT_AGE_HOURS},
        )
    else:
        _check(checks, "injury_report_freshness", "freshness", "pass", "Official injury report is within the preferred freshness window.", observed={"age_hours": round(age_hours, 3)})


def _optional_component_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    groups = {
        "shot_context": (
            "player_recent_shot_chart",
            "player_vs_opponent_shot_chart",
            "opponent_defense_by_shot_zone",
        ),
        "advanced_context": ("player_advanced", "team_advanced", "opponent_advanced"),
        "officiating_context": ("game_whistle_context",),
    }
    statuses = snapshot.get("component_status")
    if not isinstance(statuses, dict):
        _check(checks, "optional_component_status_object", "optional_components", "warning", "Step 4W optional component status object is missing.")
        return
    for group, names in groups.items():
        requested = []
        unavailable = []
        for name in names:
            row = statuses.get(name)
            if isinstance(row, dict) and row.get("requested") is True:
                requested.append(name)
                if row.get("available") is not True:
                    unavailable.append(name)
        if not requested:
            _check(checks, f"{group}_coverage", "optional_components", "info", f"{group.replace('_', ' ').title()} was not requested.")
        elif unavailable:
            _check(
                checks,
                f"{group}_coverage",
                "optional_components",
                "warning",
                f"Some requested {group.replace('_', ' ')} components are unavailable.",
                observed={"requested": requested, "unavailable": unavailable},
            )
        else:
            _check(checks, f"{group}_coverage", "optional_components", "pass", f"All requested {group.replace('_', ' ')} components are available.", observed={"requested": requested})


def _source_timestamp_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]], evaluated_at: datetime) -> None:
    rows = snapshot.get("source_timestamps")
    if not isinstance(rows, list):
        _check(checks, "source_timestamp_collection", "freshness", "warning", "Step 4W source timestamp collection is missing or malformed.")
        return
    invalid = []
    future = []
    parsed_count = 0
    for row in rows:
        if not isinstance(row, dict):
            invalid.append(row)
            continue
        path = _clean(row.get("path")) or "unknown"
        if not (path.endswith("retrieved_at_utc") or path.endswith("report_timestamp_eastern")):
            continue
        dt = _parse_dt(row.get("value"))
        if dt is None:
            invalid.append({"path": path, "value": row.get("value")})
            continue
        parsed_count += 1
        minutes_future = (dt - evaluated_at).total_seconds() / 60.0
        if minutes_future > FUTURE_TIMESTAMP_TOLERANCE_MINUTES:
            future.append({"path": path, "value": row.get("value"), "minutes_in_future": round(minutes_future, 3)})
    if future:
        _check(checks, "source_timestamp_clock_skew", "freshness", "blocker", "One or more captured source timestamps are implausibly in the future.", observed=future, threshold={"tolerance_minutes": FUTURE_TIMESTAMP_TOLERANCE_MINUTES})
    elif invalid:
        _check(checks, "source_timestamp_parse", "freshness", "warning", "One or more captured source timestamps could not be parsed.", observed=invalid)
    else:
        _check(checks, "source_timestamp_parse", "freshness", "pass", "Captured retrieval/report timestamps are parseable and not implausibly future-dated.", observed={"parsed_timestamp_count": parsed_count})


def evaluate_projection_input_snapshot(
    snapshot: dict[str, Any],
    *,
    evaluated_at_utc: datetime | None = None,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError("WNBA Step 4X snapshot must be an object.")
    require_current_availability = _bool(require_current_availability, "require_current_availability")
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)
    if evaluated_at_utc is None:
        evaluated_at = _utc_now()
    elif not isinstance(evaluated_at_utc, datetime):
        raise ValueError("WNBA evaluated_at_utc must be a datetime when supplied.")
    elif evaluated_at_utc.tzinfo is None:
        evaluated_at = evaluated_at_utc.replace(tzinfo=timezone.utc)
    else:
        evaluated_at = evaluated_at_utc.astimezone(timezone.utc)

    checks: list[dict[str, Any]] = []
    schema_ok = snapshot.get("schema_version") == SNAPSHOT_SCHEMA_VERSION
    _check(
        checks,
        "snapshot_schema_version",
        "snapshot_integrity",
        "pass" if schema_ok else "blocker",
        "Step 4W snapshot schema version is supported." if schema_ok else "Step 4W snapshot schema version is unsupported.",
        observed=snapshot.get("schema_version"),
        threshold={"required_schema_version": SNAPSHOT_SCHEMA_VERSION},
    )

    content_hash = _clean(snapshot.get("content_sha256"))
    expected_hash = _canonical_hash(_snapshot_hash_content(snapshot))
    hash_ok = content_hash is not None and len(content_hash) == 64 and content_hash == expected_hash
    _check(
        checks,
        "snapshot_content_hash",
        "snapshot_integrity",
        "pass" if hash_ok else "blocker",
        "Step 4W content hash matches the captured input package." if hash_ok else "Step 4W content hash does not match the captured input package.",
        observed={"provided": content_hash, "recomputed": expected_hash},
    )

    _required_core_checks(snapshot, checks)
    _snapshot_age_checks(snapshot, checks, evaluated_at, max_snapshot_age_minutes)
    hours_to_tip = _game_identity_checks(snapshot, checks, evaluated_at)
    _opportunity_checks(snapshot, checks)
    _availability_checks(snapshot, checks, evaluated_at, hours_to_tip, require_current_availability)
    _optional_component_checks(snapshot, checks)
    _source_timestamp_checks(snapshot, checks, evaluated_at)

    blocker_checks = [row for row in checks if row["severity"] == "blocker"]
    warning_checks = [row for row in checks if row["severity"] == "warning"]
    pass_checks = [row for row in checks if row["severity"] == "pass"]
    info_checks = [row for row in checks if row["severity"] == "info"]
    if blocker_checks:
        readiness = "NOT_READY"
    elif warning_checks:
        readiness = "READY_WITH_WARNINGS"
    else:
        readiness = "READY"

    diagnostic_score = max(0, 100 - 20 * len(blocker_checks) - 4 * len(warning_checks))
    snapshot_id = _clean(snapshot.get("snapshot_id"))
    return {
        "source": READINESS_SOURCE,
        "data_type": "rule_based_model_input_readiness_gate",
        "schema_version": READINESS_SCHEMA_VERSION,
        "evaluated_at_utc": _iso(evaluated_at),
        "readiness": readiness,
        "can_start_projection": readiness != "NOT_READY",
        "diagnostic_data_quality_score": diagnostic_score,
        "score_semantics": "Diagnostic only. Any blocker forces NOT_READY regardless of score.",
        "snapshot_reference": {
            "snapshot_id": snapshot_id,
            "content_sha256": content_hash,
            "captured_at_utc": snapshot.get("captured_at_utc"),
            "finalized_at_utc": snapshot.get("finalized_at_utc"),
            "season": snapshot.get("season"),
            "season_type": snapshot.get("season_type"),
            "game_id": snapshot.get("game_id"),
            "player_id": snapshot.get("player_id"),
            "recent_window_games": snapshot.get("recent_window_games"),
        },
        "requirements": {
            "require_current_availability": require_current_availability,
            "max_snapshot_age_minutes": max_snapshot_age_minutes,
            "minimum_core_game_coverage": MIN_CORE_GAME_COVERAGE,
            "preferred_core_game_coverage": PREFERRED_CORE_GAME_COVERAGE,
            "minimum_feature_eligible_event_share": MIN_FEATURE_ELIGIBLE_SHARE,
            "preferred_feature_eligible_event_share": PREFERRED_FEATURE_ELIGIBLE_SHARE,
            "near_tip_hours": NEAR_TIP_HOURS,
            "warning_injury_report_age_hours": WARNING_INJURY_REPORT_AGE_HOURS,
            "blocking_injury_report_age_hours_near_tip": BLOCKING_INJURY_REPORT_AGE_HOURS,
        },
        "summary": {
            "check_count": len(checks),
            "pass_count": len(pass_checks),
            "warning_count": len(warning_checks),
            "blocker_count": len(blocker_checks),
            "info_count": len(info_checks),
            "blocker_ids": [row["check_id"] for row in blocker_checks],
            "warning_ids": [row["check_id"] for row in warning_checks],
        },
        "blockers": deepcopy(blocker_checks),
        "warnings": deepcopy(warning_checks),
        "checks": checks,
        "guardrails": {
            "gate_does_not_repair_or_impute_inputs": True,
            "gate_does_not_redistribute_missing_teammate_opportunity": True,
            "gate_does_not_create_projected_minutes": True,
            "gate_does_not_create_projected_starters": True,
            "gate_does_not_create_monte_carlo": True,
            "gate_does_not_create_sportsbook_data": True,
            "gate_does_not_create_betting_probability": True,
            "official_defender_matchup_unavailability_is_not_penalized": True,
            "blockers_override_diagnostic_score": True,
        },
        "verification": {
            "step_4w_content_hash_recomputed": True,
            "required_core_identity_checked": True,
            "rotation_and_event_history_coverage_checked": True,
            "feature_eligible_event_share_checked": True,
            "availability_and_roster_state_checked_when_required": True,
            "injury_report_freshness_is_tip_time_aware": True,
            "optional_component_outages_are_reported_not_fabricated": True,
            "readiness_state_is_rule_based": True,
            "no_projection_created": True,
        },
    }


def get_player_game_model_input_readiness(
    player_id: int,
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    require_current_availability: bool = True,
    include_shot_context: bool = True,
    include_advanced_context: bool = True,
    include_officiating_context: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    include_snapshot: bool = False,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    require_current_availability = _bool(require_current_availability, "require_current_availability")
    include_shot_context = _bool(include_shot_context, "include_shot_context")
    include_advanced_context = _bool(include_advanced_context, "include_advanced_context")
    include_officiating_context = _bool(include_officiating_context, "include_officiating_context")
    include_snapshot = _bool(include_snapshot, "include_snapshot")
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)

    try:
        snapshot = get_player_game_projection_input_snapshot(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            include_current_availability=require_current_availability,
            include_shot_context=include_shot_context,
            include_advanced_context=include_advanced_context,
            include_officiating_context=include_officiating_context,
        )
    except WNBAProjectionInputSnapshotNotFoundError as exc:
        raise WNBAModelInputReadinessNotFoundError(str(exc)) from exc
    except WNBAProjectionInputSnapshotUpstreamError as exc:
        raise WNBAModelInputReadinessUpstreamError(str(exc)) from exc

    gate = evaluate_projection_input_snapshot(
        snapshot,
        require_current_availability=require_current_availability,
        max_snapshot_age_minutes=max_snapshot_age_minutes,
    )
    gate["snapshot_included"] = include_snapshot
    if include_snapshot:
        gate["snapshot"] = snapshot
    return gate
