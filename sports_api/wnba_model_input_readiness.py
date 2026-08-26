"""Step 4X: WNBA model-input readiness and data-quality gate.

Evaluates a frozen Step 4W snapshot before any projection model may run.
The gate never repairs, imputes, redistributes, or projects missing data.

States:
- READY: no blockers and no warnings
- READY_WITH_WARNINGS: no blockers, one or more warnings
- NOT_READY: one or more blockers

The diagnostic score is informational only; any blocker forces NOT_READY.
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
    pass


class WNBAModelInputReadinessNotFoundError(LookupError):
    pass


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


def _add(
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


def _coverage(
    checks: list[dict[str, Any]],
    check_id: str,
    label: str,
    observed_games: int | None,
    requested_games: int,
) -> None:
    share = _ratio(observed_games, requested_games)
    observed = {
        "observed_games": observed_games,
        "requested_games": requested_games,
        "coverage": share,
    }
    if share is None or observed_games is None or observed_games <= 0:
        _add(checks, check_id, "historical_coverage", "blocker", f"{label} has no usable recent-game coverage.", observed=observed)
    elif share < MIN_CORE_GAME_COVERAGE:
        _add(
            checks,
            check_id,
            "historical_coverage",
            "blocker",
            f"{label} covers too little of the requested recent window.",
            observed=observed,
            threshold={"minimum_coverage": MIN_CORE_GAME_COVERAGE},
        )
    elif share < PREFERRED_CORE_GAME_COVERAGE:
        _add(
            checks,
            check_id,
            "historical_coverage",
            "warning",
            f"{label} covers less than the preferred recent window.",
            observed=observed,
            threshold={"preferred_coverage": PREFERRED_CORE_GAME_COVERAGE},
        )
    else:
        _add(
            checks,
            check_id,
            "historical_coverage",
            "pass",
            f"{label} recent-game coverage is sufficient.",
            observed=observed,
            threshold={"preferred_coverage": PREFERRED_CORE_GAME_COVERAGE},
        )


def _integrity_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    schema_ok = snapshot.get("schema_version") == SNAPSHOT_SCHEMA_VERSION
    _add(
        checks,
        "snapshot_schema_version",
        "snapshot_integrity",
        "pass" if schema_ok else "blocker",
        "Step 4W snapshot schema is supported." if schema_ok else "Step 4W snapshot schema is unsupported.",
        observed=snapshot.get("schema_version"),
        threshold={"required_schema_version": SNAPSHOT_SCHEMA_VERSION},
    )

    provided = _clean(snapshot.get("content_sha256"))
    recomputed = _canonical_hash(_snapshot_hash_content(snapshot))
    hash_ok = provided is not None and len(provided) == 64 and provided == recomputed
    _add(
        checks,
        "snapshot_content_hash",
        "snapshot_integrity",
        "pass" if hash_ok else "blocker",
        "Step 4W content hash matches the hash-covered package." if hash_ok else "Step 4W content hash does not match the hash-covered package.",
        observed={"provided": provided, "recomputed": recomputed},
    )

    verification = snapshot.get("verification")
    required = (
        "required_step_4v_opportunity_available",
        "required_official_game_schedule_rest_travel_available",
        "focal_latest_observed_team_is_in_requested_game",
        "opponent_resolved_from_official_game_identity",
        "content_hash_created",
    )
    failed = required if not isinstance(verification, dict) else tuple(
        key for key in required if verification.get(key) is not True
    )
    _add(
        checks,
        "step_4w_required_verification",
        "required_core",
        "blocker" if failed else "pass",
        "Step 4W required verification failed." if failed else "Step 4W required verification passed.",
        observed={"failed_flags": list(failed)},
    )

    guardrails = snapshot.get("guardrails")
    required_guardrails = (
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
    failed_guardrails = required_guardrails if not isinstance(guardrails, dict) else tuple(
        key for key in required_guardrails if guardrails.get(key) is not True
    )
    _add(
        checks,
        "pre_model_guardrails",
        "required_core",
        "blocker" if failed_guardrails else "pass",
        "Step 4W pre-model guardrails are incomplete." if failed_guardrails else "Step 4W pre-model guardrails are intact.",
        observed={"failed_flags": list(failed_guardrails)},
    )


def _freshness_checks(
    snapshot: dict[str, Any],
    checks: list[dict[str, Any]],
    evaluated_at: datetime,
    max_snapshot_age_minutes: int,
) -> None:
    captured = _parse_dt(snapshot.get("captured_at_utc"))
    finalized = _parse_dt(snapshot.get("finalized_at_utc"))
    if captured is None or finalized is None:
        _add(checks, "snapshot_timestamps_parse", "freshness", "blocker", "Snapshot capture/finalization timestamps are missing or invalid.")
        return
    _add(
        checks,
        "snapshot_timestamp_order",
        "freshness",
        "pass" if finalized >= captured else "blocker",
        "Snapshot timestamp ordering is valid." if finalized >= captured else "Snapshot finalized before capture time.",
    )
    future_minutes = (captured - evaluated_at).total_seconds() / 60.0
    if future_minutes > FUTURE_TIMESTAMP_TOLERANCE_MINUTES:
        _add(
            checks,
            "snapshot_clock_skew",
            "freshness",
            "blocker",
            "Snapshot capture time is implausibly in the future.",
            observed={"minutes_in_future": round(future_minutes, 3)},
            threshold={"tolerance_minutes": FUTURE_TIMESTAMP_TOLERANCE_MINUTES},
        )
    age_minutes = max(0.0, (evaluated_at - finalized).total_seconds() / 60.0)
    _add(
        checks,
        "snapshot_age",
        "freshness",
        "pass" if age_minutes <= max_snapshot_age_minutes else "blocker",
        "Snapshot is fresh enough for model ingestion." if age_minutes <= max_snapshot_age_minutes else "Snapshot is older than the maximum model-input age.",
        observed={"age_minutes": round(age_minutes, 3)},
        threshold={"max_snapshot_age_minutes": max_snapshot_age_minutes},
    )


def _identity_and_tip(
    snapshot: dict[str, Any],
    checks: list[dict[str, Any]],
    evaluated_at: datetime,
) -> float | None:
    game = snapshot.get("game_identity")
    focal = snapshot.get("focal_identity")
    if not isinstance(game, dict) or not isinstance(focal, dict):
        _add(checks, "game_focal_identity_objects", "identity", "blocker", "Game/focal identity objects are missing or malformed.")
        return None
    away = _clean(game.get("away_team_key"))
    home = _clean(game.get("home_team_key"))
    team = _clean(focal.get("team_key"))
    opponent = _clean(focal.get("opponent_team_key"))
    side = _clean(focal.get("side"))
    player_id = _to_int(focal.get("player_id"))
    top_player_id = _to_int(snapshot.get("player_id"))
    valid = (
        away is not None
        and home is not None
        and away != home
        and team in {away, home}
        and opponent in {away, home}
        and team != opponent
        and side in {"away", "home"}
        and ((side == "away" and team == away and opponent == home) or (side == "home" and team == home and opponent == away))
        and player_id == top_player_id
    )
    _add(
        checks,
        "game_focal_identity_consistency",
        "identity",
        "pass" if valid else "blocker",
        "Player/team/opponent identity is internally consistent." if valid else "Player/team/opponent identity is inconsistent.",
        observed={"away": away, "home": home, "team": team, "opponent": opponent, "side": side, "player_id": player_id},
    )

    change = game.get("schedule_change")
    inactive = isinstance(change, dict) and (change.get("cancelled") or change.get("postponed"))
    _add(
        checks,
        "game_schedule_active",
        "game_status",
        "blocker" if inactive else "pass",
        "Game is cancelled/postponed." if inactive else "Game is not marked cancelled/postponed.",
        observed=deepcopy(change),
    )

    category = (_clean(_dig(game, "status", "category")) or "unknown").casefold()
    if category in {"live", "final", "suspended"}:
        severity = "blocker"
    elif category in {"delayed", "unknown"}:
        severity = "warning"
    elif category == "scheduled":
        severity = "pass"
    else:
        severity = "warning"
    _add(
        checks,
        "pregame_status",
        "game_status",
        severity,
        f"Game status is {category!r}.",
        observed=category,
    )

    tip = _parse_dt(game.get("game_datetime_utc"))
    if tip is None:
        _add(checks, "game_tip_time", "game_status", "blocker", "Official game tip time is missing or invalid.")
        return None
    hours_to_tip = (tip - evaluated_at).total_seconds() / 3600.0
    _add(
        checks,
        "game_tip_time",
        "game_status",
        "pass",
        "Official game tip time is parseable.",
        observed={"game_datetime_utc": game.get("game_datetime_utc"), "hours_to_tip": round(hours_to_tip, 3)},
    )
    if hours_to_tip < -0.25:
        _add(
            checks,
            "game_tip_not_passed",
            "game_status",
            "blocker",
            "Official tip time has already passed for this pregame gate.",
            observed={"hours_to_tip": round(hours_to_tip, 3)},
        )
    else:
        _add(checks, "game_tip_not_passed", "game_status", "pass", "Official tip time has not materially passed.")
    return hours_to_tip


def _opportunity_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    requested = _to_int(snapshot.get("recent_window_games"))
    opportunity = _dig(snapshot, "inputs", "player_opportunity_context")
    if requested is None or requested <= 0:
        _add(checks, "recent_window", "historical_coverage", "blocker", "Requested recent window is invalid.")
        return
    if not isinstance(opportunity, dict):
        _add(checks, "player_opportunity_component", "required_core", "blocker", "Step 4V player opportunity input is missing.")
        return

    _add(
        checks,
        "opportunity_player_identity",
        "identity",
        "pass" if _to_int(opportunity.get("player_id")) == _to_int(snapshot.get("player_id")) else "blocker",
        "Step 4V player identity matches." if _to_int(opportunity.get("player_id")) == _to_int(snapshot.get("player_id")) else "Step 4V player identity disagrees with Step 4W.",
    )
    _add(
        checks,
        "opportunity_team_identity",
        "identity",
        "pass" if _clean(opportunity.get("latest_observed_team_key")) == _clean(_dig(snapshot, "focal_identity", "team_key")) else "blocker",
        "Step 4V team identity matches." if _clean(opportunity.get("latest_observed_team_key")) == _clean(_dig(snapshot, "focal_identity", "team_key")) else "Step 4V team identity disagrees with Step 4W.",
    )

    components = opportunity.get("components")
    if not isinstance(components, dict):
        _add(checks, "opportunity_core_components", "required_core", "blocker", "Step 4V component status is missing.")
    else:
        missing = [
            name
            for name in ("rotation", "event_features")
            if not isinstance(components.get(name), dict) or components[name].get("available") is not True
        ]
        _add(
            checks,
            "opportunity_core_components",
            "required_core",
            "blocker" if missing else "pass",
            "Required Step 4V rotation/event components are unavailable." if missing else "Required Step 4V rotation/event components are available.",
            observed={"missing": missing},
        )
        for name, label in (
            ("starter_bench_role", "Starter/bench role context"),
            ("five_player_lineups", "Five-player lineup context"),
        ):
            row = components.get(name)
            available = isinstance(row, dict) and row.get("available") is True
            _add(
                checks,
                f"optional_{name}",
                "role_lineup_context",
                "pass" if available else "warning",
                f"{label} is available." if available else f"{label} is unavailable.",
                observed=deepcopy(row),
            )

    rotation_games = _to_int(_dig(opportunity, "observed_minutes_opportunity", "source_game_count"))
    stability_games = _to_int(_dig(opportunity, "observed_minutes_opportunity", "tracked_minutes", "stability", "rotation_game_count"))
    _coverage(checks, "rotation_game_coverage", "Official GameRotation history", rotation_games, requested)
    if rotation_games is not None and stability_games is not None and rotation_games != stability_games:
        _add(
            checks,
            "rotation_internal_count_consistency",
            "historical_coverage",
            "blocker",
            "Rotation source-game count disagrees with rotation-stability count.",
            observed={"source_game_count": rotation_games, "stability_game_count": stability_games},
        )
    else:
        _add(checks, "rotation_internal_count_consistency", "historical_coverage", "pass", "Rotation game counts are internally consistent.")

    feature_games = _to_int(_dig(opportunity, "observed_event_opportunity", "feature_game_count"))
    _coverage(checks, "event_feature_game_coverage", "Step 4U event-feature history", feature_games, requested)

    eligible = _to_float(_dig(opportunity, "observed_event_opportunity", "data_quality", "feature_eligible_share_of_selected_lineup_events"))
    if eligible is None or eligible < MIN_FEATURE_ELIGIBLE_SHARE:
        severity = "blocker"
    elif eligible < PREFERRED_FEATURE_ELIGIBLE_SHARE:
        severity = "warning"
    else:
        severity = "pass"
    _add(
        checks,
        "feature_eligible_event_share",
        "event_quality",
        severity,
        "Step 4U feature-eligible event share is sufficient." if severity == "pass" else "Step 4U feature-eligible event share is below the preferred/required level.",
        observed=eligible,
        threshold={"minimum": MIN_FEATURE_ELIGIBLE_SHARE, "preferred": PREFERRED_FEATURE_ELIGIBLE_SHARE},
    )

    cv = _to_float(_dig(opportunity, "observed_minutes_opportunity", "tracked_minutes", "stability", "tracked_minutes_coefficient_of_variation"))
    _add(
        checks,
        "observed_minutes_variability",
        "model_uncertainty",
        "warning" if cv is not None and cv > 0.35 else "pass",
        "Recent observed minutes are highly variable." if cv is not None and cv > 0.35 else "Recent observed minute variability is not unusually high.",
        observed={"coefficient_of_variation": cv},
        threshold={"warning_above": 0.35},
    )


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
        _add(checks, "current_availability_requested", "availability", "blocker", "Current game availability is required but was not requested.")
        return
    if require_current_availability and not available:
        _add(checks, "current_availability_available", "availability", "blocker", "Current game availability is required but unavailable.", observed=deepcopy(status))
        return
    if not require_current_availability and not available:
        _add(checks, "current_availability_available", "availability", "info", "Current game availability is not required by this gate.")
        return
    _add(checks, "current_availability_available", "availability", "pass", "Current game availability is available.")

    raw = _dig(snapshot, "inputs", "game_availability")
    summary = snapshot.get("availability_summary")
    side = _clean(_dig(snapshot, "focal_identity", "side"))
    player_id = _to_int(snapshot.get("player_id"))
    if not isinstance(raw, dict) or side not in {"away", "home"}:
        _add(checks, "availability_raw_focal_context", "availability", "blocker", "Hash-covered game availability cannot resolve the focal side.")
        return
    side_obj = raw.get(side)
    players = side_obj.get("players") if isinstance(side_obj, dict) else None
    if not isinstance(players, list):
        _add(checks, "availability_raw_focal_context", "availability", "blocker", "Hash-covered focal-team availability has no valid player list.")
        return
    focal_rows = [row for row in players if isinstance(row, dict) and _to_int(row.get("player_id")) == player_id]
    if len(focal_rows) > 1:
        _add(checks, "availability_raw_focal_context", "availability", "blocker", "Hash-covered availability contains duplicate focal-player rows.")
        return
    raw_focal = focal_rows[0] if focal_rows else None
    raw_match = raw_focal is not None

    if not isinstance(summary, dict):
        _add(checks, "availability_summary_integrity", "snapshot_integrity", "blocker", "Derived availability summary is missing.")
    else:
        summary_match = summary.get("focal_player_current_roster_match") is True
        summary_focal = summary.get("focal_player_availability")
        raw_report = raw.get("injury_report")
        summary_report = summary.get("injury_report")
        consistent = (
            summary_match == raw_match
            and summary_focal == raw_focal
            and summary_report == raw_report
        )
        _add(
            checks,
            "availability_summary_integrity",
            "snapshot_integrity",
            "pass" if consistent else "blocker",
            "Derived availability summary matches hash-covered game availability." if consistent else "Derived availability summary disagrees with hash-covered game availability.",
        )

    _add(
        checks,
        "focal_current_roster_match",
        "availability",
        "pass" if raw_match else ("blocker" if require_current_availability else "warning"),
        "Focal player is verified on the current roster snapshot." if raw_match else "Focal player is not verified on the current roster snapshot.",
        observed=raw_match,
    )

    if raw_focal is None:
        _add(checks, "focal_availability_row", "availability", "blocker" if require_current_availability else "warning", "Focal player availability row is absent.")
    else:
        text = (_clean(raw_focal.get("injury_report_status")) or "").casefold()
        cls = (_clean(raw_focal.get("availability_class")) or "").casefold()
        blocking = raw_focal.get("availability_blocking") is True or text == "out" or cls == "unavailable"
        uncertain = raw_focal.get("availability_uncertain") is True or text in {"questionable", "doubtful", "probable"} or cls in {"uncertain", "probable"}
        severity = "blocker" if blocking else "warning" if uncertain else "pass"
        _add(
            checks,
            "focal_player_game_availability",
            "availability",
            severity,
            "Focal player is unavailable/Out." if blocking else "Focal player carries a non-final availability designation." if uncertain else "Focal player has no blocking/uncertain availability designation.",
            observed=deepcopy(raw_focal),
        )

    near_tip = hours_to_tip is not None and 0 <= hours_to_tip <= NEAR_TIP_HOURS
    verification = raw.get("verification")
    if isinstance(verification, dict):
        for check_id, key, label in (
            ("injury_report_game_present", "injury_report_game_present", "Game is present in official injury-report evidence"),
            ("injury_report_submission_complete", "injury_report_submission_complete", "Both teams have complete injury-report submission evidence"),
        ):
            value = verification.get(key) is True
            severity = "pass" if value else ("blocker" if require_current_availability and near_tip else "warning")
            _add(checks, check_id, "availability", severity, f"{label}." if value else f"{label} is not confirmed.", observed=value)
    else:
        _add(checks, "injury_report_verification", "availability", "blocker" if require_current_availability and near_tip else "warning", "Game-level injury-report verification is missing.")

    report = raw.get("injury_report")
    report_dt = _parse_dt(report.get("report_timestamp_eastern")) if isinstance(report, dict) else None
    if report_dt is None:
        _add(checks, "injury_report_freshness", "freshness", "blocker" if require_current_availability and near_tip else "warning", "Official injury-report timestamp is missing or invalid.")
        return
    age_hours = (evaluated_at - report_dt).total_seconds() / 3600.0
    if age_hours < -(FUTURE_TIMESTAMP_TOLERANCE_MINUTES / 60.0):
        severity = "blocker"
    elif near_tip and age_hours > BLOCKING_INJURY_REPORT_AGE_HOURS:
        severity = "blocker"
    elif age_hours > WARNING_INJURY_REPORT_AGE_HOURS:
        severity = "warning"
    else:
        severity = "pass"
    _add(
        checks,
        "injury_report_freshness",
        "freshness",
        severity,
        "Official injury-report freshness is acceptable." if severity == "pass" else "Official injury-report freshness is outside the preferred/required window.",
        observed={"age_hours": round(age_hours, 3), "hours_to_tip": round(hours_to_tip, 3) if hours_to_tip is not None else None},
        threshold={"warning_age_hours": WARNING_INJURY_REPORT_AGE_HOURS, "blocking_age_hours_near_tip": BLOCKING_INJURY_REPORT_AGE_HOURS},
    )


def _optional_component_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    groups = {
        "shot_context_coverage": (
            "player_recent_shot_chart",
            "player_vs_opponent_shot_chart",
            "opponent_defense_by_shot_zone",
        ),
        "advanced_context_coverage": (
            "player_advanced",
            "team_advanced",
            "opponent_advanced",
        ),
        "officiating_context_coverage": ("game_whistle_context",),
    }
    statuses = snapshot.get("component_status")
    if not isinstance(statuses, dict):
        _add(checks, "optional_component_status_object", "optional_components", "warning", "Optional component status is missing.")
        return
    for check_id, names in groups.items():
        requested = []
        unavailable = []
        for name in names:
            row = statuses.get(name)
            if isinstance(row, dict) and row.get("requested") is True:
                requested.append(name)
                if row.get("available") is not True:
                    unavailable.append(name)
        if not requested:
            _add(checks, check_id, "optional_components", "info", "This optional component group was not requested.")
        elif unavailable:
            _add(checks, check_id, "optional_components", "warning", "Some requested optional components are unavailable.", observed={"requested": requested, "unavailable": unavailable})
        else:
            _add(checks, check_id, "optional_components", "pass", "All requested optional components in this group are available.", observed={"requested": requested})


def _source_timestamp_checks(snapshot: dict[str, Any], checks: list[dict[str, Any]], evaluated_at: datetime) -> None:
    rows = snapshot.get("source_timestamps")
    if not isinstance(rows, list):
        _add(checks, "source_timestamp_collection", "freshness", "warning", "Source timestamp collection is missing or malformed.")
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
        _add(checks, "source_timestamp_clock_skew", "freshness", "blocker", "One or more source timestamps are implausibly in the future.", observed=future)
    elif invalid:
        _add(checks, "source_timestamp_parse", "freshness", "warning", "One or more source timestamps could not be parsed.", observed=invalid)
    else:
        _add(checks, "source_timestamp_parse", "freshness", "pass", "Captured retrieval/report timestamps are parseable and not future-dated.", observed={"parsed_timestamp_count": parsed_count})


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
    _integrity_checks(snapshot, checks)
    _freshness_checks(snapshot, checks, evaluated_at, max_snapshot_age_minutes)
    hours_to_tip = _identity_and_tip(snapshot, checks, evaluated_at)
    _opportunity_checks(snapshot, checks)
    _availability_checks(snapshot, checks, evaluated_at, hours_to_tip, require_current_availability)
    _optional_component_checks(snapshot, checks)
    _source_timestamp_checks(snapshot, checks, evaluated_at)

    blockers = [row for row in checks if row["severity"] == "blocker"]
    warnings = [row for row in checks if row["severity"] == "warning"]
    passes = [row for row in checks if row["severity"] == "pass"]
    infos = [row for row in checks if row["severity"] == "info"]
    readiness = "NOT_READY" if blockers else "READY_WITH_WARNINGS" if warnings else "READY"
    score = max(0, 100 - 20 * len(blockers) - 4 * len(warnings))

    return {
        "source": READINESS_SOURCE,
        "data_type": "rule_based_model_input_readiness_gate",
        "schema_version": READINESS_SCHEMA_VERSION,
        "evaluated_at_utc": evaluated_at.isoformat(),
        "readiness": readiness,
        "can_start_projection": readiness != "NOT_READY",
        "diagnostic_data_quality_score": score,
        "score_semantics": "Diagnostic only. Any blocker forces NOT_READY regardless of score.",
        "snapshot_reference": {
            "snapshot_id": snapshot.get("snapshot_id"),
            "content_sha256": snapshot.get("content_sha256"),
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
            "pass_count": len(passes),
            "warning_count": len(warnings),
            "blocker_count": len(blockers),
            "info_count": len(infos),
            "blocker_ids": [row["check_id"] for row in blockers],
            "warning_ids": [row["check_id"] for row in warnings],
        },
        "blockers": deepcopy(blockers),
        "warnings": deepcopy(warnings),
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
            "hash_covered_availability_rechecked": True,
            "derived_availability_summary_cross_checked": True,
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
