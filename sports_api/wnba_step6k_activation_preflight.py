"""WNBA Step 6K post-canary activation preflight.

Step 6K is a network-free, read-only safety authority placed in front of the
existing Step 5W scheduler activation gate.  It adds one non-negotiable
production prerequisite: the Step 6J durable DraftKings -> Kyre canary must
have completed successfully, the exact stored bytes must still match its
completion marker, and every temporary Step 6J write switch must be OFF.

Step 6K never provisions infrastructure, mutates Render, writes the market
feed, starts a scheduler, contacts a sportsbook, or runs Monte Carlo.  It only
decides whether the already-existing Step 5W activation path may proceed.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.wnba_staging_activation_gate import get_staging_activation_gate
from sports_api.wnba_step6j_canary_activation import get_step6j_canary_status

MODEL_SOURCE = "Kyre Sports API WNBA Step 6K post-canary activation preflight"
MODEL_VERSION = "wnba_step_6k_post_canary_activation_preflight_v1"
SCHEMA_VERSION = MODEL_VERSION


class WNBAStep6KActivationError(RuntimeError):
    pass


class WNBAStep6KActivationNotReadyError(WNBAStep6KActivationError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    detail: str,
    *,
    required: bool = True,
) -> None:
    checks.append(
        {
            "name": name,
            "required": required,
            "passed": bool(passed),
            "detail": detail,
        }
    )


def _step6j_checks(status: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    state = status.get("canary_state") if isinstance(status.get("canary_state"), Mapping) else {}

    completed = state.get("status") == "completed"
    _check(
        checks,
        "step_6j_canary_completed",
        completed,
        "Step 6J durable canary has a completed terminal marker."
        if completed
        else "Step 6J durable canary has not completed yet.",
    )

    activation_id = _clean(state.get("activation_id"))
    _check(
        checks,
        "step_6j_activation_identity_present",
        bool(activation_id),
        "Step 6J completed marker has a one-shot activation identity."
        if activation_id
        else "Step 6J completed marker has no one-shot activation identity.",
    )

    rollback_verified = state.get("rollback_verified") is True
    _check(
        checks,
        "step_6j_rollback_path_verified",
        rollback_verified,
        "Step 6J verified its pre-write rollback path."
        if rollback_verified
        else "Step 6J rollback-path verification is missing.",
    )

    post_write_sha = (_clean(state.get("post_write_sha256")) or "").casefold() or None
    current_feed_sha = (_clean(status.get("feed_content_sha256")) or "").casefold() or None
    bytes_match = bool(post_write_sha and current_feed_sha and post_write_sha == current_feed_sha)
    _check(
        checks,
        "step_6j_durable_bytes_still_match",
        bytes_match,
        "Current durable feed bytes exactly match the Step 6J completed write hash."
        if bytes_match
        else "Current durable feed bytes do not match the Step 6J completed write hash.",
    )

    persistent_feed_sha = (_clean(state.get("verified_persistent_feed_sha256")) or "").casefold() or None
    _check(
        checks,
        "step_6j_persistent_feed_identity_verified",
        bool(persistent_feed_sha),
        "Step 6J recorded the verified canonical persistent-feed identity."
        if persistent_feed_sha
        else "Step 6J has no verified canonical persistent-feed identity.",
    )

    feed_exists = status.get("feed_exists") is True
    _check(
        checks,
        "step_6j_durable_feed_exists",
        feed_exists,
        "Step 6J durable feed exists."
        if feed_exists
        else "Step 6J durable feed does not exist.",
    )

    temporary_gates_off = (
        status.get("canary_enabled") is False
        and status.get("direct_sync_enabled") is False
        and status.get("reconciled_sync_enabled") is False
    )
    _check(
        checks,
        "step_6j_temporary_write_gates_closed",
        temporary_gates_off,
        "Step 6J canary, direct-sync, and reconciled-sync switches are all OFF."
        if temporary_gates_off
        else "One or more temporary Step 6J write switches are still enabled.",
    )

    identity = {
        "activation_id": activation_id,
        "status": state.get("status"),
        "date": state.get("date"),
        "season": state.get("season"),
        "completed_at_utc": state.get("completed_at_utc"),
        "post_write_sha256": post_write_sha,
        "current_feed_sha256": current_feed_sha,
        "verified_persistent_feed_sha256": persistent_feed_sha,
        "offer_side_count": state.get("offer_side_count"),
        "rollback_verified": rollback_verified,
    }
    return checks, identity


def get_step6k_activation_preflight(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the read-only Step 6K scheduler authorization decision."""
    step6j = get_step6j_canary_status(env=env)
    step5w = get_staging_activation_gate(env=env)

    checks, canary_identity = _step6j_checks(step6j)
    step6j_failures = [row for row in checks if row["required"] and not row["passed"]]
    step6j_verified = not step6j_failures

    activation_requested = step5w.get("activation_requested") is True
    step5w_checkpoint_ready = step5w.get("checkpoint_ready") is True
    step5w_live_cycle_allowed = step5w.get("live_cycle_allowed") is True

    if not activation_requested:
        _check(
            checks,
            "step_5w_preactivation_checkpoint_ready",
            step5w_checkpoint_ready,
            "Existing Step 5W immutable pre-activation checkpoint is ready."
            if step5w_checkpoint_ready
            else "Existing Step 5W pre-activation checkpoint is not ready.",
        )
        preactivation_ready = step6j_verified and step5w_checkpoint_ready
        scheduler_authorized = False
        phase = "post_canary_preactivation_ready" if preactivation_ready else "post_canary_preactivation_blocked"
    else:
        _check(
            checks,
            "step_5w_live_cycle_gate_ready",
            step5w_live_cycle_allowed,
            "Existing Step 5W activation gate permits a live cycle."
            if step5w_live_cycle_allowed
            else "Existing Step 5W activation gate does not permit a live cycle.",
        )
        preactivation_ready = False
        scheduler_authorized = step6j_verified and step5w_live_cycle_allowed
        phase = "scheduler_authorized" if scheduler_authorized else "activation_blocked"

    required_failures = [row for row in checks if row["required"] and not row["passed"]]
    blocking_reasons = [f"{row['name']}: {row['detail']}" for row in required_failures]

    checkpoint_payload = {
        "model_version": MODEL_VERSION,
        "step_6j": canary_identity,
        "step_5w_activation_checkpoint_sha256": step5w.get("activation_checkpoint_sha256"),
    }
    checkpoint_sha = _hash(checkpoint_payload) if step6j_verified else None

    if not step6j_verified:
        deferred_reason = (
            "Step 6J durable canary proof is still missing or invalid. "
            "Paid durable hosting may remain deferred; Step 6K stays fail-closed until that proof exists."
        )
    elif not activation_requested and not step5w_checkpoint_ready:
        deferred_reason = "Step 6J is verified, but the existing Step 5W pre-activation checkpoint is not ready."
    elif activation_requested and not step5w_live_cycle_allowed:
        deferred_reason = "Step 6J is verified, but the existing Step 5W live-cycle gate is not ready."
    else:
        deferred_reason = None

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6k_activation_preflight",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "phase": phase,
        "step6j_verified": step6j_verified,
        "preactivation_ready": preactivation_ready,
        "scheduler_authorized": scheduler_authorized,
        "activation_requested": activation_requested,
        "activation_checkpoint_sha256": checkpoint_sha,
        "deferred_reason": deferred_reason,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "step_6j": canary_identity,
        "step_5w": {
            "phase": step5w.get("phase"),
            "checkpoint_ready": step5w_checkpoint_ready,
            "live_cycle_allowed": step5w_live_cycle_allowed,
            "activation_checkpoint_sha256": step5w.get("activation_checkpoint_sha256"),
            "approved_checkpoint_sha256": step5w.get("approved_checkpoint_sha256"),
        },
        "semantics": {
            "fail_closed": True,
            "step_6j_canary_is_required_before_scheduler_authorization": True,
            "step_6j_exact_durable_bytes_must_still_match": True,
            "step_6j_temporary_write_switches_must_be_off": True,
            "step_5w_remains_explicit_activation_authority": True,
            "readiness_is_network_free": True,
            "readiness_is_read_only": True,
            "render_mutation_performed": False,
            "feed_write_performed": False,
            "scheduler_started_by_preflight": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


def require_step6k_scheduler_authorized(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    report = get_step6k_activation_preflight(env=env)
    if report.get("scheduler_authorized") is not True:
        raise WNBAStep6KActivationNotReadyError(
            "WNBA Step 6K scheduler gate is not authorized: "
            + "; ".join(report.get("blocking_reasons") or [report.get("deferred_reason") or "activation is not ready"])
        )
    return report


def build_step6k_activation_plan(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    report = get_step6k_activation_preflight(env=env)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6k_activation_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "current_phase": report.get("phase"),
        "scheduler_authorized": report.get("scheduler_authorized"),
        "steps": [
            {
                "order": 1,
                "action": "complete_step_6j_durable_canary_when_hosting_is_available",
                "required": True,
                "complete": report.get("step6j_verified") is True,
                "note": "This may remain deferred while paid durable hosting is intentionally postponed.",
            },
            {
                "order": 2,
                "action": "freeze_step_6k_post_canary_checkpoint",
                "required": True,
                "complete": bool(report.get("activation_checkpoint_sha256")),
                "requirement": report.get("activation_checkpoint_sha256") or "blocked until Step 6J is verified",
            },
            {
                "order": 3,
                "action": "use_existing_step_5w_explicit_activation_approval",
                "required": True,
                "complete": report.get("scheduler_authorized") is True,
                "note": "Step 6K does not create a second activation switch; Step 5W remains the explicit operator-approval authority.",
            },
            {
                "order": 4,
                "action": "allow_scheduler_cycles_only_through_step_6k_gate",
                "required": True,
                "complete": report.get("scheduler_authorized") is True,
            },
        ],
        "blocking_reasons": report.get("blocking_reasons"),
        "semantics": report.get("semantics"),
    }
