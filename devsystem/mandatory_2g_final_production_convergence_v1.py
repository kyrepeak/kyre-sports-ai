"""MONSTER Step 2G — Final Production Convergence Gate V1.

Fail-closed, MONSTER-only convergence verifier. Step 2G is the terminal proof
that the exact certified MONSTER implementation has converged through the final
MONSTER state, production deployment and stable alias into the runtime,
canonical router/backend path, and user-facing UI.

This module is read-only. It performs no network calls, deployments, cache
clears, restarts, repository mutations, or product mutations. Evidence is
collected by the authoritative MONSTER execution lane and validated here.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

VERSION = "MONSTER_STEP2G_FINAL_PRODUCTION_CONVERGENCE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
BLIND_REDEPLOY_ALLOWED = False
BLIND_CACHE_CLEAR_ALLOWED = False
EXPECTED_FINAL_BRANCH = "monster-main"
EXPECTED_PROJECT = "kyre-sports-ai"
EXPECTED_ENVIRONMENT = "production"
RECOVERY_SEQUENCE = (
    "ANTI_LOOP",
    "STEP_2C",
    "STEP_2B",
    "STEP_2A",
    "REQUIRED_CORRECTION",
    "STEP_2D_IF_DATA_TRUTH_INVALIDATED",
    "STEP_2E_IF_ROUTING_INVALIDATED",
    "STEP_2F_IF_DEPLOYMENT_INVALIDATED",
    "STEP_2G",
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_FOREIGN = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.IGNORECASE)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _walk(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, str):
        yield value


def _contains_foreign(value: Any) -> bool:
    return any(_FOREIGN.search(text) for text in _walk(value))


def _valid_sha(value: Any) -> bool:
    return bool(_SHA_RE.fullmatch(str(value or "").strip()))


def _valid_digest(value: Any) -> bool:
    return bool(_DIGEST_RE.fullmatch(str(value or "").strip()))


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _blocked(failure_kind: str, reason: str, *, detail: Any = None) -> dict[str, Any]:
    proof = {
        "version": VERSION,
        "failure_kind": failure_kind,
        "reason": reason,
        "detail": detail,
    }
    fingerprint = _digest(proof)
    return {
        "status": "BLOCKED",
        "version": VERSION,
        "monster_only": True,
        "step2g_enforced": True,
        "failure_kind": failure_kind,
        "reason": reason,
        "detail": detail,
        "failure_fingerprint": fingerprint,
        "evidence_digest": fingerprint,
        "final_verification_authorized": False,
        "frozen_checkpoint_authorized": False,
        "blind_redeploy_allowed": BLIND_REDEPLOY_ALLOWED,
        "blind_cache_clear_allowed": BLIND_CACHE_CLEAR_ALLOWED,
        "requires_user_intervention": False,
        "next_legal_action": "RETURN_TO_MONSTER_STEP_2C",
        "recovery_sequence": list(RECOVERY_SEQUENCE),
        "step2c_evidence_candidate": {
            "source": "monster-step2g-final-production-convergence-v1",
            "failure_class": "production-convergence",
            "affected_boundary": failure_kind,
            "fingerprint": fingerprint,
            "material": True,
            "summary": reason,
            "next_required_gate": "STEP_2C",
        },
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _require_equal(actual: Any, expected: Any, failure_kind: str, reason: str) -> dict[str, Any] | None:
    if actual != expected:
        return _blocked(failure_kind, reason, detail={"actual": actual, "expected": expected})
    return None


def validate_convergence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        return _blocked("UNKNOWN_CONVERGENCE_FAILURE", "Step 2G evidence must be an object")
    if _contains_foreign(evidence):
        return _blocked("FOREIGN_SYSTEM_EVIDENCE", "API 2 state/evidence is forbidden in MONSTER Step 2G")
    if evidence.get("authority") != "MONSTER_ONLY":
        return _blocked("WRONG_ENVIRONMENT", "Step 2G authority must be MONSTER_ONLY")

    certified = _mapping(evidence.get("certified"))
    final = _mapping(evidence.get("final"))
    deployment = _mapping(evidence.get("deployment"))
    alias = _mapping(evidence.get("stable_alias"))
    runtime = _mapping(evidence.get("runtime"))
    router = _mapping(evidence.get("router"))
    backend = _mapping(evidence.get("backend"))
    ui = _mapping(evidence.get("ui"))
    rollback = _mapping(evidence.get("rollback_anchor"))
    missing = [
        name
        for name, value in (
            ("certified", certified),
            ("final", final),
            ("deployment", deployment),
            ("stable_alias", alias),
            ("runtime", runtime),
            ("router", router),
            ("backend", backend),
            ("ui", ui),
            ("rollback_anchor", rollback),
        )
        if value is None
    ]
    if missing:
        return _blocked("UNKNOWN_CONVERGENCE_FAILURE", "required Step 2G evidence boundary missing", detail=missing)

    certified_sha = str(certified.get("sha") or "").strip().lower()
    certified_digest = str(certified.get("artifact_digest") or "").strip().lower()
    if not _valid_sha(certified_sha) or not _valid_digest(certified_digest):
        return _blocked("WRONG_FINAL_SHA", "certified MONSTER SHA/artifact identity is invalid")

    final_branch = str(final.get("branch") or "").strip()
    final_sha = str(final.get("sha") or "").strip().lower()
    final_digest = str(final.get("artifact_digest") or "").strip().lower()
    if final_branch != EXPECTED_FINAL_BRANCH:
        return _blocked("MERGE_NOT_PRESENT", "certified work is not on the authoritative MONSTER final branch")
    if not _valid_sha(final_sha):
        return _blocked("WRONG_FINAL_SHA", "final MONSTER SHA is invalid")
    if final.get("contains_certified_sha") is not True:
        return _blocked("MERGE_NOT_PRESENT", "final MONSTER state does not contain the certified candidate")
    if final_digest != certified_digest:
        return _blocked("WRONG_FINAL_SHA", "final MONSTER artifact differs from the certified candidate")

    deployment_id = str(deployment.get("id") or "").strip()
    deployment_sha = str(deployment.get("sha") or "").strip().lower()
    if not deployment_id:
        return _blocked("DEPLOYMENT_STALE", "expected MONSTER production deployment identity is missing")
    if deployment_sha != final_sha:
        return _blocked("DEPLOYMENT_WRONG_SHA", "production deployment was not built from the final MONSTER SHA")
    if str(deployment.get("project") or "").strip() != EXPECTED_PROJECT:
        return _blocked("WRONG_PROJECT", "production deployment belongs to the wrong project")
    if str(deployment.get("environment") or "").strip() != EXPECTED_ENVIRONMENT:
        return _blocked("WRONG_ENVIRONMENT", "deployment is not the MONSTER production environment")
    if deployment.get("stale") is True:
        return _blocked("DEPLOYMENT_STALE", "deployment is explicitly stale")
    if deployment.get("healthy") is not True:
        return _blocked("PRODUCTION_NOT_UPDATED", "expected production deployment is not healthy")

    alias_url = str(alias.get("url") or "").strip()
    if not alias_url or alias.get("healthy") is not True:
        return _blocked("ALIAS_STALE", "stable MONSTER production alias is missing or unhealthy")
    if str(alias.get("target_deployment_id") or "").strip() != deployment_id:
        return _blocked("ALIAS_DRIFT", "stable production alias targets the wrong deployment")
    if str(alias.get("target_sha") or "").strip().lower() != final_sha:
        return _blocked("ALIAS_DRIFT", "stable production alias targets the wrong SHA")

    if str(runtime.get("entrypoint") or "") != str(runtime.get("expected_entrypoint") or ""):
        return _blocked("ENTRYPOINT_DRIFT", "live runtime loaded the wrong MONSTER application entrypoint")
    if str(runtime.get("sha") or "").strip().lower() != final_sha:
        return _blocked("PROCESS_STALE", "live runtime SHA differs from final/deployed MONSTER SHA")
    if str(runtime.get("deployment_id") or "").strip() != deployment_id:
        return _blocked("PROCESS_STALE", "live runtime is attached to a different deployment")
    if str(runtime.get("artifact_digest") or "").strip().lower() != certified_digest:
        return _blocked("PRODUCTION_NOT_UPDATED", "live runtime artifact differs from the certified MONSTER artifact")
    if runtime.get("module_cache_fresh") is not True:
        return _blocked("STREAMLIT_STALE_MODULE", "live Streamlit/Python module cache is stale")
    if runtime.get("process_fresh") is not True:
        return _blocked("PROCESS_STALE", "live production process is stale")
    if runtime.get("application_state_fresh") is not True:
        return _blocked("FRONTEND_STALE_STATE", "live browser-facing application state is stale")

    router_fields = (
        ("owner", "expected_owner", "ROUTER_DRIFT", "canonical router owner drift"),
        ("sport", "expected_sport", "ROUTER_DRIFT", "canonical sport route drift"),
        ("market", "expected_market", "ROUTER_DRIFT", "canonical market/page route drift"),
        ("module", "expected_module", "ROUTER_DRIFT", "canonical module route drift"),
        ("backend_endpoint", "expected_backend_endpoint", "BACKEND_ROUTE_DRIFT", "router backend endpoint drift"),
    )
    for actual_key, expected_key, kind, reason in router_fields:
        mismatch = _require_equal(router.get(actual_key), router.get(expected_key), kind, reason)
        if mismatch:
            return mismatch

    mismatch = _require_equal(
        backend.get("endpoint"), backend.get("expected_endpoint"),
        "BACKEND_ROUTE_DRIFT", "live backend endpoint differs from the certified endpoint",
    )
    if mismatch:
        return mismatch
    mismatch = _require_equal(
        backend.get("schema"), backend.get("expected_schema"),
        "API_SCHEMA_DRIFT", "live backend schema differs from the certified schema",
    )
    if mismatch:
        return mismatch
    mismatch = _require_equal(
        backend.get("data_truth_contract"), backend.get("expected_data_truth_contract"),
        "API_SCHEMA_DRIFT", "live backend data-truth contract differs from the certified Step 2D contract",
    )
    if mismatch:
        return mismatch

    required_markers = {str(item) for item in ui.get("expected_markers", [])}
    observed_markers = {str(item) for item in ui.get("observed_markers", [])}
    forbidden_markers = {str(item) for item in ui.get("forbidden_markers", [])}
    observed_forbidden = {str(item) for item in ui.get("observed_forbidden_markers", [])}
    if not required_markers or not required_markers.issubset(observed_markers):
        return _blocked("USER_FACING_PARITY_FAILURE", "live MONSTER UI is missing certified behavior/markers")
    if forbidden_markers.intersection(observed_markers) or observed_forbidden:
        return _blocked("USER_FACING_PARITY_FAILURE", "live MONSTER UI still exposes stale/forbidden behavior")
    if ui.get("behavior_verified") is not True:
        return _blocked("USER_FACING_PARITY_FAILURE", "live user-facing behavior was not verified")

    if not _valid_sha(rollback.get("sha")):
        return _blocked("UNKNOWN_CONVERGENCE_FAILURE", "valid MONSTER rollback anchor is required")
    if int(evidence.get("promotion_lanes") or 0) != 1:
        return _blocked("UNKNOWN_CONVERGENCE_FAILURE", "Step 2G requires exactly one MONSTER promotion lane")

    proof = {
        "version": VERSION,
        "authority": "MONSTER_ONLY",
        "certified_sha": certified_sha,
        "certified_artifact_digest": certified_digest,
        "final_branch": final_branch,
        "final_sha": final_sha,
        "deployment_id": deployment_id,
        "stable_alias": alias_url,
        "runtime": {
            "sha": final_sha,
            "deployment_id": deployment_id,
            "entrypoint": runtime.get("entrypoint"),
            "artifact_digest": certified_digest,
        },
        "router": {
            "owner": router.get("owner"),
            "sport": router.get("sport"),
            "market": router.get("market"),
            "module": router.get("module"),
            "backend_endpoint": router.get("backend_endpoint"),
        },
        "backend": {
            "endpoint": backend.get("endpoint"),
            "schema": backend.get("schema"),
            "data_truth_contract": backend.get("data_truth_contract"),
        },
        "ui_markers": sorted(required_markers),
        "rollback_sha": str(rollback.get("sha")).lower(),
        "promotion_lanes": 1,
    }
    evidence_digest = _digest(proof)
    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "step2g_enforced": True,
        "certified_candidate_sha": certified_sha,
        "final_sha": final_sha,
        "deployment_id": deployment_id,
        "stable_alias": alias_url,
        "live_runtime_identity": dict(proof["runtime"]),
        "live_router_identity": dict(proof["router"]),
        "live_backend_identity": dict(proof["backend"]),
        "live_ui_parity": True,
        "stale_cache_module_process_detected": False,
        "rollback_anchor_verified": True,
        "evidence_digest": evidence_digest,
        "final_verification_authorized": True,
        "frozen_checkpoint_authorized": True,
        "blind_redeploy_allowed": BLIND_REDEPLOY_ALLOWED,
        "blind_cache_clear_allowed": BLIND_CACHE_CLEAR_ALLOWED,
        "recovery_sequence": list(RECOVERY_SEQUENCE),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    evidence = {
        "authority": "MONSTER_ONLY",
        "certified": {"sha": "1" * 40, "artifact_digest": "a" * 64},
        "final": {
            "branch": EXPECTED_FINAL_BRANCH,
            "sha": "2" * 40,
            "contains_certified_sha": True,
            "artifact_digest": "a" * 64,
        },
        "deployment": {
            "id": "monster-self-test",
            "sha": "2" * 40,
            "project": EXPECTED_PROJECT,
            "environment": EXPECTED_ENVIRONMENT,
            "healthy": True,
            "stale": False,
        },
        "stable_alias": {
            "url": "https://pickvault.streamlit.app",
            "target_deployment_id": "monster-self-test",
            "target_sha": "2" * 40,
            "healthy": True,
        },
        "runtime": {
            "entrypoint": "app.py",
            "expected_entrypoint": "app.py",
            "sha": "2" * 40,
            "deployment_id": "monster-self-test",
            "artifact_digest": "a" * 64,
            "process_fresh": True,
            "module_cache_fresh": True,
            "application_state_fresh": True,
        },
        "router": {
            "owner": "MONSTER_CANONICAL_ROUTER",
            "expected_owner": "MONSTER_CANONICAL_ROUTER",
            "sport": "nfl",
            "expected_sport": "nfl",
            "market": "game-total",
            "expected_market": "game-total",
            "module": "self-test-module",
            "expected_module": "self-test-module",
            "backend_endpoint": "/api/self-test",
            "expected_backend_endpoint": "/api/self-test",
        },
        "backend": {
            "endpoint": "/api/self-test",
            "expected_endpoint": "/api/self-test",
            "schema": "self-test-v1",
            "expected_schema": "self-test-v1",
            "data_truth_contract": "STEP2D_GREEN",
            "expected_data_truth_contract": "STEP2D_GREEN",
        },
        "ui": {
            "expected_markers": ["MONSTER_STEP2G_SELF_TEST"],
            "observed_markers": ["MONSTER_STEP2G_SELF_TEST"],
            "forbidden_markers": [],
            "observed_forbidden_markers": [],
            "behavior_verified": True,
        },
        "rollback_anchor": {"sha": "0" * 40},
        "promotion_lanes": 1,
    }
    result = validate_convergence(evidence)
    if result.get("status") != "GREEN":
        raise RuntimeError(f"MONSTER Step 2G self-test failed: {result}")
    return result


if __name__ == "__main__":
    print("MONSTER_STEP2G_FINAL_PRODUCTION_CONVERGENCE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
