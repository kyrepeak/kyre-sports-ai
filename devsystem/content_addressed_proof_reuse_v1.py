"""MONSTER V6 Step 1 — Content-Addressed Proof Reuse V1.

A read-only proof-reuse decision engine. Reuse is allowed only for static,
content-addressed proof when every protected artifact blob, dependency blob,
proof-policy identity, proof scope, and terminal-success receipt still match.

Head movement by itself does not invalidate a content-addressed proof. Any
content, dependency, policy, scope, receipt, or proof-kind drift fails closed
to a new proof run.

This module performs no network calls and grants no mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_V6_CONTENT_ADDRESSED_PROOF_REUSE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REUSABLE_KINDS = {"STATIC_CONTENT"}


class ProofReuseFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise ProofReuseFailure(f"{field} must be a full 40-character SHA")
    return text


def _blob_map(value: Mapping[str, Any], field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ProofReuseFailure(f"{field} must be an object")
    out: dict[str, str] = {}
    for raw_path, raw_sha in value.items():
        path = str(raw_path or "").strip().replace("\\", "/")
        if not path or path.startswith("../") or "/../" in path:
            raise ProofReuseFailure(f"{field} contains invalid path")
        out[path] = _sha(raw_sha, f"{field}.{path}")
    if not out:
        raise ProofReuseFailure(f"{field} must not be empty")
    return dict(sorted(out.items()))


def _scope(values: Sequence[Any]) -> list[str]:
    out = sorted({str(v or "").strip().upper() for v in values if str(v or "").strip()})
    if not out:
        raise ProofReuseFailure("proof scope must not be empty")
    return out


def _fingerprint_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(receipt))
    out.pop("content_fingerprint", None)
    return out


def validate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise ProofReuseFailure("receipt must be an object")
    out = deepcopy(dict(receipt))
    if out.get("version") != VERSION or int(out.get("schema_version", 0)) != 1:
        raise ProofReuseFailure("receipt version/schema mismatch")
    out["checkpoint_id"] = str(out.get("checkpoint_id") or "").strip()
    if not out["checkpoint_id"]:
        raise ProofReuseFailure("checkpoint_id required")
    out["source_main_sha"] = _sha(out.get("source_main_sha"), "source_main_sha")
    out["proof_run_id"] = int(out.get("proof_run_id") or 0)
    if out["proof_run_id"] <= 0:
        raise ProofReuseFailure("proof_run_id must be positive")
    out["terminal_state"] = str(out.get("terminal_state") or "").strip().upper()
    out["terminal_receipt_digest"] = str(out.get("terminal_receipt_digest") or "").strip().lower()
    if not _DIGEST.fullmatch(out["terminal_receipt_digest"]):
        raise ProofReuseFailure("terminal_receipt_digest invalid")
    out["proof_policy_version"] = str(out.get("proof_policy_version") or "").strip()
    if not out["proof_policy_version"]:
        raise ProofReuseFailure("proof_policy_version required")
    out["proof_kind"] = str(out.get("proof_kind") or "").strip().upper()
    if not out["proof_kind"]:
        raise ProofReuseFailure("proof_kind required")
    out["proof_scope"] = _scope(out.get("proof_scope") or [])
    out["artifacts"] = _blob_map(out.get("artifacts") or {}, "artifacts")
    out["dependencies"] = _blob_map(out.get("dependencies") or {}, "dependencies")
    supplied = str(out.get("content_fingerprint") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", supplied):
        raise ProofReuseFailure("content_fingerprint invalid")
    expected = _hash(_fingerprint_payload(out))
    if supplied != expected:
        raise ProofReuseFailure("content_fingerprint mismatch")
    return out


def build_receipt(
    *,
    checkpoint_id: str,
    source_main_sha: str,
    proof_run_id: int,
    terminal_receipt_digest: str,
    proof_policy_version: str,
    proof_scope: Sequence[str],
    artifacts: Mapping[str, str],
    dependencies: Mapping[str, str],
    proof_kind: str = "STATIC_CONTENT",
) -> dict[str, Any]:
    receipt = {
        "schema_version": 1,
        "version": VERSION,
        "checkpoint_id": str(checkpoint_id or "").strip(),
        "source_main_sha": _sha(source_main_sha, "source_main_sha"),
        "proof_run_id": int(proof_run_id),
        "terminal_state": "SUCCESS",
        "terminal_receipt_digest": str(terminal_receipt_digest or "").strip().lower(),
        "proof_policy_version": str(proof_policy_version or "").strip(),
        "proof_kind": str(proof_kind or "").strip().upper(),
        "proof_scope": _scope(proof_scope),
        "artifacts": _blob_map(artifacts, "artifacts"),
        "dependencies": _blob_map(dependencies, "dependencies"),
    }
    if not receipt["checkpoint_id"] or receipt["proof_run_id"] <= 0:
        raise ProofReuseFailure("checkpoint/proof identity invalid")
    if not _DIGEST.fullmatch(receipt["terminal_receipt_digest"]):
        raise ProofReuseFailure("terminal_receipt_digest invalid")
    if not receipt["proof_policy_version"]:
        raise ProofReuseFailure("proof_policy_version required")
    receipt["content_fingerprint"] = _hash(receipt)
    return validate_receipt(receipt)


def from_frozen_checkpoint(
    entry: Mapping[str, Any],
    *,
    proof_policy_version: str,
    proof_scope: Sequence[str],
    dependencies: Mapping[str, str],
    proof_kind: str = "STATIC_CONTENT",
) -> dict[str, Any]:
    if not isinstance(entry, Mapping) or str(entry.get("status") or "").upper() != "FROZEN":
        raise ProofReuseFailure("checkpoint must be FROZEN")
    proof_run_id = int(entry.get("proof_run_id") or 0)
    terminal = str(entry.get("terminal_receipt_digest") or "")
    if proof_run_id <= 0 or not _DIGEST.fullmatch(terminal.lower()):
        raise ProofReuseFailure("frozen checkpoint lacks reusable terminal proof")
    return build_receipt(
        checkpoint_id=str(entry.get("checkpoint_id") or ""),
        source_main_sha=str(entry.get("proven_merge_sha") or entry.get("source_main_sha") or ""),
        proof_run_id=proof_run_id,
        terminal_receipt_digest=terminal,
        proof_policy_version=proof_policy_version,
        proof_scope=proof_scope,
        artifacts=dict(entry.get("artifacts") or {}),
        dependencies=dependencies,
        proof_kind=proof_kind,
    )


def evaluate_reuse(
    receipt: Mapping[str, Any],
    *,
    observed_artifacts: Mapping[str, str],
    observed_dependencies: Mapping[str, str],
    required_scope: Sequence[str],
    proof_policy_version: str,
    current_head_sha: str,
) -> dict[str, Any]:
    try:
        proof = validate_receipt(receipt)
    except ProofReuseFailure as exc:
        return {
            "version": VERSION,
            "decision": "NEW_PROOF_REQUIRED",
            "reusable": False,
            "reasons": ["INVALID_OR_TAMPERED_RECEIPT"],
            "detail": str(exc),
            "next_legal_action": "RUN_NEW_PROOF",
        }

    current_head = _sha(current_head_sha, "current_head_sha")
    observed_a = _blob_map(observed_artifacts, "observed_artifacts")
    observed_d = _blob_map(observed_dependencies, "observed_dependencies")
    needed_scope = _scope(required_scope)
    policy = str(proof_policy_version or "").strip()

    reasons: list[str] = []
    if proof["terminal_state"] != "SUCCESS":
        reasons.append("TERMINAL_PROOF_NOT_SUCCESS")
    if proof["proof_kind"] not in _REUSABLE_KINDS:
        reasons.append("PROOF_KIND_NOT_CONTENT_REUSABLE")
    if proof["proof_policy_version"] != policy:
        reasons.append("PROOF_POLICY_DRIFT")
    if proof["artifacts"] != observed_a:
        reasons.append("ARTIFACT_BLOB_DRIFT")
    if proof["dependencies"] != observed_d:
        reasons.append("DEPENDENCY_BLOB_DRIFT")
    if not set(needed_scope).issubset(set(proof["proof_scope"])):
        reasons.append("PROOF_SCOPE_INSUFFICIENT")

    reusable = not reasons
    return {
        "version": VERSION,
        "decision": "REUSE_APPROVED" if reusable else "NEW_PROOF_REQUIRED",
        "reusable": reusable,
        "checkpoint_id": proof["checkpoint_id"],
        "proof_run_id": proof["proof_run_id"],
        "source_main_sha": proof["source_main_sha"],
        "current_head_sha": current_head,
        "head_moved": current_head != proof["source_main_sha"],
        "content_fingerprint": proof["content_fingerprint"],
        "reasons": reasons,
        "next_legal_action": "REUSE_TERMINAL_PROOF" if reusable else "RUN_NEW_PROOF",
        "protections": {
            "content_identity_required": True,
            "dependency_identity_required": True,
            "proof_policy_identity_required": True,
            "terminal_success_required": True,
            "scope_subset_required": True,
            "production_and_live_proof_never_reused": True,
            "unrelated_head_movement_allowed": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        },
    }


def contract_self_test() -> dict[str, Any]:
    a = "a" * 40
    b = "b" * 40
    c = "c" * 40
    digest = "sha256:" + "d" * 64
    artifacts = {"feature.py": a, "tests/test_feature.py": b}
    deps = {"shared/contract.py": c}
    receipt = build_receipt(
        checkpoint_id="TEST_STEP",
        source_main_sha=a,
        proof_run_id=123,
        terminal_receipt_digest=digest,
        proof_policy_version="policy-v1",
        proof_scope=["STATIC_CONTRACT", "FOCUSED_TEST"],
        artifacts=artifacts,
        dependencies=deps,
    )
    same_new_head = evaluate_reuse(
        receipt,
        observed_artifacts=artifacts,
        observed_dependencies=deps,
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v1",
        current_head_sha=b,
    )
    artifact_drift = evaluate_reuse(
        receipt,
        observed_artifacts={**artifacts, "feature.py": c},
        observed_dependencies=deps,
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v1",
        current_head_sha=b,
    )
    dependency_drift = evaluate_reuse(
        receipt,
        observed_artifacts=artifacts,
        observed_dependencies={"shared/contract.py": a},
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v1",
        current_head_sha=b,
    )
    policy_drift = evaluate_reuse(
        receipt,
        observed_artifacts=artifacts,
        observed_dependencies=deps,
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v2",
        current_head_sha=b,
    )
    scope_drift = evaluate_reuse(
        receipt,
        observed_artifacts=artifacts,
        observed_dependencies=deps,
        required_scope=["PRODUCTION_CERTIFICATION"],
        proof_policy_version="policy-v1",
        current_head_sha=b,
    )
    live_receipt = build_receipt(
        checkpoint_id="LIVE_STEP",
        source_main_sha=a,
        proof_run_id=124,
        terminal_receipt_digest=digest,
        proof_policy_version="policy-v1",
        proof_scope=["PRODUCTION_CERTIFICATION"],
        artifacts=artifacts,
        dependencies=deps,
        proof_kind="PRODUCTION_STATE",
    )
    live = evaluate_reuse(
        live_receipt,
        observed_artifacts=artifacts,
        observed_dependencies=deps,
        required_scope=["PRODUCTION_CERTIFICATION"],
        proof_policy_version="policy-v1",
        current_head_sha=b,
    )
    tampered = deepcopy(receipt)
    tampered["artifacts"]["feature.py"] = c
    tamper = evaluate_reuse(
        tampered,
        observed_artifacts=artifacts,
        observed_dependencies=deps,
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v1",
        current_head_sha=b,
    )
    frozen = from_frozen_checkpoint(
        {
            "status": "FROZEN",
            "checkpoint_id": "FROZEN_STEP",
            "source_main_sha": a,
            "proven_merge_sha": a,
            "proof_run_id": 999,
            "terminal_receipt_digest": digest,
            "artifacts": artifacts,
        },
        proof_policy_version="policy-v1",
        proof_scope=["STATIC_CONTRACT"],
        dependencies=deps,
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "identical_content_reuses_after_unrelated_head_move": (
            same_new_head["reusable"] is True
            and same_new_head["head_moved"] is True
            and same_new_head["decision"] == "REUSE_APPROVED"
        ),
        "artifact_drift_requires_new_proof": "ARTIFACT_BLOB_DRIFT" in artifact_drift["reasons"],
        "dependency_drift_requires_new_proof": "DEPENDENCY_BLOB_DRIFT" in dependency_drift["reasons"],
        "policy_drift_requires_new_proof": "PROOF_POLICY_DRIFT" in policy_drift["reasons"],
        "scope_growth_requires_new_proof": "PROOF_SCOPE_INSUFFICIENT" in scope_drift["reasons"],
        "production_state_proof_not_reused": "PROOF_KIND_NOT_CONTENT_REUSABLE" in live["reasons"],
        "tamper_fails_closed": tamper["reusable"] is False,
        "frozen_registry_checkpoint_can_seed_receipt": frozen["checkpoint_id"] == "FROZEN_STEP",
        "step_2a_still_required_for_mutation": MUTATION_AUTHORITY_GRANTED is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        "identical_content_reuses_after_unrelated_head_move",
        "artifact_drift_requires_new_proof",
        "dependency_drift_requires_new_proof",
        "policy_drift_requires_new_proof",
        "scope_growth_requires_new_proof",
        "production_state_proof_not_reused",
        "tamper_fails_closed",
        "frozen_registry_checkpoint_can_seed_receipt",
        "step_2a_still_required_for_mutation",
    ]
    if not all(result[key] is True for key in required):
        raise ProofReuseFailure("content-addressed proof reuse self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"]:
        raise ProofReuseFailure("read-only safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V6_CONTENT_ADDRESSED_PROOF_REUSE_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProofReuseFailure as exc:
        print(f"MONSTER_V6_CONTENT_ADDRESSED_PROOF_REUSE_BLOCKED: {exc}")
        raise SystemExit(1)
