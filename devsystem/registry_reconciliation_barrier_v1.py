"""Registry Race Repair V1 Step 1 — Reconciliation Barrier.

Read-only guard that runs before frozen-registry verification.

It distinguishes three states:
1) READY: frozen blobs are aligned, or every mismatch is covered by an exact
   candidate-head thaw.
2) WAIT: every non-candidate mismatch is covered by a thaw that has been newly
   merged into authoritative main, but the registry baseline has not caught up.
3) BLOCKED: at least one mismatch lacks unique authorized thaw evidence.

The barrier never writes Git, never mutates the registry, never dispatches
workflows, and never grants mutation authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.frozen_artifact_registry_v1 import (
    _hash,
    _payload_without_hash,
    git_blob_map,
    git_head_sha,
    validate_registry,
)
from devsystem.frozen_registry_auto_reconciler_v1 import (
    VERSION as AUTO_RECONCILER_VERSION,
    newly_merged_thaw_targets,
)

VERSION = "MONSTER_REGISTRY_RACE_V1_STEP1_RECONCILIATION_BARRIER_V1"
EXPECTED_AUTO_RECONCILER_VERSION = (
    "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP4_FROZEN_REGISTRY_AUTO_RECONCILIATION_V1"
)
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class RegistryReconciliationBarrierFailure(RuntimeError):
    pass


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise RegistryReconciliationBarrierFailure(f"{label} must be a full SHA")
    return text


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any) -> str:
    return "BARRIER-" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:32].upper()


def _matching_grants(
    registry: Mapping[str, Any],
    *,
    path: str,
    expected_blob: str,
    actual_blob: str,
    allowed_targets: set[str],
) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for grant in registry["active_thaws"]:
        target = str(grant["target_head_sha"]).lower()
        if target not in allowed_targets:
            continue
        pair = grant["files"].get(path)
        if not isinstance(pair, Mapping):
            continue
        if (
            str(pair.get("from_blob") or "").lower() == expected_blob
            and str(pair.get("to_blob") or "").lower() == actual_blob
        ):
            matches.append(
                {
                    "thaw_id": str(grant["thaw_id"]),
                    "target_head_sha": target,
                    "path": path,
                    "from_blob": expected_blob,
                    "to_blob": actual_blob,
                }
            )
    return matches


def evaluate_barrier(
    registry: Mapping[str, Any],
    actual_blobs: Mapping[str, str | None],
    *,
    candidate_head_sha: str,
    current_main_sha: str,
    newly_merged_targets: Sequence[str] = (),
) -> dict[str, Any]:
    """Classify whether frozen verification may legally proceed."""
    if AUTO_RECONCILER_VERSION != EXPECTED_AUTO_RECONCILER_VERSION:
        raise RegistryReconciliationBarrierFailure(
            "frozen auto-reconciler parent version drift"
        )

    validated = validate_registry(registry)
    candidate = _sha(candidate_head_sha, "candidate_head_sha")
    current_main = _sha(current_main_sha, "current_main_sha")
    registry_source = _sha(registry["source_main_sha"], "registry source_main_sha")

    active_targets = {
        str(grant["target_head_sha"]).lower() for grant in registry["active_thaws"]
    }
    merged_targets = {
        _sha(value, "newly merged target") for value in newly_merged_targets
    }
    unknown_targets = sorted(merged_targets - active_targets)
    if unknown_targets:
        raise RegistryReconciliationBarrierFailure(
            "newly merged target is not an active thaw: " + ", ".join(unknown_targets)
        )

    exact_candidate_targets = {candidate} if candidate in active_targets else set()

    exact_candidate_thaws: list[dict[str, str]] = []
    reconciliation_required: list[dict[str, str]] = []
    blocked_mismatches: list[dict[str, Any]] = []

    for path, expected in sorted(validated["artifacts"].items()):
        raw_actual = actual_blobs.get(path)
        actual = str(raw_actual).lower() if raw_actual else None
        if actual == expected:
            continue
        if actual is None:
            blocked_mismatches.append(
                {
                    "path": path,
                    "expected_blob": expected,
                    "actual_blob": None,
                    "reason": "FROZEN_ARTIFACT_DELETED",
                }
            )
            continue

        exact = _matching_grants(
            registry,
            path=path,
            expected_blob=expected,
            actual_blob=actual,
            allowed_targets=exact_candidate_targets,
        )
        merged = _matching_grants(
            registry,
            path=path,
            expected_blob=expected,
            actual_blob=actual,
            allowed_targets=merged_targets,
        )

        unique = exact + [item for item in merged if item not in exact]
        if len(unique) != 1:
            blocked_mismatches.append(
                {
                    "path": path,
                    "expected_blob": expected,
                    "actual_blob": actual,
                    "reason": (
                        "NO_UNIQUE_AUTHORITY"
                        if not unique
                        else "AMBIGUOUS_THAW_AUTHORITY"
                    ),
                    "matching_authorities": len(unique),
                }
            )
            continue

        authority = unique[0]
        if authority["target_head_sha"] == candidate:
            exact_candidate_thaws.append(authority)
        elif authority["target_head_sha"] in merged_targets:
            reconciliation_required.append(authority)
        else:
            blocked_mismatches.append(
                {
                    "path": path,
                    "expected_blob": expected,
                    "actual_blob": actual,
                    "reason": "THAW_AUTHORITY_NOT_LEGAL_FOR_STATE",
                }
            )

    basis = {
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "registry_source_main_sha": registry_source,
        "current_main_sha": current_main,
        "candidate_head_sha": candidate,
        "exact_candidate_thaws": exact_candidate_thaws,
        "reconciliation_required": reconciliation_required,
        "blocked_mismatches": blocked_mismatches,
    }
    token = _fingerprint(basis)

    if blocked_mismatches:
        return {
            "version": VERSION,
            "status": "BLOCKED",
            "decision": "UNAUTHORIZED_FROZEN_DRIFT",
            "allow_frozen_verification": False,
            "hard_failure": True,
            "candidate_head_sha": candidate,
            "current_main_sha": current_main,
            "registry_source_main_sha": registry_source,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "exact_candidate_thaw_count": len(exact_candidate_thaws),
            "reconciliation_mismatch_count": len(reconciliation_required),
            "blocked_mismatch_count": len(blocked_mismatches),
            "blocked_mismatches": blocked_mismatches,
            "barrier_token": token,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        }

    if reconciliation_required:
        return {
            "version": VERSION,
            "status": "WAIT",
            "decision": "REGISTRY_RECONCILIATION_REQUIRED",
            "allow_frozen_verification": False,
            "hard_failure": False,
            "candidate_head_sha": candidate,
            "current_main_sha": current_main,
            "registry_source_main_sha": registry_source,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "exact_candidate_thaw_count": len(exact_candidate_thaws),
            "reconciliation_mismatch_count": len(reconciliation_required),
            "blocked_mismatch_count": 0,
            "reconciliation_authorities": reconciliation_required,
            "barrier_token": token,
            "next_legal_action": "WAIT_FOR_AUTHORITATIVE_REGISTRY_RECONCILIATION",
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        }

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "FROZEN_REGISTRY_READY",
        "allow_frozen_verification": True,
        "hard_failure": False,
        "candidate_head_sha": candidate,
        "current_main_sha": current_main,
        "registry_source_main_sha": registry_source,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "exact_candidate_thaw_count": len(exact_candidate_thaws),
        "reconciliation_mismatch_count": 0,
        "blocked_mismatch_count": 0,
        "barrier_token": token,
        "next_legal_action": "RUN_FROZEN_REGISTRY_VERIFICATION",
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def plan_git_head_barrier(
    registry: Mapping[str, Any],
    *,
    candidate_head: str = "HEAD",
    current_main_sha: str,
) -> dict[str, Any]:
    validated = validate_registry(registry)
    candidate_sha = git_head_sha(candidate_head)
    actual = git_blob_map(candidate_head, list(validated["artifacts"]))
    merged = newly_merged_thaw_targets(
        registry,
        main_sha=_sha(current_main_sha, "current_main_sha"),
    )
    return evaluate_barrier(
        registry,
        actual,
        candidate_head_sha=candidate_sha,
        current_main_sha=current_main_sha,
        newly_merged_targets=merged,
    )


def _sample_registry() -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "owner/repo",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 10,
        "source_main_sha": "1" * 40,
        "entries": {
            "STEP_A": {
                "status": "FROZEN",
                "checkpoint_id": "STEP_A",
                "source_main_sha": "1" * 40,
                "artifacts": {
                    "shared.py": "a" * 40,
                    "keep.py": "c" * 40,
                },
            }
        },
        "active_thaws": [
            {
                "thaw_id": "THAW-SHARED",
                "status": "ACTIVE",
                "target_head_sha": "2" * 40,
                "files": {
                    "shared.py": {
                        "from_blob": "a" * 40,
                        "to_blob": "b" * 40,
                    }
                },
            }
        ],
    }
    payload["state_hash"] = _hash(_payload_without_hash(payload))
    return payload


def self_test() -> dict[str, Any]:
    sample = _sample_registry()

    aligned = evaluate_barrier(
        sample,
        {"shared.py": "a" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="4" * 40,
        newly_merged_targets=[],
    )
    if aligned["decision"] != "FROZEN_REGISTRY_READY":
        raise RegistryReconciliationBarrierFailure("aligned registry was blocked")

    unrelated_main_advance = evaluate_barrier(
        sample,
        {"shared.py": "a" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="5" * 40,
        newly_merged_targets=[],
    )
    if unrelated_main_advance["allow_frozen_verification"] is not True:
        raise RegistryReconciliationBarrierFailure(
            "unrelated main advance incorrectly required reconciliation"
        )

    exact_candidate = evaluate_barrier(
        sample,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="2" * 40,
        current_main_sha="1" * 40,
        newly_merged_targets=[],
    )
    if exact_candidate["decision"] != "FROZEN_REGISTRY_READY":
        raise RegistryReconciliationBarrierFailure(
            "exact candidate thaw was not allowed through barrier"
        )

    inherited_merged = evaluate_barrier(
        sample,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="4" * 40,
        newly_merged_targets=["2" * 40],
    )
    if inherited_merged["decision"] != "REGISTRY_RECONCILIATION_REQUIRED":
        raise RegistryReconciliationBarrierFailure(
            "newly merged inherited thaw did not enter reconciliation barrier"
        )
    if inherited_merged["hard_failure"] is not False:
        raise RegistryReconciliationBarrierFailure(
            "reconciliation barrier incorrectly classified WAIT as hard failure"
        )

    unauthorized = evaluate_barrier(
        sample,
        {"shared.py": "d" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="4" * 40,
        newly_merged_targets=[],
    )
    if unauthorized["decision"] != "UNAUTHORIZED_FROZEN_DRIFT":
        raise RegistryReconciliationBarrierFailure(
            "unauthorized drift was not blocked"
        )

    return {
        "status": "GREEN",
        "version": VERSION,
        "aligned_registry_ready": aligned["allow_frozen_verification"] is True,
        "unrelated_main_advance_does_not_block": (
            unrelated_main_advance["allow_frozen_verification"] is True
        ),
        "exact_candidate_thaw_allowed": (
            exact_candidate["allow_frozen_verification"] is True
        ),
        "newly_merged_inherited_thaw_waits_for_reconciliation": (
            inherited_merged["status"] == "WAIT"
        ),
        "wait_is_not_hard_failure": inherited_merged["hard_failure"] is False,
        "unauthorized_drift_blocks": unauthorized["hard_failure"] is True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--registry-file", required=True)
    evaluate.add_argument("--candidate-head", default="HEAD")
    evaluate.add_argument("--current-main-sha", required=True)
    evaluate.add_argument("--json-out")

    args = parser.parse_args(argv)
    if args.command in {None, "self-test"}:
        result = self_test()
        print("MONSTER_REGISTRY_RACE_V1_STEP1_RECONCILIATION_BARRIER_GREEN")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    result = plan_git_head_barrier(
        _load(args.registry_file),
        candidate_head=args.candidate_head,
        current_main_sha=args.current_main_sha,
    )
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "GREEN":
        return 0
    if result["status"] == "WAIT":
        return 3
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RegistryReconciliationBarrierFailure as exc:
        print(
            "MONSTER_REGISTRY_RACE_V1_STEP1_BLOCKED: " + str(exc),
            file=sys.stderr,
        )
        raise SystemExit(1)
