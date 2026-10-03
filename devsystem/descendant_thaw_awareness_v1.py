"""Registry Race Repair V1 Step 2 — Descendant Thaw Awareness.

Read-only lineage certifier layered above the frozen Step-1 reconciliation barrier.

It proves that a frozen-file change seen on a later workstream is inherited from
an authorized thaw already merged into authoritative main, rather than authored
by the later workstream itself.

Required lineage:
    thaw target -> authoritative main -> candidate head

The blob pair must also match exactly:
    frozen baseline -> authorized thaw to_blob -> candidate actual blob

No network calls. No Git writes. No registry writes. No mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
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
from devsystem.registry_reconciliation_barrier_v1 import (
    VERSION as STEP1_VERSION,
    EXPECTED_AUTO_RECONCILER_VERSION,
    evaluate_barrier,
)

VERSION = "MONSTER_REGISTRY_RACE_V1_STEP2_DESCENDANT_THAW_AWARENESS_V1"
EXPECTED_STEP1_VERSION = "MONSTER_REGISTRY_RACE_V1_STEP1_RECONCILIATION_BARRIER_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class DescendantThawAwarenessFailure(RuntimeError):
    pass


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise DescendantThawAwarenessFailure(f"{label} must be a full SHA")
    return text


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any) -> str:
    return "LINEAGE-" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:32].upper()


def _parents_green() -> None:
    if STEP1_VERSION != EXPECTED_STEP1_VERSION:
        raise DescendantThawAwarenessFailure("frozen Step-1 barrier version drift")


def _matching_pairs(
    registry: Mapping[str, Any],
    *,
    path: str,
    expected_blob: str,
    actual_blob: str,
) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for grant in registry["active_thaws"]:
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
                    "target_head_sha": str(grant["target_head_sha"]).lower(),
                    "path": path,
                    "from_blob": expected_blob,
                    "to_blob": actual_blob,
                }
            )
    return matches


def evaluate_descendant_authority(
    registry: Mapping[str, Any],
    actual_blobs: Mapping[str, str | None],
    *,
    candidate_head_sha: str,
    current_main_sha: str,
    main_descends_from_targets: Mapping[str, bool],
    candidate_descends_from_main: bool,
) -> dict[str, Any]:
    """Certify inherited thaw authority from explicit ancestry facts."""
    _parents_green()
    validated = validate_registry(registry)
    candidate = _sha(candidate_head_sha, "candidate_head_sha")
    current_main = _sha(current_main_sha, "current_main_sha")
    registry_source = _sha(registry["source_main_sha"], "registry source_main_sha")

    active_targets = {
        str(grant["target_head_sha"]).lower() for grant in registry["active_thaws"]
    }
    ancestry_keys = {str(key).lower() for key in main_descends_from_targets}
    unknown = sorted(ancestry_keys - active_targets)
    if unknown:
        raise DescendantThawAwarenessFailure(
            "ancestry facts supplied for non-active thaw target: " + ", ".join(unknown)
        )

    inherited: list[dict[str, Any]] = []
    exact_candidate: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for path, expected in sorted(validated["artifacts"].items()):
        raw_actual = actual_blobs.get(path)
        actual = str(raw_actual).lower() if raw_actual else None
        if actual == expected:
            continue
        if actual is None:
            blocked.append(
                {
                    "path": path,
                    "expected_blob": expected,
                    "actual_blob": None,
                    "reason": "FROZEN_ARTIFACT_DELETED",
                }
            )
            continue

        matches = _matching_pairs(
            registry,
            path=path,
            expected_blob=expected,
            actual_blob=actual,
        )
        if len(matches) != 1:
            blocked.append(
                {
                    "path": path,
                    "expected_blob": expected,
                    "actual_blob": actual,
                    "reason": (
                        "NO_UNIQUE_THAW_BLOB_AUTHORITY"
                        if not matches
                        else "AMBIGUOUS_THAW_BLOB_AUTHORITY"
                    ),
                    "matching_authorities": len(matches),
                }
            )
            continue

        authority = matches[0]
        target = authority["target_head_sha"]

        if target == candidate:
            exact_candidate.append(
                {
                    **authority,
                    "authority_type": "EXACT_CANDIDATE_THAW",
                    "target_ancestor_of_main": bool(
                        main_descends_from_targets.get(target, False)
                    ),
                    "main_ancestor_of_candidate": bool(candidate_descends_from_main),
                }
            )
            continue

        if not bool(main_descends_from_targets.get(target, False)):
            blocked.append(
                {
                    **authority,
                    "reason": "THAW_TARGET_NOT_MERGED_INTO_AUTHORITATIVE_MAIN",
                }
            )
            continue

        if not candidate_descends_from_main:
            blocked.append(
                {
                    **authority,
                    "reason": "CANDIDATE_NOT_DESCENDED_FROM_AUTHORITATIVE_MAIN",
                }
            )
            continue

        inherited.append(
            {
                **authority,
                "authority_type": "AUTHORIZED_INHERITED_THAW",
                "target_ancestor_of_main": True,
                "main_ancestor_of_candidate": True,
            }
        )

    basis = {
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "registry_source_main_sha": registry_source,
        "current_main_sha": current_main,
        "candidate_head_sha": candidate,
        "candidate_descends_from_main": bool(candidate_descends_from_main),
        "inherited": inherited,
        "exact_candidate": exact_candidate,
        "blocked": blocked,
    }
    lineage_token = _fingerprint(basis)

    if blocked:
        return {
            "version": VERSION,
            "status": "BLOCKED",
            "decision": "DESCENDANT_AUTHORITY_REJECTED",
            "hard_failure": True,
            "candidate_head_sha": candidate,
            "current_main_sha": current_main,
            "registry_source_main_sha": registry_source,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "candidate_descends_from_main": bool(candidate_descends_from_main),
            "inherited_authority_count": len(inherited),
            "exact_candidate_authority_count": len(exact_candidate),
            "blocked_count": len(blocked),
            "blocked": blocked,
            "lineage_token": lineage_token,
            "registry_reconciliation_required": False,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        }

    if inherited:
        merged_targets = sorted(
            {item["target_head_sha"] for item in inherited}
        )
        barrier = evaluate_barrier(
            registry,
            actual_blobs,
            candidate_head_sha=candidate,
            current_main_sha=current_main,
            newly_merged_targets=merged_targets,
        )
        if barrier["decision"] != "REGISTRY_RECONCILIATION_REQUIRED":
            raise DescendantThawAwarenessFailure(
                "Step-1 barrier did not classify inherited thaw as reconciliation WAIT"
            )

        return {
            "version": VERSION,
            "status": "GREEN",
            "decision": "AUTHORIZED_INHERITED_THAW",
            "hard_failure": False,
            "candidate_head_sha": candidate,
            "current_main_sha": current_main,
            "registry_source_main_sha": registry_source,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "candidate_descends_from_main": True,
            "inherited_authority_count": len(inherited),
            "exact_candidate_authority_count": len(exact_candidate),
            "blocked_count": 0,
            "authorities": inherited,
            "lineage_token": lineage_token,
            "registry_reconciliation_required": True,
            "next_legal_action": "WAIT_FOR_REGISTRY_FORWARD_PORT_THEN_RESUME_ONCE",
            "step1_barrier_status": barrier["status"],
            "step1_barrier_decision": barrier["decision"],
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        }

    barrier = evaluate_barrier(
        registry,
        actual_blobs,
        candidate_head_sha=candidate,
        current_main_sha=current_main,
        newly_merged_targets=[],
    )
    if barrier["status"] != "GREEN":
        raise DescendantThawAwarenessFailure(
            "non-inherited state did not remain Step-1 GREEN"
        )

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": (
            "EXACT_CANDIDATE_THAW_AUTHORITY"
            if exact_candidate
            else "NO_INHERITED_THAW_REQUIRED"
        ),
        "hard_failure": False,
        "candidate_head_sha": candidate,
        "current_main_sha": current_main,
        "registry_source_main_sha": registry_source,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "candidate_descends_from_main": bool(candidate_descends_from_main),
        "inherited_authority_count": 0,
        "exact_candidate_authority_count": len(exact_candidate),
        "blocked_count": 0,
        "authorities": exact_candidate,
        "lineage_token": lineage_token,
        "registry_reconciliation_required": False,
        "next_legal_action": "CONTINUE_FROZEN_VERIFICATION",
        "step1_barrier_status": barrier["status"],
        "step1_barrier_decision": barrier["decision"],
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def plan_git_head_descendant_authority(
    registry: Mapping[str, Any],
    *,
    candidate_head: str = "HEAD",
    current_main_sha: str,
) -> dict[str, Any]:
    """Evaluate descendant authority using local Git ancestry only."""
    _parents_green()
    validated = validate_registry(registry)
    candidate_sha = git_head_sha(candidate_head)
    current_main = _sha(current_main_sha, "current_main_sha")
    actual = git_blob_map(candidate_head, list(validated["artifacts"]))

    target_facts: dict[str, bool] = {}
    for grant in registry["active_thaws"]:
        target = _sha(grant["target_head_sha"], "thaw target")
        target_facts[target] = _is_ancestor(target, current_main)

    candidate_from_main = _is_ancestor(current_main, candidate_sha)

    return evaluate_descendant_authority(
        registry,
        actual,
        candidate_head_sha=candidate_sha,
        current_main_sha=current_main,
        main_descends_from_targets=target_facts,
        candidate_descends_from_main=candidate_from_main,
    )


def _sample_registry() -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "owner/repo",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 20,
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

    inherited = evaluate_descendant_authority(
        sample,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    if inherited["decision"] != "AUTHORIZED_INHERITED_THAW":
        raise DescendantThawAwarenessFailure(
            "valid inherited thaw was not certified"
        )
    if inherited["registry_reconciliation_required"] is not True:
        raise DescendantThawAwarenessFailure(
            "inherited thaw bypassed registry reconciliation"
        )

    stale_candidate = evaluate_descendant_authority(
        sample,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=False,
    )
    if stale_candidate["status"] != "BLOCKED":
        raise DescendantThawAwarenessFailure(
            "non-descendant candidate inherited authority"
        )

    unmerged_target = evaluate_descendant_authority(
        sample,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: False},
        candidate_descends_from_main=True,
    )
    if unmerged_target["status"] != "BLOCKED":
        raise DescendantThawAwarenessFailure(
            "unmerged thaw target inherited authority"
        )

    exact = evaluate_descendant_authority(
        sample,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="2" * 40,
        current_main_sha="1" * 40,
        main_descends_from_targets={"2" * 40: False},
        candidate_descends_from_main=False,
    )
    if exact["decision"] != "EXACT_CANDIDATE_THAW_AUTHORITY":
        raise DescendantThawAwarenessFailure(
            "exact candidate thaw was not preserved"
        )

    aligned = evaluate_descendant_authority(
        sample,
        {"shared.py": "a" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    if aligned["decision"] != "NO_INHERITED_THAW_REQUIRED":
        raise DescendantThawAwarenessFailure("aligned state drift")

    return {
        "status": "GREEN",
        "version": VERSION,
        "authorized_inherited_thaw_certified": (
            inherited["decision"] == "AUTHORIZED_INHERITED_THAW"
        ),
        "inherited_thaw_still_requires_registry_reconciliation": (
            inherited["registry_reconciliation_required"] is True
        ),
        "candidate_must_descend_from_authoritative_main": (
            stale_candidate["status"] == "BLOCKED"
        ),
        "thaw_target_must_be_merged_into_main": (
            unmerged_target["status"] == "BLOCKED"
        ),
        "exact_candidate_thaw_preserved": (
            exact["decision"] == "EXACT_CANDIDATE_THAW_AUTHORITY"
        ),
        "aligned_state_stays_green": (
            aligned["decision"] == "NO_INHERITED_THAW_REQUIRED"
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def main() -> int:
    result = self_test()
    print("MONSTER_REGISTRY_RACE_V1_STEP2_DESCENDANT_THAW_AWARENESS_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DescendantThawAwarenessFailure as exc:
        print(
            "MONSTER_REGISTRY_RACE_V1_STEP2_BLOCKED: " + str(exc),
            file=sys.stderr,
        )
        raise SystemExit(1)
