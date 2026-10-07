"""Runless Task 17 Step 3 — content-addressed post-merge proof reuse.

A pre-merge Runless terminal proof may be reused on merged main only when:
- the proof was terminal-success and structurally valid;
- the candidate is an ancestor of merged main and the head actually moved;
- the proof plan remains static-only (no public/live probes);
- proof-policy content is byte-for-byte equivalent by canonical digest;
- every protected artifact and dependency blob is unchanged.

This module is read-only. It never executes static evidence, publishes a gate,
mutates GitHub, or enables GitHub Actions. Callers must still enforce Step 2A
before any mutation such as publishing a reused gate or freezing a checkpoint.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from devsystem.content_addressed_proof_reuse_v1 import (
    ProofReuseFailure,
    build_receipt,
    evaluate_reuse,
)

VERSION = "RUNLESS_TASK17_POST_MERGE_PROOF_REUSE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_ENABLED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SCOPE = ("RUNLESS_FINAL_GATE", "STATIC_CONTENT")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _policy_digest(policy: Mapping[str, Any]) -> str:
    if not isinstance(policy, Mapping):
        raise ValueError("proof policy must be an object")
    return hashlib.sha256(_canonical(dict(policy)).encode("utf-8")).hexdigest()


def _new_proof_result(*, reasons: list[str], candidate_sha: str | None, merged_main_sha: str | None) -> dict[str, Any]:
    return {
        "version": VERSION,
        "decision": "NEW_PROOF_REQUIRED",
        "reusable": False,
        "reasons": sorted(set(reasons)),
        "next_legal_action": "RUN_NEW_PROOF",
        "source_candidate_sha": candidate_sha,
        "merged_main_sha": merged_main_sha,
        "head_moved": bool(candidate_sha and merged_main_sha and candidate_sha != merged_main_sha),
        "static_evidence_reexecuted": False,
        "github_actions_enabled": GITHUB_ACTIONS_ENABLED,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def evaluate_postmerge_reuse(
    *,
    premerge_receipt: Mapping[str, Any],
    merged_main_sha: str,
    merged_artifacts: Mapping[str, str],
    merged_dependencies: Mapping[str, str],
    candidate_policy: Mapping[str, Any],
    merged_policy: Mapping[str, Any],
    candidate_is_ancestor: bool,
    proof_run_id: int,
) -> dict[str, Any]:
    """Return a fail-closed decision for reusing one pre-merge Runless proof."""

    receipt = dict(premerge_receipt or {})
    candidate_sha = str(receipt.get("candidate_sha") or "").strip().lower()
    merged_sha = str(merged_main_sha or "").strip().lower()
    digest = str(receipt.get("digest") or "").strip().lower()
    proof_fingerprint = str(receipt.get("proof_fingerprint") or "").strip().lower()
    proof_id = str(receipt.get("proof_id") or "").strip()

    malformed = (
        not _SHA40.fullmatch(candidate_sha)
        or not _SHA40.fullmatch(merged_sha)
        or not _DIGEST64.fullmatch(digest)
        or not _DIGEST64.fullmatch(proof_fingerprint)
        or not proof_id
        or int(proof_run_id or 0) <= 0
        or not isinstance(receipt.get("artifact_map"), Mapping)
        or not isinstance(receipt.get("dependency_map"), Mapping)
    )
    if malformed:
        return _new_proof_result(
            reasons=["INVALID_PREMERGE_RECEIPT"],
            candidate_sha=candidate_sha or None,
            merged_main_sha=merged_sha or None,
        )

    reasons: list[str] = []
    if str(receipt.get("failure_class") or "").strip().upper() != "NONE":
        reasons.append("TERMINAL_PROOF_NOT_SUCCESS")
    if not bool(candidate_is_ancestor):
        reasons.append("CANDIDATE_NOT_ANCESTOR")
    if candidate_sha == merged_sha:
        reasons.append("HEAD_DID_NOT_MOVE")

    try:
        candidate_policy_digest = _policy_digest(candidate_policy)
        merged_policy_digest = _policy_digest(merged_policy)
    except (TypeError, ValueError):
        return _new_proof_result(
            reasons=["INVALID_PROOF_POLICY"],
            candidate_sha=candidate_sha,
            merged_main_sha=merged_sha,
        )

    candidate_probes = list(candidate_policy.get("probes") or [])
    merged_probes = list(merged_policy.get("probes") or [])
    if candidate_probes or merged_probes:
        reasons.append("DYNAMIC_PROOF_NOT_REUSABLE")
    if candidate_policy_digest != merged_policy_digest:
        reasons.append("PROOF_POLICY_DRIFT")

    if reasons:
        return _new_proof_result(
            reasons=reasons,
            candidate_sha=candidate_sha,
            merged_main_sha=merged_sha,
        )

    policy_version = f"{VERSION}:{candidate_policy_digest}"
    try:
        content_receipt = build_receipt(
            checkpoint_id=proof_id,
            source_main_sha=candidate_sha,
            proof_run_id=int(proof_run_id),
            terminal_receipt_digest="sha256:" + digest,
            proof_policy_version=policy_version,
            proof_scope=_SCOPE,
            artifacts=dict(receipt["artifact_map"]),
            dependencies=dict(receipt["dependency_map"]),
            proof_kind="STATIC_CONTENT",
        )
        decision = evaluate_reuse(
            content_receipt,
            observed_artifacts=merged_artifacts,
            observed_dependencies=merged_dependencies,
            required_scope=_SCOPE,
            proof_policy_version=policy_version,
            current_head_sha=merged_sha,
        )
    except (ProofReuseFailure, TypeError, ValueError):
        return _new_proof_result(
            reasons=["INVALID_PREMERGE_RECEIPT"],
            candidate_sha=candidate_sha,
            merged_main_sha=merged_sha,
        )

    if not decision.get("reusable"):
        return _new_proof_result(
            reasons=list(decision.get("reasons") or ["CONTENT_IDENTITY_DRIFT"]),
            candidate_sha=candidate_sha,
            merged_main_sha=merged_sha,
        )

    return {
        "version": VERSION,
        "decision": "REUSE_APPROVED",
        "reusable": True,
        "reasons": [],
        "next_legal_action": "PUBLISH_REUSED_GATE",
        "source_candidate_sha": candidate_sha,
        "merged_main_sha": merged_sha,
        "head_moved": True,
        "proof_id": proof_id,
        "proof_run_id": int(proof_run_id),
        "reused_receipt_digest": digest,
        "content_fingerprint": decision["content_fingerprint"],
        "proof_policy_digest": candidate_policy_digest,
        "artifact_count": len(receipt["artifact_map"]),
        "dependency_count": len(receipt["dependency_map"]),
        "static_evidence_reexecuted": False,
        "github_actions_enabled": GITHUB_ACTIONS_ENABLED,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
