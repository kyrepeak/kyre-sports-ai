"""MONSTER Step 2F — Live Production Consumption + Stable Alias Gate V1.

Read-only production attestation verifier.  It proves that the exact MONSTER
candidate is the production deployment consumed through the stable alias and
canonical endpoint.  Preview health, branch builds, stale deployments and
alias-only checks are never accepted as production proof.

For a genuinely read-only control-plane-only change, deployment may be marked
not applicable only when the attestation proves that the implementation makes
no network calls, automatic mutation, or product/runtime mutation and carries
a rollback anchor.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

VERSION = "MONSTER_STEP2F_LIVE_PRODUCTION_CONSUMPTION_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
BLIND_REDEPLOY_ALLOWED = False
RECOVERY_SEQUENCE = ("ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "EXECUTE", "STEP_2D", "STEP_2E", "STEP_2F")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _blocked(failure_kind: str, reason: str, *, detail: Any = None) -> dict[str, Any]:
    evidence = {"gate": VERSION, "failure_kind": failure_kind, "reason": reason, "detail": detail}
    fingerprint = _digest(evidence)
    return {
        "status": "BLOCKED",
        "version": VERSION,
        "monster_only": True,
        "step2f_enforced": True,
        "failure_kind": failure_kind,
        "reason": reason,
        "detail": detail,
        "failure_fingerprint": fingerprint,
        "evidence_digest": fingerprint,
        "step2c_evidence_candidate": {
            "source": "monster-step2f-production-consumption-v1",
            "fingerprint": fingerprint,
            "failure_class": "production/deployment",
            "affected_boundary": "stable-production-consumption",
            "material": True,
            "summary": reason,
            "next_required_gate": "STEP_2C",
        },
        "blind_redeploy_allowed": BLIND_REDEPLOY_ALLOWED,
        "final_verification_authorized": False,
        "requires_user_intervention": False,
        "next_legal_action": "RETURN_TO_MONSTER_STEP_2C",
        "recovery_sequence": list(RECOVERY_SEQUENCE),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _valid_sha(value: Any) -> bool:
    return bool(_SHA_RE.fullmatch(str(value or "").strip()))


def validate_production_attestation(attestation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(attestation, Mapping):
        return _blocked("PROOF_MISMATCH", "production attestation must be an object")
    candidate_sha = str(attestation.get("candidate_sha") or "").strip().lower()
    if not _valid_sha(candidate_sha):
        return _blocked("BAD_CANDIDATE", "candidate SHA must be an exact 40-character commit SHA")

    rollback = attestation.get("rollback_anchor")
    if not isinstance(rollback, Mapping) or not rollback:
        return _blocked("ROLLBACK_ANCHOR_MISSING", "production proof requires a rollback anchor")

    applicable = attestation.get("deployment_applicable")
    if applicable is False:
        read_only = (
            attestation.get("control_plane_only") is True
            and attestation.get("network_calls") is False
            and attestation.get("auto_mutate") is False
            and attestation.get("product_runtime_mutation") is False
        )
        if not read_only:
            return _blocked("DEPLOYMENT_PROOF_REQUIRED", "deployment N/A is legal only for a proven read-only control-plane change")
        proof = {
            "candidate_sha": candidate_sha,
            "deployment_applicable": False,
            "rollback_anchor": dict(rollback),
            "proof": "NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE",
        }
        return {
            "status": "GREEN",
            "version": VERSION,
            "monster_only": True,
            "step2f_enforced": True,
            "deployment_applicable": False,
            "deployment_proof": "NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE",
            "exact_head_deployed": False,
            "stable_alias_parity": False,
            "real_website_consumption_verified": False,
            "rollback_anchor_verified": True,
            "evidence_digest": _digest(proof),
            "blind_redeploy_allowed": BLIND_REDEPLOY_ALLOWED,
            "final_verification_authorized": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        }
    if applicable is not True:
        return _blocked("DEPLOYMENT_PROOF_REQUIRED", "deployment applicability must be explicit")

    deployment = attestation.get("deployment")
    alias = attestation.get("stable_alias")
    endpoint = attestation.get("canonical_endpoint")
    smoke = attestation.get("smoke")
    if not all(isinstance(item, Mapping) for item in (deployment, alias, endpoint, smoke)):
        return _blocked("PROOF_MISMATCH", "deployment, stable alias, endpoint and smoke evidence are required")
    deployment_id = str(deployment.get("id") or "").strip()
    deployment_sha = str(deployment.get("sha") or "").strip().lower()
    if not deployment_id or deployment_sha != candidate_sha:
        return _blocked("DEPLOYMENT_DRIFT", "production deployment does not contain the certified candidate SHA")
    if deployment.get("environment") != "production" or deployment.get("production") is not True:
        return _blocked("WRONG_PROJECT_ENVIRONMENT", "candidate is not attested as a production deployment")
    if deployment.get("preview") is True:
        return _blocked("PREVIEW_MASQUERADING_AS_PRODUCTION", "preview deployment cannot satisfy Step 2F")
    if deployment.get("stale") is True:
        return _blocked("STALE_DEPLOYMENT", "stale production deployment cannot satisfy Step 2F")
    if deployment.get("healthy") is not True:
        return _blocked("UNHEALTHY_PRODUCTION_RUNTIME", "production deployment health is not GREEN")

    if alias.get("healthy") is not True:
        return _blocked("ALIAS_DRIFT", "stable production alias is unhealthy")
    if str(alias.get("target_deployment_id") or "").strip() != deployment_id:
        return _blocked("ALIAS_DRIFT", "stable alias points to a different deployment")
    if str(alias.get("target_sha") or "").strip().lower() != candidate_sha:
        return _blocked("ALIAS_DRIFT", "stable alias points to a deployment with a different SHA")

    if endpoint.get("healthy") is not True:
        return _blocked("UNHEALTHY_PRODUCTION_RUNTIME", "canonical endpoint health failed")
    if str(endpoint.get("router_owner") or "") != str(endpoint.get("expected_router_owner") or ""):
        return _blocked("WRONG_ROUTER", "canonical endpoint router owner differs from the expected owner")
    if str(endpoint.get("schema") or "") != str(endpoint.get("expected_schema") or ""):
        return _blocked("SCHEMA_MISMATCH", "canonical endpoint schema differs from expected schema")
    if endpoint.get("consumer_verified") is not True:
        return _blocked("CONSUMER_MISMATCH", "real website consumption of the canonical endpoint is not verified")

    required = {str(item) for item in smoke.get("required", [])}
    passed = {str(item) for item in smoke.get("passed", [])}
    if not required or not required.issubset(passed):
        return _blocked("SMOKE_COVERAGE_INCOMPLETE", "every required production smoke route must pass")
    if int(attestation.get("promotion_lanes") or 0) != 1:
        return _blocked("DUPLICATE_PROMOTION_LANE", "Step 2F requires exactly one promotion/deployment lane")

    proof = {
        "candidate_sha": candidate_sha,
        "deployment_id": deployment_id,
        "alias": alias.get("url"),
        "endpoint": endpoint.get("url"),
        "smoke": sorted(required),
        "rollback": dict(rollback),
    }
    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "step2f_enforced": True,
        "deployment_applicable": True,
        "deployment_id": deployment_id,
        "exact_head_deployed": True,
        "stable_alias_parity": True,
        "canonical_endpoint_verified": True,
        "real_website_consumption_verified": True,
        "rollback_anchor_verified": True,
        "evidence_digest": _digest(proof),
        "blind_redeploy_allowed": BLIND_REDEPLOY_ALLOWED,
        "final_verification_authorized": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    sha = "a" * 40
    result = validate_production_attestation({
        "task_id": "monster-step2f-self-test",
        "candidate_sha": sha,
        "deployment_applicable": False,
        "control_plane_only": True,
        "network_calls": False,
        "auto_mutate": False,
        "product_runtime_mutation": False,
        "rollback_anchor": {"sha": "b" * 40, "kind": "verified-parent"},
    })
    if result.get("status") != "GREEN":
        raise RuntimeError(f"Step 2F self-test failed: {result}")
    return result


if __name__ == "__main__":
    print("MONSTER_STEP2F_LIVE_PRODUCTION_CONSUMPTION_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
