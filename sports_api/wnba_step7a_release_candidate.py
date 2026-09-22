"""Step 7A WNBA production release-candidate certification.

Step 7A is a read-only release boundary. It promotes the already-frozen Step 6W
architecture into a production release *candidate* without merging to main,
deploying Render, contacting Supabase/DraftKings, starting a scheduler, or
enabling production runtime.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any

from sports_api.wnba_step6w_final_certification import build_step6w_final_certification

MODEL_SOURCE = "Kyre Sports API WNBA Step 7A production release-candidate certification"
MODEL_VERSION = "wnba_step_7a_release_candidate_v1"
SCHEMA_VERSION = MODEL_VERSION

CERTIFIED_STEP6W_REVISION = "653ea47836b436076c2bc8e9e58d6a1d11b3dee3"
CERTIFIED_STEP6W_RUN_ID = 33050371110
CERTIFIED_STEP6W_RUN_ATTEMPT = 1
CERTIFIED_STEP6W_ARTIFACT_ID = 9637336718
CERTIFIED_STEP6W_ARTIFACT_DIGEST = "sha256:98461559379ab23f76347364732ef3cfaaec264c3cc15736af8f620224aff296"
CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256 = "31b59ff2d9515e19143268f39ba3e5172fac07af3b839b88fe0fe08daa2aff99"

SOURCE_BRANCH = "api-foundation-v1"
TARGET_BRANCH = "main"


class WNBAStep7AReleaseCandidateError(RuntimeError):
    pass


class WNBAStep7ANotCertifiedError(WNBAStep7AReleaseCandidateError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_step7a_release_candidate(
    *,
    env: Mapping[str, str] | None = None,
    step6w_getter: Callable[..., dict[str, Any]] = build_step6w_final_certification,
) -> dict[str, Any]:
    """Build the fail-closed WNBA production release-candidate certificate."""
    environment = _environment(env)
    step6w = step6w_getter(env=environment)
    final_freeze = step6w.get("final_freeze") if isinstance(step6w.get("final_freeze"), Mapping) else {}
    semantics = step6w.get("semantics") if isinstance(step6w.get("semantics"), Mapping) else {}
    supabase = step6w.get("supabase") if isinstance(step6w.get("supabase"), Mapping) else {}

    checks = {
        "step6w_final_architecture_certified": step6w.get("final_architecture_certified") is True,
        "step6w_state_is_frozen": step6w.get("state") == "wnba_upgraded_architecture_frozen",
        "step6w_manifest_matches_frozen_proof": final_freeze.get("final_manifest_sha256") == CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256,
        "step6w_canonical_hash_matches_manifest": final_freeze.get("canonical_json_sha256") == CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256,
        "step6j_live_canary_complete": step6w.get("step6j_live_canary_complete") is True,
        "production_runtime_still_off": step6w.get("production_live") is False,
        "scheduler_still_not_authorized": step6w.get("scheduler_authorized") is False,
        "scheduler_still_not_started": step6w.get("scheduler_started") is False,
        "step6w_was_network_free": semantics.get("network_used") is False,
        "step6w_did_not_mutate_production_runtime": semantics.get("production_runtime_mutated") is False,
        "step6w_did_not_mutate_scheduler_authorization": semantics.get("scheduler_authorization_mutated") is False,
        "step6w_did_not_write_feed": semantics.get("feed_write_performed") is False,
        "step6w_did_not_read_secret": semantics.get("secret_read") is False,
        "step6w_did_not_return_secret": semantics.get("secret_returned") is False,
        "supabase_canary_left_no_active_lock": supabase.get("active_locks_after_canary") == 0,
    }

    certified = all(checks.values())
    blocking_reasons = [name for name, passed in checks.items() if not passed]

    release_contract = {
        "schema_version": SCHEMA_VERSION,
        "source_branch": SOURCE_BRANCH,
        "target_branch": TARGET_BRANCH,
        "certified_step6w": {
            "revision": CERTIFIED_STEP6W_REVISION,
            "run_id": CERTIFIED_STEP6W_RUN_ID,
            "run_attempt": CERTIFIED_STEP6W_RUN_ATTEMPT,
            "artifact_id": CERTIFIED_STEP6W_ARTIFACT_ID,
            "artifact_digest": CERTIFIED_STEP6W_ARTIFACT_DIGEST,
            "final_manifest_sha256": CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256,
        },
        "release_policy": {
            "candidate_only": True,
            "merge_to_main_authorized": False,
            "render_deployment_authorized": False,
            "production_runtime_authorized": False,
            "scheduler_authorized": False,
            "supabase_write_authorized": False,
            "draftkings_live_read_authorized": False,
            "wager_action_authorized": False,
            "next_boundary": "Step 7B explicit main-branch merge",
        },
    }
    release_manifest_sha = _hash(release_contract)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step7a_production_release_candidate",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": "wnba_production_release_candidate_certified" if certified else "wnba_production_release_candidate_blocked",
        "release_candidate_certified": certified,
        "blocking_reasons": blocking_reasons,
        "checks": checks,
        "source_branch": SOURCE_BRANCH,
        "target_branch": TARGET_BRANCH,
        "production_live": False,
        "merge_to_main_authorized": False,
        "render_deployment_authorized": False,
        "scheduler_authorized": False,
        "scheduler_started": False,
        "release_candidate": {
            **release_contract,
            "release_manifest_sha256": release_manifest_sha,
            "canonical_json_sha256": release_manifest_sha,
        },
        "semantics": {
            "step7a_is_read_only": True,
            "step7a_is_release_candidate_only": True,
            "step7a_uses_frozen_step6w_certificate": True,
            "network_used": False,
            "draftkings_called": False,
            "supabase_called": False,
            "feed_write_performed": False,
            "environment_mutated": False,
            "secret_read": False,
            "secret_returned": False,
            "merge_performed": False,
            "render_deployment_performed": False,
            "production_runtime_mutated": False,
            "scheduler_authorization_mutated": False,
            "scheduler_started": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


def require_step7a_release_candidate_certified(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = build_step7a_release_candidate(env=env)
    if report.get("release_candidate_certified") is not True:
        raise WNBAStep7ANotCertifiedError(
            "WNBA Step 7A production release candidate is blocked: "
            + "; ".join(report.get("blocking_reasons") or ["unknown blocker"])
        )
    return report
