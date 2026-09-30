"""MONSTER V4 Step 2 — Semantic Action Normalizer V1.

Canonicalizes semantically equivalent control-plane actions before the frozen
lease + 2A chain fingerprints, authorizes, or executes them.

Goal:
- spelling/URL/alias differences must not mint a new semantic action identity;
- the canonical action is the only action passed into the Step-1 leased
  enforcement wrapper;
- final V4 Step-2 authority requires a tamper-evident normalization proof.

This module performs no network calls and no repository/product mutations.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.distributed_execution_lease_v1 import enforce_leased_action
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_adversarial_certification_v1 import (
    TwoAAdversarialCertificationFailure,
    require_final_certification,
)
from devsystem.persistent_execution_brain_v1 import validate_state

VERSION = "MONSTER_V4_SEMANTIC_ACTION_NORMALIZER_V1"
PROOF_SCHEMA_VERSION = 1
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_ACTION_TYPE_ALIASES = {
    "merge": "merge",
    "merge_pr": "merge",
    "merge_pull_request": "merge",
    "pull_request_merge": "merge",
    "patch": "patch",
    "apply_patch": "patch",
    "rerun": "rerun",
    "rerun_workflow": "rerun",
    "retry_workflow": "rerun",
    "retry_run": "rerun",
    "start_run": "start_run",
    "start_workflow_run": "start_run",
    "start_async_run": "start_run",
    "start_competing_run": "start_competing_run",
    "start_competing_async_run": "start_competing_run",
    "competing_run": "start_competing_run",
    "dispatch_workflow": "dispatch_workflow",
    "workflow_dispatch": "dispatch_workflow",
    "dispatch_run": "dispatch_workflow",
    "update_branch": "update_branch",
    "branch_update": "update_branch",
    "update_branch_ref": "update_branch",
    "create_pr": "create_pr",
    "create_pull_request": "create_pr",
    "open_pr": "create_pr",
    "open_pull_request": "create_pr",
    "edit_product": "edit_product",
    "edit_product_runtime": "edit_product",
    "edit_runtime": "edit_product",
    "observe_async": "observe_async",
    "observe": "observe_async",
    "observe_run": "observe_async",
    "poll_status": "observe_async",
    "poll": "observe_async",
    "poll_run": "observe_async",
    "read_status": "observe_async",
    "read_run_status": "observe_async",
    "gather_evidence": "gather_evidence",
    "gather_proof": "gather_evidence",
    "classify_terminal_result": "classify_terminal_result",
    "classify_result": "classify_terminal_result",
}

_ID_KEYS = {
    "pr_number",
    "pull_request_number",
    "run_id",
    "job_id",
    "workflow_run_id",
    "authoritative_run_id",
    "authoritative_job_id",
}
_SHA_KEYS = {
    "sha",
    "main_sha",
    "head_sha",
    "commit_sha",
    "expected_head_sha",
    "base_sha",
}
_REPO_KEYS = {"repository", "repository_full_name", "repo"}
_BRANCH_KEYS = {"branch", "head_branch", "base_branch", "work_branch"}

_PR_LOCAL_RE = re.compile(
    r"^(?:github:)?(?:pr|pull|pull_request|pull-request)[/:# ]+(\d+)$",
    re.IGNORECASE,
)
_PR_HASH_RE = re.compile(r"^(?:pr|pull request)\s*#(\d+)$", re.IGNORECASE)
_RUN_LOCAL_RE = re.compile(r"^(?:github:)?(?:run|workflow_run|workflow-run)[/:# ]+(\d+)$", re.IGNORECASE)
_JOB_LOCAL_RE = re.compile(r"^(?:github:)?job[/:# ]+(\d+)$", re.IGNORECASE)
_BRANCH_LOCAL_RE = re.compile(r"^(?:github:)?branch[:/](.+)$", re.IGNORECASE)


class SemanticActionNormalizerFailure(RuntimeError):
    pass


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _repository(value: str) -> str:
    repo = str(value or "").strip().strip("/").lower()
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise SemanticActionNormalizerFailure("repository must be owner/name")
    return repo


def _token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def normalize_action_type(value: Any) -> str:
    token = _token(value)
    if not token:
        raise SemanticActionNormalizerFailure("action_type is required")
    return _ACTION_TYPE_ALIASES.get(token, token)


def _normalize_branch(value: Any) -> str:
    branch = str(value or "").strip()
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/") :]
    return branch


def _normalize_payload(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): _normalize_payload(v, key=str(k))
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_payload(item) for item in value]

    normalized_key = str(key or "").lower()
    if normalized_key in _ID_KEYS:
        text = str(value or "").strip()
        return int(text) if text.isdigit() else text
    if normalized_key in _SHA_KEYS:
        return str(value or "").strip().lower()
    if normalized_key in _REPO_KEYS:
        text = str(value or "").strip().strip("/")
        return text.lower()
    if normalized_key in _BRANCH_KEYS:
        return _normalize_branch(value)
    if isinstance(value, str):
        return value.strip()
    return value


def normalize_target(target: Any, *, repository: str) -> str:
    repo = _repository(repository)
    owner, name = repo.split("/", 1)
    raw = str(target or "").strip()
    if not raw:
        raise SemanticActionNormalizerFailure("target is required")

    pr_match = _PR_LOCAL_RE.match(raw) or _PR_HASH_RE.match(raw)
    if pr_match:
        return f"github:pr/{repo}/{int(pr_match.group(1))}"

    run_match = _RUN_LOCAL_RE.match(raw)
    if run_match:
        return f"github:run/{repo}/{int(run_match.group(1))}"

    job_match = _JOB_LOCAL_RE.match(raw)
    if job_match:
        return f"github:job/{repo}/{int(job_match.group(1))}"

    branch_match = _BRANCH_LOCAL_RE.match(raw)
    if branch_match:
        return f"github:branch/{repo}/{_normalize_branch(branch_match.group(1))}"

    if raw.startswith("refs/heads/"):
        return f"github:branch/{repo}/{_normalize_branch(raw)}"

    try:
        parsed = urlparse(raw)
    except ValueError:
        parsed = None

    if parsed and parsed.scheme.lower() in {"http", "https"}:
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")
        parts = [part for part in path.split("/") if part]

        if host == "github.com" and len(parts) >= 4:
            url_repo = f"{parts[0].lower()}/{parts[1].lower()}"
            if parts[2].lower() == "pull" and parts[3].isdigit():
                return f"github:pr/{url_repo}/{int(parts[3])}"
            if len(parts) >= 5 and parts[2].lower() == "actions" and parts[3].lower() == "runs" and parts[4].isdigit():
                if len(parts) >= 7 and parts[5].lower() == "job" and parts[6].isdigit():
                    return f"github:job/{url_repo}/{int(parts[6])}"
                return f"github:run/{url_repo}/{int(parts[4])}"

        if host == "api.github.com" and len(parts) >= 5 and parts[0].lower() == "repos":
            url_repo = f"{parts[1].lower()}/{parts[2].lower()}"
            kind = parts[3].lower()
            ident = parts[4]
            if kind in {"pulls", "pull"} and ident.isdigit():
                return f"github:pr/{url_repo}/{int(ident)}"
            if kind in {"actions", "runs"}:
                run_id = parts[-1]
                if run_id.isdigit():
                    return f"github:run/{url_repo}/{int(run_id)}"

    lowered = raw.lower()
    prefix = f"github:pr/{repo}/"
    if lowered.startswith(prefix) and raw[len(prefix):].isdigit():
        return f"github:pr/{repo}/{int(raw[len(prefix):])}"
    prefix = f"github:run/{repo}/"
    if lowered.startswith(prefix) and raw[len(prefix):].isdigit():
        return f"github:run/{repo}/{int(raw[len(prefix):])}"
    prefix = f"github:job/{repo}/"
    if lowered.startswith(prefix) and raw[len(prefix):].isdigit():
        return f"github:job/{repo}/{int(raw[len(prefix):])}"

    return re.sub(r"\s+", " ", raw).strip()


def canonicalize_action(action: Mapping[str, Any], *, repository: str) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise SemanticActionNormalizerFailure("action must be an object")

    required = ("task_id", "checkpoint_id", "action_type", "target")
    missing = [field for field in required if not str(action.get(field) or "").strip()]
    if missing:
        raise SemanticActionNormalizerFailure(
            "action missing required fields: " + ", ".join(missing)
        )

    result = deepcopy(dict(action))
    result["task_id"] = str(action["task_id"]).strip().lower()

    checkpoint = str(action["checkpoint_id"]).strip()
    if checkpoint.isdigit():
        checkpoint = str(int(checkpoint))
    result["checkpoint_id"] = checkpoint

    result["action_type"] = normalize_action_type(action["action_type"])
    result["target"] = normalize_target(action["target"], repository=repository)

    for field in (
        "inputs",
        "evidence",
        "contradictory_evidence",
        "failure",
    ):
        if field in result:
            result[field] = _normalize_payload(result[field])

    if "failure_class" in result:
        result["failure_class"] = str(result.get("failure_class") or "").strip().upper()

    if "command" in result:
        command = result["command"]
        if isinstance(command, (list, tuple)):
            result["command"] = [str(item).strip() for item in command]
        elif command:
            result["command"] = [str(command).strip()]

    return result


def semantic_fingerprint(action: Mapping[str, Any], *, repository: str) -> str:
    return fingerprint_action(canonicalize_action(action, repository=repository))


def build_normalization_proof(
    raw_action: Mapping[str, Any],
    canonical_action: Mapping[str, Any],
    *,
    repository: str,
) -> dict[str, Any]:
    repo = _repository(repository)
    raw_fp = fingerprint_action(dict(raw_action))
    canonical_fp = fingerprint_action(dict(canonical_action))
    body = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "version": VERSION,
        "repository": repo,
        "raw_action_fingerprint": raw_fp,
        "canonical_action_fingerprint": canonical_fp,
        "raw_action_type": str(raw_action.get("action_type") or ""),
        "canonical_action_type": str(canonical_action.get("action_type") or ""),
        "raw_target": str(raw_action.get("target") or ""),
        "canonical_target": str(canonical_action.get("target") or ""),
        "normalization_changed": dict(raw_action) != dict(canonical_action),
    }
    return {"payload": body, "proof_hash": _hash(body)}


def validate_normalization_proof(
    proof: Mapping[str, Any],
    raw_action: Mapping[str, Any],
    *,
    repository: str,
) -> dict[str, Any]:
    if not isinstance(proof, Mapping):
        raise SemanticActionNormalizerFailure("normalization proof must be an object")
    payload = proof.get("payload")
    if not isinstance(payload, Mapping):
        raise SemanticActionNormalizerFailure("normalization proof payload missing")
    if int(payload.get("schema_version") or 0) != PROOF_SCHEMA_VERSION:
        raise SemanticActionNormalizerFailure("normalization proof schema mismatch")
    if str(payload.get("version") or "") != VERSION:
        raise SemanticActionNormalizerFailure("normalization proof version mismatch")
    if str(payload.get("repository") or "") != _repository(repository):
        raise SemanticActionNormalizerFailure("normalization proof repository mismatch")
    if str(proof.get("proof_hash") or "") != _hash(dict(payload)):
        raise SemanticActionNormalizerFailure("normalization proof hash mismatch")

    canonical = canonicalize_action(raw_action, repository=repository)
    raw_fp = fingerprint_action(dict(raw_action))
    canonical_fp = fingerprint_action(canonical)
    if str(payload.get("raw_action_fingerprint") or "") != raw_fp:
        raise SemanticActionNormalizerFailure("raw action fingerprint mismatch")
    if str(payload.get("canonical_action_fingerprint") or "") != canonical_fp:
        raise SemanticActionNormalizerFailure("canonical action fingerprint mismatch")
    if str(payload.get("canonical_action_type") or "") != canonical["action_type"]:
        raise SemanticActionNormalizerFailure("canonical action type mismatch")
    if str(payload.get("canonical_target") or "") != canonical["target"]:
        raise SemanticActionNormalizerFailure("canonical target mismatch")

    return {
        "status": "GREEN",
        "raw_action_fingerprint": raw_fp,
        "canonical_action_fingerprint": canonical_fp,
        "canonical_action": canonical,
        "proof_hash": str(proof["proof_hash"]),
    }


def enforce_semantic_action(
    lease_state: Mapping[str, Any],
    *,
    repository: str,
    owner_id: str,
    lease_id: str | None,
    now_utc: str,
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
    current_main_sha: str,
    current_head_sha: str,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonicalize_action(action, repository=repository)
    proof = build_normalization_proof(action, canonical, repository=repository)

    outcome = enforce_leased_action(
        lease_state,
        owner_id=owner_id,
        lease_id=lease_id,
        now_utc=now_utc,
        brain_state=brain_state,
        action=canonical,
        history=history,
        replay_ledger=replay_ledger,
        consumption_ledger=consumption_ledger,
        current_main_sha=current_main_sha,
        current_head_sha=current_head_sha,
        forward_decision=forward_decision,
    )
    result = deepcopy(dict(outcome["result"]))
    result["semantic_normalization_version"] = VERSION
    result["semantic_normalization_proof"] = proof
    result["semantic_normalization_authorized"] = result.get("allowed") is True
    result["raw_action_fingerprint"] = proof["payload"]["raw_action_fingerprint"]
    result["canonical_action_fingerprint"] = proof["payload"]["canonical_action_fingerprint"]
    result["canonical_action_type"] = canonical["action_type"]
    result["canonical_target"] = canonical["target"]

    return {
        "result": result,
        "canonical_action": canonical,
        "replay_ledger": deepcopy(dict(outcome["replay_ledger"])),
        "consumption_ledger": deepcopy(dict(outcome["consumption_ledger"])),
    }


def require_semantic_execution_authority(
    result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    raw_action: Mapping[str, Any],
    *,
    repository: str,
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise SemanticActionNormalizerFailure("semantic result must be an object")
    if result.get("allowed") is not True:
        raise SemanticActionNormalizerFailure("semantic action is not authorized")
    if result.get("semantic_normalization_authorized") is not True:
        raise SemanticActionNormalizerFailure("semantic normalization authority missing")
    if result.get("distributed_lease_authorized") is not True:
        raise SemanticActionNormalizerFailure("distributed lease authority missing")

    proof_validation = validate_normalization_proof(
        result.get("semantic_normalization_proof"),
        raw_action,
        repository=repository,
    )
    canonical = proof_validation["canonical_action"]
    try:
        global_validation = require_final_certification(
            result,
            brain_state,
            canonical,
        )
    except TwoAAdversarialCertificationFailure as exc:
        raise SemanticActionNormalizerFailure(str(exc)) from exc

    if str(result.get("canonical_action_fingerprint") or "") != proof_validation["canonical_action_fingerprint"]:
        raise SemanticActionNormalizerFailure("result canonical fingerprint mismatch")
    if str(result.get("canonical_target") or "") != canonical["target"]:
        raise SemanticActionNormalizerFailure("result canonical target mismatch")

    return {
        "status": "GREEN",
        "normalization_proof_hash": proof_validation["proof_hash"],
        "canonical_action_fingerprint": proof_validation["canonical_action_fingerprint"],
        "canonical_action": canonical,
        "global_proof_hash": global_validation["proof_hash"],
    }


def contract_self_test() -> dict[str, Any]:
    from devsystem.action_ledger_v2 import build_receipt
    from devsystem.distributed_execution_lease_v1 import claim_lease, new_lease_state
    from devsystem.mandatory_2a_receipt_v1 import new_consumption_ledger
    from devsystem.mandatory_2a_replay_lock_v1 import new_replay_ledger
    from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state

    repo = "owner/repo"
    main_sha = "1" * 40
    head_sha = "2" * 40
    owner = "chat:semantic-self-test"
    now = "2026-09-30T05:10:00Z"

    raw_a = {
        "task_id": " Test-Task ",
        "checkpoint_id": "02",
        "action_type": "merge pull request",
        "target": "PR #42",
        "inputs": {"head_sha": ("A" * 40), "pr_number": "42"},
    }
    raw_b = {
        "task_id": "test-task",
        "checkpoint_id": 2,
        "action_type": "merge_pr",
        "target": "https://github.com/owner/repo/pull/42",
        "inputs": {"head_sha": ("a" * 40), "pr_number": 42},
    }
    raw_c = {
        **raw_b,
        "target": "https://github.com/owner/repo/pull/43",
        "inputs": {"head_sha": ("a" * 40), "pr_number": 43},
    }

    canonical_a = canonicalize_action(raw_a, repository=repo)
    canonical_b = canonicalize_action(raw_b, repository=repo)
    canonical_c = canonicalize_action(raw_c, repository=repo)

    lease0 = new_lease_state(repo)
    claimed = claim_lease(
        lease0,
        owner_id=owner,
        now_utc=now,
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        expected_revision=lease0["revision"],
        expected_state_hash=lease0["state_hash"],
    )
    live_lease = claimed["state"]
    lease_id = claimed["result"]["lease_id"]

    brain = build_state(BrainStateInput(
        program_id="semantic-self-test",
        program_title="MONSTER V4 semantic normalizer",
        total_steps=6,
        current_step=2,
        step_title="Semantic Action Normalizer",
        execution_state="ACTIVE",
        repository=repo,
        main_sha=main_sha,
        work_branch="monster-v4-step2",
        observed_head_sha=head_sha,
        next_legal_action="Continue under semantic identity.",
        completed_steps=(1,),
        frozen_steps=(1,),
        remaining_steps=(3, 4, 5, 6),
        updated_at_utc=now,
    ))

    def forward_for(canonical_action: Mapping[str, Any], nonce: str):
        return {
            "decision": "AUTHORIZED",
            "receipt": build_receipt({
                "policy_version": 2,
                "task_id": str(canonical_action["task_id"]),
                "checkpoint_id": str(canonical_action["checkpoint_id"]),
                "action_fingerprint": fingerprint_action(dict(canonical_action)),
                "root_cause_fingerprint": "r" * 64,
                "evidence_fingerprint": "e" * 64,
                "relevant_input_fingerprint": "i" * 64,
                "decision": "AUTHORIZED",
                "previous_chain_hash": "0" * 64,
                "event_nonce": nonce,
                "override_event_id": None,
            }),
        }

    first = enforce_semantic_action(
        live_lease,
        repository=repo,
        owner_id=owner,
        lease_id=lease_id,
        now_utc="2026-09-30T05:11:00Z",
        brain_state=brain,
        action=raw_a,
        history=[],
        replay_ledger=new_replay_ledger(),
        consumption_ledger=new_consumption_ledger(),
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        forward_decision=forward_for(canonical_a, "semantic-first"),
    )
    first_validation = require_semantic_execution_authority(
        first["result"],
        brain,
        raw_a,
        repository=repo,
    )

    replay = enforce_semantic_action(
        live_lease,
        repository=repo,
        owner_id=owner,
        lease_id=lease_id,
        now_utc="2026-09-30T05:12:00Z",
        brain_state=brain,
        action=raw_b,
        history=[],
        replay_ledger=first["replay_ledger"],
        consumption_ledger=first["consumption_ledger"],
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        forward_decision=forward_for(canonical_b, "semantic-second-alias"),
    )

    raw_step1_blocked = False
    raw_step1_result = deepcopy(first["result"])
    raw_step1_result.pop("semantic_normalization_proof", None)
    raw_step1_result.pop("semantic_normalization_authorized", None)
    try:
        require_semantic_execution_authority(
            raw_step1_result,
            brain,
            raw_a,
            repository=repo,
        )
    except SemanticActionNormalizerFailure:
        raw_step1_blocked = True

    tampered = deepcopy(first["result"])
    tampered["semantic_normalization_proof"]["payload"]["canonical_target"] = "github:pr/owner/repo/999"
    tamper_blocked = False
    try:
        require_semantic_execution_authority(
            tampered,
            brain,
            raw_a,
            repository=repo,
        )
    except SemanticActionNormalizerFailure:
        tamper_blocked = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "alias_targets_equal": canonical_a["target"] == canonical_b["target"],
        "alias_action_types_equal": canonical_a["action_type"] == canonical_b["action_type"] == "merge",
        "alias_payloads_equal": canonical_a["inputs"] == canonical_b["inputs"],
        "semantic_fingerprints_equal": fingerprint_action(canonical_a) == fingerprint_action(canonical_b),
        "different_action_stays_distinct": fingerprint_action(canonical_b) != fingerprint_action(canonical_c),
        "canonical_target": canonical_a["target"],
        "first_alias_authorized": first["result"].get("semantic_normalization_authorized") is True,
        "second_alias_replay_skipped": replay["result"].get("decision") == "LOOP_SKIPPED_CONTINUE",
        "raw_step1_authority_rejected": raw_step1_blocked,
        "tampered_normalization_proof_rejected": tamper_blocked,
        "normalization_proof_valid": first_validation["status"] == "GREEN",
        "distributed_lease_preserved": first["result"].get("distributed_lease_authorized") is True,
        "two_a_chain_preserved": first["result"].get("certified") is True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "alias_targets_equal",
        "alias_action_types_equal",
        "alias_payloads_equal",
        "semantic_fingerprints_equal",
        "different_action_stays_distinct",
        "first_alias_authorized",
        "second_alias_replay_skipped",
        "raw_step1_authority_rejected",
        "tampered_normalization_proof_rejected",
        "normalization_proof_valid",
        "distributed_lease_preserved",
        "two_a_chain_preserved",
    )
    if not all(result[key] is True for key in required):
        raise SemanticActionNormalizerFailure("semantic normalizer self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_V4_SEMANTIC_ACTION_NORMALIZER_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
