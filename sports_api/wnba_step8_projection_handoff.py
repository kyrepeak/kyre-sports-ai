"""Step 8A: frozen Step-7G to projection-model handoff contract.

This layer is the first boundary after the certified Step-7G first-party release.
It does not create a projection, projected minutes, Monte Carlo simulation,
sportsbook probability, or persistence record. It only validates that a fresh
Step-4X readiness report and its included Step-4W content-addressed snapshot are
eligible to cross into the future Step-8 model layer.

The handoff is deliberately bound to the exact frozen Step-7G release identity.
Step 8 must not silently consume a different release, an unresolved candidate
scope, a blocked readiness state, an unexpected warning, or a tampered snapshot.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Mapping

from sports_api import wnba_step7g_release_freeze as step7g_freeze
import sports_api.wnba_step7g_first_party_integration as step7g_integration
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)

SOURCE = "Kyre Sports API WNBA Step 8A certified projection handoff"
SCHEMA_VERSION = "wnba_step_8a_v1"
HANDOFF_RELEASE_ID = "wnba_step8_projection_handoff_2026_regular_season_v1"
STEP7G_FROZEN_HEAD_SHA = "1d1842937b51695d5776b73fc0cca55e407ecf39"
STEP8_PROJECTION_HANDOFF_ENABLED_ENV = "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED"
RECENT_WINDOW_GAMES = 5

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep8ProjectionHandoffDisabledError(RuntimeError):
    """Raised when Step 8A is not explicitly enabled for the current process."""


class WNBAStep8ProjectionHandoffNotReadyError(RuntimeError):
    """Raised when the frozen Step-7G readiness contract does not authorize projection."""


class WNBAStep8ProjectionHandoffUpstreamError(RuntimeError):
    """Raised when the certified Step-7G handoff cannot be constructed safely."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step8_projection_handoff_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP8_PROJECTION_HANDOFF_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep8ProjectionHandoffDisabledError(
            "Step 8A refuses to run while production switches are enabled: "
            + ", ".join(bad)
        )


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


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_hash_content(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct the exact frozen Step-4W content-addressed hash surface."""
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


def recompute_step4w_snapshot_content_sha256(snapshot: Mapping[str, Any]) -> str:
    return _canonical_hash(_snapshot_hash_content(snapshot))


def _check_by_id(readiness: Mapping[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = readiness.get("checks")
    if not isinstance(checks, list):
        return None
    matches = [
        row for row in checks
        if isinstance(row, dict) and row.get("check_id") == check_id
    ]
    if len(matches) > 1:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            f"Step 8A readiness contains duplicate check ID {check_id!r}."
        )
    return deepcopy(matches[0]) if matches else None


def _validate_step7g_release_status(status: Mapping[str, Any]) -> dict[str, Any]:
    if step7g_freeze.DEFAULT_ENABLED is not False:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Frozen Step-7G release unexpectedly became default-enabled."
        )
    if step7g_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Frozen Step-7G release unexpectedly allows production activation."
        )
    if status.get("model_version") != step7g_freeze.INTEGRATION_VERSION:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A integration version does not match the frozen Step-7G release."
        )
    if status.get("candidate_scope") != {}:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            f"Step 8A refuses unresolved Step-7G candidate scope: {status.get('candidate_scope')!r}."
        )
    if status.get("all_core_seams_installed") is not True:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A requires all certified Step-7G first-party seams to be installed."
        )
    scope = status.get("certified_scope")
    if not isinstance(scope, dict):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-7G certified scope is malformed."
        )
    for key, expected in step7g_freeze.CERTIFIED_SCOPE.items():
        if scope.get(key) is not expected:
            raise WNBAStep8ProjectionHandoffUpstreamError(
                f"Step 8A frozen certified scope mismatch for {key!r}."
            )
    return {
        "release_id": step7g_freeze.RELEASE_ID,
        "integration_version": step7g_freeze.INTEGRATION_VERSION,
        "frozen_head_sha": STEP7G_FROZEN_HEAD_SHA,
        "certified_baseline_sha": step7g_freeze.CERTIFIED_BASELINE_SHA,
        "season": step7g_freeze.SEASON,
        "season_type": step7g_freeze.SEASON_TYPE,
        "candidate_scope": {},
        "certified_scope": deepcopy(scope),
    }


def _validate_snapshot(
    snapshot: Mapping[str, Any],
    snapshot_reference: Mapping[str, Any],
    *,
    expected_player_id: int,
    expected_game_id: str,
) -> dict[str, Any]:
    if snapshot.get("data_type") != "content_addressed_pre_model_projection_input_snapshot":
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A received the wrong Step-4W snapshot data type."
        )
    if snapshot.get("schema_version") != "wnba_step_4w_v1":
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A received an unsupported Step-4W snapshot schema."
        )
    if _clean(snapshot.get("game_id")) != expected_game_id:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot returned the wrong game ID."
        )
    if _to_int(snapshot.get("player_id")) != expected_player_id:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot returned the wrong player ID."
        )
    if snapshot.get("season") != step7g_freeze.SEASON:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot returned the wrong season."
        )
    if snapshot.get("season_type") != step7g_freeze.SEASON_TYPE:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot returned the wrong season type."
        )
    if snapshot.get("recent_window_games") != RECENT_WINDOW_GAMES:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot returned the wrong recent-game window."
        )

    content_sha = _clean(snapshot.get("content_sha256"))
    if content_sha is None or len(content_sha) != 64:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot content hash is malformed."
        )
    try:
        int(content_sha, 16)
    except ValueError as exc:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot content hash is not hexadecimal."
        ) from exc
    recomputed = recompute_step4w_snapshot_content_sha256(snapshot)
    if recomputed != content_sha:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A independently recomputed a different Step-4W snapshot hash."
        )

    for key in (
        "snapshot_id",
        "content_sha256",
        "season",
        "season_type",
        "game_id",
        "player_id",
        "recent_window_games",
    ):
        if snapshot_reference.get(key) != snapshot.get(key):
            raise WNBAStep8ProjectionHandoffUpstreamError(
                f"Step 8A readiness snapshot reference disagrees on {key!r}."
            )

    guardrails = snapshot.get("guardrails")
    if not isinstance(guardrails, dict):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4W snapshot guardrails are missing."
        )
    for key in (
        "snapshot_is_pre_model_input_not_projection",
        "no_projected_minutes_created",
        "no_projected_starters_created",
        "no_monte_carlo_created",
        "no_sportsbook_data_created",
        "no_betting_probability_created",
    ):
        if guardrails.get(key) is not True:
            raise WNBAStep8ProjectionHandoffUpstreamError(
                f"Step 8A Step-4W guardrail {key!r} is not true."
            )

    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "content_sha256": content_sha,
        "captured_at_utc": snapshot.get("captured_at_utc"),
        "finalized_at_utc": snapshot.get("finalized_at_utc"),
        "game_id": expected_game_id,
        "player_id": expected_player_id,
        "season": snapshot.get("season"),
        "season_type": snapshot.get("season_type"),
        "recent_window_games": snapshot.get("recent_window_games"),
    }


def validate_step7g_projection_handoff(
    readiness: Mapping[str, Any],
    integration_status: Mapping[str, Any],
    *,
    expected_player_id: int,
    expected_game_id: str,
) -> dict[str, Any]:
    """Validate a frozen Step-7G readiness payload into a Step-8A handoff package."""
    expected_player_id = _positive_player_id(expected_player_id)
    expected_game_id = _game_id(expected_game_id)
    if not isinstance(readiness, Mapping):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A readiness payload must be an object."
        )
    release = _validate_step7g_release_status(integration_status)

    if readiness.get("data_type") != "rule_based_model_input_readiness_gate":
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A received the wrong Step-4X readiness data type."
        )
    if readiness.get("schema_version") != "wnba_step_4x_v1":
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A received an unsupported Step-4X readiness schema."
        )
    if readiness.get("readiness") not in {"READY", "READY_WITH_WARNINGS"}:
        raise WNBAStep8ProjectionHandoffNotReadyError(
            f"Step 8A refuses non-startable readiness state {readiness.get('readiness')!r}."
        )
    if readiness.get("can_start_projection") is not True:
        raise WNBAStep8ProjectionHandoffNotReadyError(
            "Step 8A Step-4X gate does not authorize projection start."
        )

    summary = readiness.get("summary")
    if not isinstance(summary, dict):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4X readiness summary is malformed."
        )
    blocker_ids = list(summary.get("blocker_ids") or [])
    if summary.get("blocker_count") != 0 or blocker_ids:
        raise WNBAStep8ProjectionHandoffNotReadyError(
            f"Step 8A refuses readiness blockers: {blocker_ids!r}."
        )
    warning_ids = list(summary.get("warning_ids") or [])
    if len(warning_ids) != len(set(warning_ids)):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A readiness contains duplicate warning IDs."
        )
    unexpected_warnings = set(warning_ids) - step7g_freeze.ALLOWED_NON_BLOCKING_WARNING_IDS
    if unexpected_warnings:
        raise WNBAStep8ProjectionHandoffNotReadyError(
            "Step 8A refuses warnings outside the frozen Step-7G allowlist: "
            + ", ".join(sorted(unexpected_warnings))
        )

    required_checks: dict[str, dict[str, Any]] = {}
    for check_id in step7g_freeze.REQUIRED_RELEASE_DEFAULT_CHECKS:
        row = _check_by_id(readiness, check_id)
        if row is None:
            raise WNBAStep8ProjectionHandoffNotReadyError(
                f"Step 8A is missing required frozen readiness check {check_id!r}."
            )
        if row.get("severity") != "pass" or row.get("blocking") is not False:
            raise WNBAStep8ProjectionHandoffNotReadyError(
                f"Step 8A required readiness check {check_id!r} did not pass."
            )
        required_checks[check_id] = {
            "severity": "pass",
            "blocking": False,
            "observed": deepcopy(row.get("observed")),
        }

    if readiness.get("snapshot_included") is not True:
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A requires the full Step-4W snapshot to be included."
        )
    snapshot = readiness.get("snapshot")
    snapshot_reference = readiness.get("snapshot_reference")
    if not isinstance(snapshot, dict) or not isinstance(snapshot_reference, dict):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A readiness is missing its Step-4W snapshot or reference."
        )
    validated_snapshot_reference = _validate_snapshot(
        snapshot,
        snapshot_reference,
        expected_player_id=expected_player_id,
        expected_game_id=expected_game_id,
    )

    readiness_guardrails = readiness.get("guardrails")
    verification = readiness.get("verification")
    if not isinstance(readiness_guardrails, dict) or not isinstance(verification, dict):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A Step-4X guardrails or verification are missing."
        )
    for key in (
        "gate_does_not_repair_or_impute_inputs",
        "gate_does_not_create_projected_minutes",
        "gate_does_not_create_projected_starters",
        "gate_does_not_create_monte_carlo",
        "gate_does_not_create_sportsbook_data",
        "gate_does_not_create_betting_probability",
        "blockers_override_diagnostic_score",
    ):
        if readiness_guardrails.get(key) is not True:
            raise WNBAStep8ProjectionHandoffUpstreamError(
                f"Step 8A Step-4X guardrail {key!r} is not true."
            )
    for key in (
        "step_4w_content_hash_recomputed",
        "required_core_identity_checked",
        "availability_and_roster_state_checked_when_required",
        "optional_component_outages_are_reported_not_fabricated",
        "readiness_state_is_rule_based",
        "no_projection_created",
    ):
        if verification.get(key) is not True:
            raise WNBAStep8ProjectionHandoffUpstreamError(
                f"Step 8A Step-4X verification {key!r} is not true."
            )

    focal = snapshot.get("focal_identity")
    game_identity = snapshot.get("game_identity")
    if not isinstance(focal, dict) or not isinstance(game_identity, dict):
        raise WNBAStep8ProjectionHandoffUpstreamError(
            "Step 8A snapshot is missing focal or game identity."
        )

    readiness_proof = {
        "schema_version": readiness.get("schema_version"),
        "readiness": readiness.get("readiness"),
        "can_start_projection": True,
        "diagnostic_data_quality_score": readiness.get("diagnostic_data_quality_score"),
        "summary": {
            "check_count": summary.get("check_count"),
            "pass_count": summary.get("pass_count"),
            "warning_count": summary.get("warning_count"),
            "blocker_count": 0,
            "blocker_ids": [],
            "warning_ids": warning_ids,
        },
        "required_release_checks": required_checks,
    }
    hash_content = {
        "schema_version": SCHEMA_VERSION,
        "handoff_release_id": HANDOFF_RELEASE_ID,
        "upstream_release": release,
        "snapshot_reference": validated_snapshot_reference,
        "readiness_proof": readiness_proof,
        "game_identity": deepcopy(game_identity),
        "focal_identity": deepcopy(focal),
        "snapshot": deepcopy(snapshot),
    }
    handoff_sha = _canonical_hash(hash_content)

    return {
        "source": SOURCE,
        "data_type": "certified_pre_projection_model_handoff",
        "schema_version": SCHEMA_VERSION,
        "handoff_release_id": HANDOFF_RELEASE_ID,
        "handoff_id": f"wnba-8a-{expected_game_id}-{expected_player_id}-{handoff_sha[:16]}",
        "handoff_content_sha256": handoff_sha,
        "created_at_utc": _utc_now_iso(),
        "projection_execution_authorized": True,
        "production_activation_allowed": False,
        "upstream_release": release,
        "snapshot_reference": validated_snapshot_reference,
        "readiness_proof": readiness_proof,
        "game_identity": deepcopy(game_identity),
        "focal_identity": deepcopy(focal),
        "snapshot": deepcopy(snapshot),
        "guardrails": {
            "step7g_frozen_release_identity_required": True,
            "step7g_candidate_scope_must_be_empty": True,
            "step4w_snapshot_hash_independently_recomputed": True,
            "step4x_required_release_checks_must_pass": True,
            "step4x_blockers_forbid_handoff": True,
            "unexpected_warnings_forbid_handoff": True,
            "handoff_is_not_projection": True,
            "no_projected_minutes_created": True,
            "no_projected_starters_created": True,
            "no_monte_carlo_created": True,
            "no_sportsbook_data_created": True,
            "no_betting_probability_created": True,
            "no_persistence_created": True,
            "no_production_activation_created": True,
        },
        "verification": {
            "requested_game_identity_matches_snapshot": True,
            "requested_player_identity_matches_snapshot": True,
            "snapshot_reference_matches_included_snapshot": True,
            "snapshot_content_hash_matches_independent_recompute": True,
            "all_frozen_release_default_checks_pass": True,
            "zero_blockers": True,
            "warnings_within_frozen_allowlist": True,
            "projection_start_authorized_only_by_step4x": True,
            "no_model_output_created": True,
        },
    }


def get_player_game_step8_projection_handoff(
    player_id: int,
    game_id: str,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a live Step-8A handoff from the exact frozen Step-7G release."""
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    source_env = os.environ if env is None else env
    if not step8_projection_handoff_enabled(source_env):
        raise WNBAStep8ProjectionHandoffDisabledError(
            f"Step 8A is disabled. Set {STEP8_PROJECTION_HANDOFF_ENABLED_ENV}=true only for an authorized isolated process."
        )
    _assert_safe_environment(source_env)
    if not step7g_integration.step7g_first_party_enabled(source_env):
        raise WNBAStep8ProjectionHandoffDisabledError(
            "Step 8A requires the certified Step-7G first-party integration to be explicitly enabled in the same isolated process."
        )

    status = step7g_integration.install_step7g_first_party_integration(source_env)
    _validate_step7g_release_status(status)
    try:
        readiness = get_player_game_model_input_readiness(
            player_id,
            game_id,
            step7g_freeze.SEASON,
            season_type=step7g_freeze.SEASON_TYPE,
            last_n_games=RECENT_WINDOW_GAMES,
            require_current_availability=True,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=True,
            max_snapshot_age_minutes=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
            include_snapshot=True,
        )
    except WNBAModelInputReadinessNotFoundError as exc:
        raise WNBAStep8ProjectionHandoffNotReadyError(str(exc)) from exc
    except WNBAModelInputReadinessUpstreamError as exc:
        raise WNBAStep8ProjectionHandoffUpstreamError(str(exc)) from exc

    return validate_step7g_projection_handoff(
        readiness,
        status,
        expected_player_id=player_id,
        expected_game_id=game_id,
    )
