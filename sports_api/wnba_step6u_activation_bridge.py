"""Step 6U storage-aware activation bridge.

Step 6U binds a verified Step 6T durable-canary evidence hash to the existing
Step 5W pre-activation checkpoint without modifying frozen Step 6K or granting
scheduler authority.  Filesystem selection additionally requires the frozen
Step 6K post-canary preflight to remain green.  Supabase selection leaves Step
6K fail-closed and uses Step 6T only as remote durable-canary evidence.

The public status path is network-free and performs no storage verification.
Explicit bridge verification may invoke the read-only Step 6T verifier, which
can read Supabase when that backend is selected.  Step 6U never writes durable
storage, mutates environment variables, starts the scheduler, calls a
sportsbook, runs Monte Carlo, or authorizes production.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

from sports_api.wnba_staging_activation_gate import get_staging_activation_gate
from sports_api.wnba_step6k_activation_preflight import get_step6k_activation_preflight
from sports_api.wnba_step6q_durable_storage import FILESYSTEM_BACKEND, SUPABASE_BACKEND
from sports_api.wnba_step6t_canary_evidence import (
    WNBAStep6TEvidenceError,
    get_step6t_canary_evidence_status,
    verify_step6t_canary_evidence,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6U storage-aware activation bridge"
MODEL_VERSION = "wnba_step_6u_storage_aware_activation_bridge_v1"
SCHEMA_VERSION = MODEL_VERSION
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class WNBAStep6UActivationBridgeError(RuntimeError):
    pass


class WNBAStep6UActivationBridgeNotReadyError(WNBAStep6UActivationBridgeError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def _validate_evidence(
    evidence: Mapping[str, Any],
    *,
    selected_backend: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    verified = evidence.get("evidence_verified") is True
    _check(
        checks,
        "step_6t_evidence_verified",
        verified,
        "Step 6T durable-canary evidence is verified."
        if verified
        else "Step 6T durable-canary evidence is not verified.",
    )

    evidence_sha = (_clean(evidence.get("evidence_sha256")) or "").casefold()
    evidence_sha_valid = bool(_SHA256_RE.fullmatch(evidence_sha))
    _check(
        checks,
        "step_6t_evidence_hash_valid",
        evidence_sha_valid,
        "Step 6T evidence has a valid SHA-256 identity."
        if evidence_sha_valid
        else "Step 6T evidence SHA-256 is missing or invalid.",
    )

    evidence_does_not_authorize = evidence.get("scheduler_authorized") is False
    _check(
        checks,
        "step_6t_did_not_authorize_scheduler",
        evidence_does_not_authorize,
        "Step 6T remained evidence-only and did not authorize the scheduler."
        if evidence_does_not_authorize
        else "Step 6U refuses evidence that claims scheduler authority.",
    )

    canary = evidence.get("canary_identity") if isinstance(evidence.get("canary_identity"), Mapping) else {}
    backend = _clean(canary.get("storage_backend"))
    backend_matches = backend == selected_backend
    _check(
        checks,
        "step_6t_backend_matches_selected_storage",
        backend_matches,
        "Step 6T canary evidence is bound to the selected durable-storage backend."
        if backend_matches
        else "Step 6T canary evidence backend does not match the selected durable-storage backend.",
    )

    completed = canary.get("status") == "completed"
    _check(
        checks,
        "step_6t_canary_completed",
        completed,
        "Step 6T evidence represents a completed durable canary."
        if completed
        else "Step 6T evidence does not represent a completed durable canary.",
    )

    activation_id = _clean(canary.get("activation_id"))
    _check(
        checks,
        "step_6t_activation_identity_present",
        bool(activation_id),
        "Step 6T evidence has a one-shot canary activation identity."
        if activation_id
        else "Step 6T evidence has no canary activation identity.",
    )

    rollback_verified = canary.get("rollback_verified") is True
    _check(
        checks,
        "step_6t_rollback_verified",
        rollback_verified,
        "Step 6T evidence confirms the rollback path."
        if rollback_verified
        else "Step 6T evidence does not confirm the rollback path.",
    )

    post_write_sha = (_clean(canary.get("post_write_sha256")) or "").casefold()
    canonical_sha = (_clean(canary.get("verified_persistent_feed_sha256")) or "").casefold()
    hashes_valid = bool(_SHA256_RE.fullmatch(post_write_sha) and _SHA256_RE.fullmatch(canonical_sha))
    _check(
        checks,
        "step_6t_durable_hashes_valid",
        hashes_valid,
        "Step 6T evidence includes valid durable-byte and canonical-feed hashes."
        if hashes_valid
        else "Step 6T evidence is missing a valid durable-byte or canonical-feed hash.",
    )

    identity = {
        "storage_backend": backend,
        "activation_id": activation_id,
        "status": canary.get("status"),
        "date": canary.get("date"),
        "season": canary.get("season"),
        "completed_at_utc": canary.get("completed_at_utc"),
        "preexisting_feed": canary.get("preexisting_feed"),
        "pre_write_sha256": canary.get("pre_write_sha256"),
        "post_write_sha256": post_write_sha or None,
        "verified_persistent_feed_sha256": canonical_sha or None,
        "offer_side_count": canary.get("offer_side_count"),
        "rollback_verified": rollback_verified,
        "rollback_mode": canary.get("rollback_mode"),
        "backup_content_sha256": canary.get("backup_content_sha256"),
        "evidence_sha256": evidence_sha or None,
    }
    return checks, identity


def _step5w_preactivation_checks(step5w: Mapping[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    activation_requested = step5w.get("activation_requested") is True
    checkpoint_ready = step5w.get("checkpoint_ready") is True
    live_cycle_allowed = step5w.get("live_cycle_allowed") is True
    checkpoint_sha = (_clean(step5w.get("activation_checkpoint_sha256")) or "").casefold()

    _check(
        checks,
        "step_5w_activation_not_requested_yet",
        not activation_requested,
        "Step 5W remains in the pre-activation phase while the Step 6U bridge checkpoint is frozen."
        if not activation_requested
        else "Step 6U bridge checkpoint must be frozen before Step 5W activation is requested.",
    )
    _check(
        checks,
        "step_5w_preactivation_checkpoint_ready",
        checkpoint_ready,
        "Step 5W immutable pre-activation checkpoint is ready."
        if checkpoint_ready
        else "Step 5W immutable pre-activation checkpoint is not ready.",
    )
    _check(
        checks,
        "step_5w_live_cycle_still_blocked",
        not live_cycle_allowed,
        "Step 5W still blocks live scheduler cycles during bridge creation."
        if not live_cycle_allowed
        else "Step 6U refuses bridge creation after Step 5W already allows live cycles.",
    )
    _check(
        checks,
        "step_5w_checkpoint_hash_valid",
        bool(_SHA256_RE.fullmatch(checkpoint_sha)),
        "Step 5W pre-activation checkpoint has a valid SHA-256 identity."
        if _SHA256_RE.fullmatch(checkpoint_sha)
        else "Step 5W pre-activation checkpoint SHA-256 is missing or invalid.",
    )
    return checks


def _filesystem_step6k_checks(
    step6k: Mapping[str, Any],
    *,
    step5w_checkpoint_sha256: str | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    step6j_verified = step6k.get("step6j_verified") is True
    preactivation_ready = step6k.get("preactivation_ready") is True
    scheduler_blocked = step6k.get("scheduler_authorized") is False
    step6k_step5w = step6k.get("step_5w") if isinstance(step6k.get("step_5w"), Mapping) else {}
    step6k_step5w_sha = (_clean(step6k_step5w.get("activation_checkpoint_sha256")) or "").casefold() or None

    _check(
        checks,
        "filesystem_frozen_step_6k_step6j_verified",
        step6j_verified,
        "Frozen Step 6K independently verifies the filesystem Step 6J canary."
        if step6j_verified
        else "Frozen Step 6K does not independently verify the filesystem Step 6J canary.",
    )
    _check(
        checks,
        "filesystem_frozen_step_6k_preactivation_ready",
        preactivation_ready,
        "Frozen Step 6K post-canary pre-activation gate is ready."
        if preactivation_ready
        else "Frozen Step 6K post-canary pre-activation gate is not ready.",
    )
    _check(
        checks,
        "filesystem_frozen_step_6k_scheduler_still_blocked",
        scheduler_blocked,
        "Frozen Step 6K still blocks scheduler authority during bridge creation."
        if scheduler_blocked
        else "Step 6U refuses a filesystem bridge if Step 6K already authorizes the scheduler.",
    )
    checkpoint_matches = bool(
        step5w_checkpoint_sha256
        and step6k_step5w_sha
        and step6k_step5w_sha == step5w_checkpoint_sha256
    )
    _check(
        checks,
        "filesystem_step_6k_step_5w_checkpoint_matches",
        checkpoint_matches,
        "Frozen Step 6K and Step 5W reference the same pre-activation checkpoint."
        if checkpoint_matches
        else "Frozen Step 6K and Step 5W do not reference the same pre-activation checkpoint.",
    )
    return checks


def build_step6u_activation_bridge(
    *,
    env: Mapping[str, str] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify evidence and build a deterministic pre-activation bridge checkpoint.

    This function is read-only.  If ``evidence`` is omitted it invokes the
    explicit Step 6T verifier, which may perform Supabase reads.  It never
    persists the bridge checkpoint and never grants scheduler authority.
    """
    environment = _environment(env)
    step6t_status = get_step6t_canary_evidence_status(environment)
    selected_backend = _clean(step6t_status.get("selected_backend"))
    if step6t_status.get("configuration_ready") is not True or selected_backend not in {
        FILESYSTEM_BACKEND,
        SUPABASE_BACKEND,
    }:
        raise WNBAStep6UActivationBridgeNotReadyError(
            str(step6t_status.get("configuration_error") or "Step 6T evidence verification is not configured.")
        )

    if evidence is None:
        try:
            evidence = verify_step6t_canary_evidence(environment)
        except WNBAStep6TEvidenceError as exc:
            raise WNBAStep6UActivationBridgeNotReadyError(str(exc)) from exc
    if not isinstance(evidence, Mapping):
        raise WNBAStep6UActivationBridgeNotReadyError("Step 6U requires a Step 6T evidence object.")

    checks, canary_identity = _validate_evidence(evidence, selected_backend=selected_backend)
    step5w = get_staging_activation_gate(env=environment)
    checks.extend(_step5w_preactivation_checks(step5w))

    step5w_checkpoint = (_clean(step5w.get("activation_checkpoint_sha256")) or "").casefold() or None
    legacy_step6k: dict[str, Any] | None = None
    if selected_backend == FILESYSTEM_BACKEND:
        legacy_step6k = get_step6k_activation_preflight(env=environment)
        checks.extend(
            _filesystem_step6k_checks(
                legacy_step6k,
                step5w_checkpoint_sha256=step5w_checkpoint,
            )
        )
    else:
        # Step 6K is intentionally not used as the remote-canary verifier: it is
        # frozen to the filesystem contract.  Step 6U does not supersede that
        # authority because it never grants scheduler permission.
        _check(
            checks,
            "supabase_frozen_step_6k_remains_unmodified",
            True,
            "Supabase bridging leaves frozen Step 6K unchanged and fail-closed; Step 6U creates evidence only.",
        )
        _check(
            checks,
            "supabase_step_6u_does_not_replace_scheduler_authority",
            True,
            "Supabase durable evidence is not converted into scheduler authority by Step 6U.",
        )

    failures = [row for row in checks if row.get("required", True) and row.get("passed") is not True]
    if failures:
        raise WNBAStep6UActivationBridgeNotReadyError(
            "Step 6U activation bridge is not ready: "
            + "; ".join(f"{row['name']}: {row['detail']}" for row in failures)
        )

    evidence_sha = canary_identity.get("evidence_sha256")
    legacy_step6k_checkpoint = (
        _clean((legacy_step6k or {}).get("activation_checkpoint_sha256"))
        if selected_backend == FILESYSTEM_BACKEND
        else None
    )
    checkpoint_payload = {
        "model_version": MODEL_VERSION,
        "storage_backend": selected_backend,
        "step_6t_evidence_sha256": evidence_sha,
        "canary_identity": canary_identity,
        "step_5w_activation_checkpoint_sha256": step5w_checkpoint,
        "filesystem_step_6k_activation_checkpoint_sha256": legacy_step6k_checkpoint,
    }
    bridge_checkpoint = _stable_hash(checkpoint_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6u_activation_bridge",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "selected_backend": selected_backend,
        "bridge_ready": True,
        "bridge_checkpoint_sha256": bridge_checkpoint,
        "scheduler_authorized": False,
        "step_6t_evidence_sha256": evidence_sha,
        "canary_identity": canary_identity,
        "step_5w": {
            "phase": step5w.get("phase"),
            "checkpoint_ready": step5w.get("checkpoint_ready"),
            "live_cycle_allowed": step5w.get("live_cycle_allowed"),
            "activation_checkpoint_sha256": step5w_checkpoint,
        },
        "filesystem_step_6k": (
            {
                "step6j_verified": legacy_step6k.get("step6j_verified"),
                "preactivation_ready": legacy_step6k.get("preactivation_ready"),
                "scheduler_authorized": legacy_step6k.get("scheduler_authorized"),
                "activation_checkpoint_sha256": legacy_step6k_checkpoint,
            }
            if legacy_step6k is not None
            else None
        ),
        "checks": checks,
        "checkpoint_payload": checkpoint_payload,
        "handoff": {
            "bridge_checkpoint_must_be_captured_by_later_operator_step": True,
            "step6k_modified": False,
            "step5w_modified": False,
            "step6k_scheduler_authority_bypassed": False,
            "step5w_explicit_activation_authority_bypassed": False,
            "later_live_operator_step_required": True,
        },
        "safety": {
            "storage_read_performed": True,
            "storage_write_performed": False,
            "remote_storage_read_possible": selected_backend == SUPABASE_BACKEND,
            "remote_storage_write_performed": False,
            "environment_mutation_performed": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "scheduler_authorized_by_step6u": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_value_returned": False,
        },
    }


def get_step6u_activation_bridge_status(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return network-free bridge configuration status without verifying evidence."""
    environment = _environment(env)
    step6t = get_step6t_canary_evidence_status(environment)
    step5w = get_staging_activation_gate(env=environment)
    selected_backend = _clean(step6t.get("selected_backend"))

    configuration_ready = bool(
        step6t.get("configuration_ready") is True
        and step5w.get("activation_requested") is not True
        and step5w.get("checkpoint_ready") is True
        and step5w.get("live_cycle_allowed") is not True
    )
    reasons: list[str] = []
    if step6t.get("configuration_ready") is not True:
        reasons.append(str(step6t.get("configuration_error") or "Step 6T configuration is not ready."))
    if step5w.get("activation_requested") is True:
        reasons.append("Step 5W activation is already requested; freeze the Step 6U bridge before activation.")
    if step5w.get("checkpoint_ready") is not True:
        reasons.append("Step 5W pre-activation checkpoint is not ready.")
    if step5w.get("live_cycle_allowed") is True:
        reasons.append("Step 5W already allows a live cycle; Step 6U bridge creation is pre-activation only.")

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6u_activation_bridge_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "selected_backend": selected_backend,
        "configuration_ready": configuration_ready,
        "bridge_ready": False,
        "bridge_checkpoint_sha256": None,
        "scheduler_authorized": False,
        "verification_required": True,
        "blocking_reasons": reasons,
        "step_6t": {
            "configuration_ready": step6t.get("configuration_ready"),
            "verification_requires_network": step6t.get("verification_requires_network"),
            "verification_is_read_only": step6t.get("verification_is_read_only"),
        },
        "step_5w": {
            "phase": step5w.get("phase"),
            "checkpoint_ready": step5w.get("checkpoint_ready"),
            "live_cycle_allowed": step5w.get("live_cycle_allowed"),
            "activation_checkpoint_sha256": step5w.get("activation_checkpoint_sha256"),
        },
        "handoff": {
            "step6k_modified": False,
            "step5w_modified": False,
            "step6k_scheduler_authority_bypassed": False,
            "step5w_explicit_activation_authority_bypassed": False,
            "later_live_operator_step_required": True,
        },
        "safety": {
            "network_used_by_status": False,
            "storage_read_performed_by_status": False,
            "storage_write_performed_by_status": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "scheduler_authorized_by_step6u": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_value_returned": False,
        },
    }


def require_step6u_bridge_ready(
    *,
    env: Mapping[str, str] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_step6u_activation_bridge(env=env, evidence=evidence)
    if report.get("bridge_ready") is not True or report.get("scheduler_authorized") is not False:
        raise WNBAStep6UActivationBridgeNotReadyError("Step 6U activation bridge is not safely ready.")
    return report
