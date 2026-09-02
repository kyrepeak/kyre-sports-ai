"""MLB Step 18D — final production hardening freeze certificate.

Aggregates the already-read-only Step 18A rollback baseline, Step 18B production
observability report, and Step 18C manual-only incident-response plan into one
final fail-closed Step 18 certificate. This module performs no network I/O and
never mutates Render, GitHub, databases, schedulers, providers, sportsbooks,
models, projections, Monte Carlo, actionable output, or wagers.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "mlb_step18d_final_production_freeze_v1"
CERTIFICATE_VERSION = "mlb_step18d_final_hardening_certificate_v1"
FINAL_MARKER = "MLB_STEP18D_FINAL_PRODUCTION_FREEZE_GREEN"
STEP18A_MERGED_MAIN_SHA = "60f8917e4f963f733759f60b82d7dcf468f776cf"
STEP18B_MERGED_MAIN_SHA = "ae66134026297516aac4e6936b8ac9d8e2302481"
STEP18C_MERGED_MAIN_SHA = "a72fd55f38056f32158bf182f3dc041e5b92b1b1"
CERTIFIED_RENDER_REVISION = "ece3cd2d15d091728fdbe30be774dd9c15e4fe8e"
EXPECTED_BASELINE_TYPE = "mlb_step18a_production_baseline_evidence"
EXPECTED_OBSERVABILITY_TYPE = "mlb_step18b_production_observability"
EXPECTED_RESPONSE_TYPE = "mlb_step18c_incident_response_plan"


class MLBStep18DFinalFreezeError(RuntimeError):
    """Raised when any final Step 18 production-freeze invariant is violated."""


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise MLBStep18DFinalFreezeError(message)


def _hash64(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def build_final_production_freeze(
    *,
    baseline: Mapping[str, Any],
    observability: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    certified_at_utc: str | None = None,
) -> dict[str, Any]:
    """Return the final sanitized Step 18 certificate or fail closed."""
    _assert(isinstance(baseline, Mapping), "Step 18A baseline must be an object")
    _assert(isinstance(observability, Mapping), "Step 18B observability must be an object")
    _assert(isinstance(response_plan, Mapping), "Step 18C response plan must be an object")

    _assert(baseline.get("data_type") == EXPECTED_BASELINE_TYPE, "Step 18A baseline contract drift")
    _assert(baseline.get("state") == "green", "Step 18A baseline is not green")
    _assert(baseline.get("mutation_performed") is False, "Step 18A unexpectedly mutated production")
    baseline_safety = baseline.get("safety") if isinstance(baseline.get("safety"), Mapping) else {}
    _assert(baseline_safety.get("render_mutation_performed") is False, "Step 18A Render mutation drift")
    _assert(baseline_safety.get("provider_calls") == 0, "Step 18A provider boundary drift")
    _assert(baseline_safety.get("sportsbook_calls") == 0, "Step 18A sportsbook boundary drift")
    _assert(baseline_safety.get("actionable_output_enabled") is False, "Step 18A actionable-output drift")
    _assert(baseline_safety.get("wagering_enabled") is False, "Step 18A wagering drift")
    rollback = baseline.get("rollback_target") if isinstance(baseline.get("rollback_target"), Mapping) else {}
    _assert(rollback.get("deployed_revision") == CERTIFIED_RENDER_REVISION, "Step 18A rollback revision drift")
    _assert(rollback.get("merged_main_sha") == "911e917d9d1552289bab5f8c74604103c056982f", "Step 18A Step17B merge lineage drift")
    _assert(_hash64(baseline.get("evidence_sha256")), "Step 18A evidence hash missing")
    _assert(_hash64(rollback.get("safe_config_sha256")), "Step 18A safe-config hash missing")

    _assert(observability.get("data_type") == EXPECTED_OBSERVABILITY_TYPE, "Step 18B observability contract drift")
    _assert(observability.get("state") == "healthy", "Step 18B production state is not healthy")
    _assert(observability.get("healthy") is True, "Step 18B healthy flag is false")
    _assert(observability.get("incident_active") is False, "Step 18B incident is active")
    _assert(observability.get("critical_incident_count") == 0, "Step 18B critical incidents are present")
    _assert(observability.get("warning_incident_count") == 0, "Step 18B warnings are present")
    obs_semantics = observability.get("semantics") if isinstance(observability.get("semantics"), Mapping) else {}
    for key in (
        "render_mutation_performed",
        "database_connection_opened",
        "database_read_performed",
        "database_write_performed",
        "scheduler_started",
        "scheduler_cycle_triggered",
        "provider_network_called",
        "sportsbook_network_called",
        "model_run",
        "projection_run",
        "monte_carlo_run",
        "actionable_output_enabled",
        "wager_action_performed",
        "database_secret_exposed",
        "new_render_service_created",
    ):
        _assert(obs_semantics.get(key) is False, f"Step 18B dangerous semantic drift: {key}")
    _assert(obs_semantics.get("read_only") is True, "Step 18B is not read-only")
    _assert(_hash64(observability.get("report_sha256")), "Step 18B report hash missing")

    mlb = observability.get("mlb_step17b") if isinstance(observability.get("mlb_step17b"), Mapping) else {}
    _assert(mlb.get("enabled") is True and mlb.get("running") is True, "Step 17B runtime is not enabled/running")
    _assert(mlb.get("role") == "leader" and mlb.get("leadership_acquired") is True, "Step 17B leadership drift")
    _assert(mlb.get("recovered_from_checkpoint") is True, "Step 17B restart recovery drift")
    _assert(isinstance(mlb.get("success_count"), int) and mlb.get("success_count", 0) >= 1, "Step 17B has no successful cycle")
    _assert(isinstance(mlb.get("last_checkpoint_version"), int) and mlb.get("last_checkpoint_version", 0) >= 1, "Step 17B checkpoint missing")
    _assert(mlb.get("provider_calls") == 0 and mlb.get("sportsbook_calls") == 0, "Step 17B network safety boundary drift")
    _assert(mlb.get("actionable_output_enabled") is False and mlb.get("wagering_enabled") is False, "Step 17B actionability drift")

    _assert(response_plan.get("data_type") == EXPECTED_RESPONSE_TYPE, "Step 18C response-plan contract drift")
    _assert(response_plan.get("response_state") == "healthy", "Step 18C response state is not healthy")
    _assert(response_plan.get("disposition") == "no_action", "Step 18C final disposition is not no_action")
    _assert(response_plan.get("page_operator") is False, "Step 18C would page the operator")
    _assert(response_plan.get("rollback_recommended") is False, "Step 18C recommends rollback")
    _assert(response_plan.get("automatic_rollback_performed") is False, "Step 18C automatic rollback invariant violated")
    response_rollback = response_plan.get("rollback_target") if isinstance(response_plan.get("rollback_target"), Mapping) else {}
    _assert(response_rollback.get("revision") == CERTIFIED_RENDER_REVISION, "Step 18C rollback revision drift")
    _assert(response_rollback.get("execution_mode") == "manual_only", "Step 18C rollback mode drift")
    _assert(response_rollback.get("requires_post_recovery_step18a") is True, "Step 18C post-recovery 18A gate drift")
    _assert(response_rollback.get("requires_post_recovery_step18b") is True, "Step 18C post-recovery 18B gate drift")
    plan_semantics = response_plan.get("semantics") if isinstance(response_plan.get("semantics"), Mapping) else {}
    _assert(plan_semantics.get("advisory_only") is True, "Step 18C is not advisory-only")
    for key in (
        "render_mutation_performed",
        "github_mutation_performed",
        "database_connection_opened",
        "database_read_performed",
        "database_write_performed",
        "scheduler_started",
        "provider_network_called",
        "sportsbook_network_called",
        "model_run",
        "projection_run",
        "monte_carlo_run",
        "actionable_output_enabled",
        "wager_action_performed",
    ):
        _assert(plan_semantics.get(key) is False, f"Step 18C dangerous semantic drift: {key}")
    _assert(_hash64(response_plan.get("plan_sha256")), "Step 18C plan hash missing")

    source_obs = response_plan.get("source_observability") if isinstance(response_plan.get("source_observability"), Mapping) else {}
    _assert(source_obs.get("report_sha256") == observability.get("report_sha256"), "Step 18B/18C evidence linkage drift")
    _assert(source_obs.get("state") == observability.get("state"), "Step 18B/18C state linkage drift")

    lineage = observability.get("lineage") if isinstance(observability.get("lineage"), Mapping) else {}
    _assert(lineage.get("step18a_merged_main_sha") == STEP18A_MERGED_MAIN_SHA, "Step 18B lineage to 18A drift")
    _assert(lineage.get("step17b_certified_deployed_sha") == CERTIFIED_RENDER_REVISION, "Step 18B deployed revision drift")
    response_lineage = response_plan.get("lineage") if isinstance(response_plan.get("lineage"), Mapping) else {}
    _assert(response_lineage.get("step18b_merged_main_sha") == STEP18B_MERGED_MAIN_SHA, "Step 18C lineage to 18B drift")
    _assert(response_lineage.get("certified_render_rollback_revision") == CERTIFIED_RENDER_REVISION, "Step 18C certified rollback lineage drift")

    certified_at = certified_at_utc or datetime.now(timezone.utc).isoformat()
    certificate = {
        "data_type": "mlb_step18d_final_production_freeze_certificate",
        "schema_version": SCHEMA_VERSION,
        "certificate_version": CERTIFICATE_VERSION,
        "state": "green",
        "step18_complete": True,
        "certified_at_utc": certified_at,
        "final_marker": FINAL_MARKER,
        "lineage": {
            "step18a_merged_main_sha": STEP18A_MERGED_MAIN_SHA,
            "step18b_merged_main_sha": STEP18B_MERGED_MAIN_SHA,
            "step18c_merged_main_sha": STEP18C_MERGED_MAIN_SHA,
            "certified_render_revision": CERTIFIED_RENDER_REVISION,
        },
        "evidence": {
            "step18a_evidence_sha256": baseline.get("evidence_sha256"),
            "step18a_safe_config_sha256": rollback.get("safe_config_sha256"),
            "step18b_report_sha256": observability.get("report_sha256"),
            "step18c_plan_sha256": response_plan.get("plan_sha256"),
        },
        "live_state": {
            "mlb_enabled": True,
            "mlb_running": True,
            "mlb_role": "leader",
            "success_count": mlb.get("success_count"),
            "failure_count": mlb.get("failure_count"),
            "last_checkpoint_version": mlb.get("last_checkpoint_version"),
            "recovered_from_checkpoint": True,
            "critical_incident_count": 0,
            "warning_incident_count": 0,
            "response_disposition": "no_action",
        },
        "frozen_invariants": {
            "render_mutation_performed": False,
            "automatic_rollback_performed": False,
            "database_write_performed": False,
            "provider_network_called": False,
            "sportsbook_network_called": False,
            "legacy_runtime_started": False,
            "legacy_scheduler_started": False,
            "model_run": False,
            "projection_run": False,
            "monte_carlo_run": False,
            "actionable_output_enabled": False,
            "wagering_enabled": False,
            "wager_action_performed": False,
            "database_secret_exposed": False,
            "new_render_service_created": False,
        },
        "recovery_policy": {
            "rollback_execution_mode": "manual_only",
            "rollback_revision": CERTIFIED_RENDER_REVISION,
            "requires_post_recovery_step18a": True,
            "requires_post_recovery_step18b": True,
        },
    }
    certificate["certificate_sha256"] = _canonical_hash(
        {key: deepcopy(value) for key, value in certificate.items() if key != "certified_at_utc"}
    )
    return certificate


__all__ = [
    "CERTIFICATE_VERSION",
    "CERTIFIED_RENDER_REVISION",
    "FINAL_MARKER",
    "MLBStep18DFinalFreezeError",
    "SCHEMA_VERSION",
    "STEP18A_MERGED_MAIN_SHA",
    "STEP18B_MERGED_MAIN_SHA",
    "STEP18C_MERGED_MAIN_SHA",
    "build_final_production_freeze",
]
