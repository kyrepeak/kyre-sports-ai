"""Step 6W final WNBA upgraded-architecture certification and freeze.

Step 6W is deliberately read-only and network-free. It certifies the completed
Step 6V live Supabase canary by immutable evidence and then binds that proof to
the previously frozen Phase 6 engineering contract.

This module does not contact DraftKings or Supabase, mutate environment
variables, write the Kyre feed, start a scheduler, enable production runtime,
run Monte Carlo, provision hosting, expose secrets, or perform wager actions.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step6p_phase6_certification import build_step6p_phase6_certification

MODEL_SOURCE = "Kyre Sports API WNBA Step 6W final upgraded-architecture certification + freeze"
MODEL_VERSION = "wnba_step_6w_final_certification_v1"
SCHEMA_VERSION = MODEL_VERSION

CERTIFIED_STEP6U_REVISION = "0ed7d9a312348a24294658fe49e4f8585d00c402"
CERTIFIED_STEP6V_REVISION = "8f045a7e89d0fb97f0fa7bb2c8855f91c4435a9f"
STEP6V_RUN_ID = 33048741562
STEP6V_RUN_ATTEMPT = 1
STEP6V_ARTIFACT_ID = 9636707111
STEP6V_ARTIFACT_DIGEST = "sha256:c80588ad73688f8356ed01e61b06fbec200e9e1e71aad70be8d3163776008c1f"
STEP6V_EVIDENCE_FILE_SHA256 = "bce31354b1be098b6a1e5cf708b28da87b28d916c8accfa32d4f7183b3706e7d"
STEP6V_ACTIVATION_ID = "step6v-33048741562-1"

SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
SUPABASE_FEED_OBJECT_KEY = "wnba_market_feed.json"
SUPABASE_FEED_SIZE_BYTES = 92290
SUPABASE_FEED_SHA256 = "7d6363bc12e6ee2351938eb83eb636d89ec25e559fc199b6a904cdeec816b00e"
SUPABASE_MARKER_OBJECT_KEY = ".wnba-step6j-canary-state.json"
SUPABASE_MARKER_SHA256 = "64cf7739cdb095546b7954c35f14d7a4244672c3a8ef999f6cc25a93168f46d2"

EVIDENCE_PATH = Path(__file__).resolve().parent / "certification" / "wnba_step6v_live_canary_evidence.json"

FINAL_UPGRADE_STEPS: tuple[dict[str, str], ...] = (
    {"step": "6Q", "role": "durable storage abstraction", "state": "frozen"},
    {"step": "6R", "role": "Supabase durable-storage backend + schema contract", "state": "frozen"},
    {"step": "6S", "role": "storage-aware Step 6J canary", "state": "frozen"},
    {"step": "6T", "role": "durable canary evidence verification", "state": "frozen"},
    {"step": "6U", "role": "read-only activation evidence bridge", "state": "frozen"},
    {"step": "6V", "role": "GitHub -> Supabase one-shot live Step 6J canary", "state": "frozen_live_proof"},
    {"step": "6W", "role": "final upgraded-architecture certification + freeze", "state": "certifier"},
)


class WNBAStep6WCertificationError(RuntimeError):
    pass


class WNBAStep6WNotCertifiedError(WNBAStep6WCertificationError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_step6v_evidence(path: Path = EVIDENCE_PATH) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise WNBAStep6WCertificationError("Step 6V evidence must be a JSON object.")
    return parsed, digest


def _expected_all_off(switches: Mapping[str, Any]) -> bool:
    expected = (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
    )
    return all(switches.get(name) is False for name in expected)


def build_step6w_final_certification(
    *,
    env: Mapping[str, str] | None = None,
    phase6_getter: Callable[..., dict[str, Any]] = build_step6p_phase6_certification,
    evidence_loader: Callable[[], tuple[dict[str, Any], str]] = _load_step6v_evidence,
) -> dict[str, Any]:
    """Build the network-free final WNBA upgraded-architecture certificate."""
    environment = _environment(env)
    phase6 = phase6_getter(env=environment)

    evidence_error: str | None = None
    try:
        evidence, evidence_file_sha = evidence_loader()
    except Exception as exc:  # fail closed while still returning a diagnostic report
        evidence = {}
        evidence_file_sha = ""
        evidence_error = f"{type(exc).__name__}: {exc}"

    canary = evidence.get("canary") if isinstance(evidence.get("canary"), Mapping) else {}
    durable = evidence.get("evidence") if isinstance(evidence.get("evidence"), Mapping) else {}
    switches = evidence.get("final_switch_state") if isinstance(evidence.get("final_switch_state"), Mapping) else {}
    safety = evidence.get("safety") if isinstance(evidence.get("safety"), Mapping) else {}
    phase6_semantics = phase6.get("semantics") if isinstance(phase6.get("semantics"), Mapping) else {}

    checks = {
        "phase6_engineering_contract_certified": phase6.get("phase6_engineering_certified") is True,
        "phase6_certificate_never_claims_production_live": phase6.get("production_live") is False,
        "phase6_certification_was_network_free": phase6_semantics.get("network_used") is False,
        "step6v_evidence_loaded": evidence_error is None,
        "step6v_evidence_file_sha256_matches": evidence_file_sha == STEP6V_EVIDENCE_FILE_SHA256,
        "step6v_status_completed": evidence.get("status") == "completed",
        "step6v_candidate_true": evidence.get("step6j_complete_candidate") is True,
        "step6v_storage_backend_supabase": evidence.get("storage_backend") == "supabase",
        "step6v_activation_identity_matches": evidence.get("activation_id") == STEP6V_ACTIVATION_ID,
        "step6v_canary_date_matches": evidence.get("date") == "2026-08-27" and evidence.get("season") == 2026,
        "step6v_offer_sides_nonzero": int(canary.get("offer_side_count") or 0) > 0,
        "step6v_post_write_sha_matches_observed_supabase_feed": canary.get("post_write_sha256") == SUPABASE_FEED_SHA256,
        "step6v_durable_evidence_verified": durable.get("evidence_verified") is True,
        "step6v_rollback_verified": durable.get("rollback_verified") is True,
        "step6v_rollback_available": canary.get("rollback_available") is True,
        "step6v_feed_size_matches_observed_supabase_feed": durable.get("feed_size_bytes") == SUPABASE_FEED_SIZE_BYTES,
        "step6v_marker_sha_matches_observed_supabase_marker": durable.get("marker_content_sha256") == SUPABASE_MARKER_SHA256,
        "step6v_all_runtime_write_switches_finished_off": _expected_all_off(switches),
        "step6v_scheduler_not_authorized": safety.get("scheduler_authorized") is False,
        "step6v_scheduler_not_started": safety.get("scheduler_started") is False,
        "step6v_production_runtime_never_enabled": safety.get("production_runtime_enabled") is False,
        "step6v_temporary_write_switches_not_persisted": safety.get("temporary_write_switches_persisted") is False,
        "step6v_base_environment_not_mutated": safety.get("base_environment_mutated") is False,
        "step6v_secret_not_returned": safety.get("secret_value_returned") is False,
        "step6v_no_paid_odds_vendor": safety.get("paid_odds_vendor_used") is False,
        "step6v_no_monte_carlo": safety.get("monte_carlo_run") is False,
        "step6v_no_wager_action": safety.get("wager_action_performed") is False,
    }

    certified = all(checks.values())
    blocking_reasons = [name for name, passed in checks.items() if not passed]
    state = "wnba_upgraded_architecture_frozen" if certified else "wnba_final_certification_blocked"

    phase6_freeze = phase6.get("master_freeze") if isinstance(phase6.get("master_freeze"), Mapping) else {}
    freeze_payload = {
        "schema_version": SCHEMA_VERSION,
        "certified_step6u_revision": CERTIFIED_STEP6U_REVISION,
        "certified_step6v_revision": CERTIFIED_STEP6V_REVISION,
        "step6v_run": {
            "run_id": STEP6V_RUN_ID,
            "run_attempt": STEP6V_RUN_ATTEMPT,
            "artifact_id": STEP6V_ARTIFACT_ID,
            "artifact_digest": STEP6V_ARTIFACT_DIGEST,
            "evidence_file_sha256": STEP6V_EVIDENCE_FILE_SHA256,
            "activation_id": STEP6V_ACTIVATION_ID,
        },
        "supabase_observed_durable_state": {
            "project_ref": SUPABASE_PROJECT_REF,
            "feed_object_key": SUPABASE_FEED_OBJECT_KEY,
            "feed_size_bytes": SUPABASE_FEED_SIZE_BYTES,
            "feed_sha256": SUPABASE_FEED_SHA256,
            "marker_object_key": SUPABASE_MARKER_OBJECT_KEY,
            "marker_sha256": SUPABASE_MARKER_SHA256,
            "active_locks_after_canary": 0,
        },
        "phase6_master_manifest_sha256": phase6_freeze.get("master_manifest_sha256"),
        "upgraded_steps": list(FINAL_UPGRADE_STEPS),
        "final_safety_policy": {
            "production_runtime_default_off": True,
            "scheduler_authorized_by_step6w": False,
            "scheduler_started_by_step6w": False,
            "step6v_is_one_shot_proof_not_continuous_sync": True,
            "live_activation_requires_a_new_explicit_operator_boundary": True,
            "secrets_must_remain_out_of_evidence_and_source_control": True,
            "paid_odds_vendor_required": False,
        },
    }
    freeze_sha = _hash(freeze_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6w_final_upgraded_architecture_certification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": state,
        "final_architecture_certified": certified,
        "production_live": False,
        "scheduler_authorized": False,
        "scheduler_started": False,
        "step6j_live_canary_complete": checks["step6v_status_completed"] and checks["step6v_candidate_true"],
        "blocking_reasons": blocking_reasons,
        "checks": checks,
        "evidence_error": evidence_error,
        "step6v": {
            "certified_revision": CERTIFIED_STEP6V_REVISION,
            "run_id": STEP6V_RUN_ID,
            "run_attempt": STEP6V_RUN_ATTEMPT,
            "artifact_id": STEP6V_ARTIFACT_ID,
            "artifact_digest": STEP6V_ARTIFACT_DIGEST,
            "evidence_file_sha256": evidence_file_sha,
            "activation_id": evidence.get("activation_id"),
            "offer_side_count": canary.get("offer_side_count"),
            "evidence_verified": durable.get("evidence_verified"),
            "rollback_verified": durable.get("rollback_verified"),
        },
        "supabase": freeze_payload["supabase_observed_durable_state"],
        "upgraded_steps": list(FINAL_UPGRADE_STEPS),
        "final_freeze": {
            **freeze_payload,
            "final_manifest_sha256": freeze_sha,
            "canonical_json_sha256": freeze_sha,
        },
        "semantics": {
            "step6w_is_read_only": True,
            "step6w_uses_frozen_evidence_not_live_network_calls": True,
            "production_runtime_mutated": False,
            "scheduler_authorization_mutated": False,
            "scheduler_started": False,
            "draftkings_called": False,
            "supabase_called": False,
            "feed_write_performed": False,
            "environment_mutated": False,
            "secret_read": False,
            "secret_returned": False,
            "paid_host_created": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "network_used": False,
            "final_certification_does_not_enable_production": True,
        },
    }


def require_step6w_final_certified(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = build_step6w_final_certification(env=env)
    if report.get("final_architecture_certified") is not True:
        raise WNBAStep6WNotCertifiedError(
            "WNBA Step 6W final certification is blocked: "
            + "; ".join(report.get("blocking_reasons") or ["unknown blocker"])
        )
    return report
