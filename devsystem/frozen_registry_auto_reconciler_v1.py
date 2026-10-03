"""API2 Control-Plane Efficiency V1 Step 4 — Frozen Registry Auto-Reconciliation.

Pure/read-only planner layered above the frozen Step-6 lifecycle planner.

It may PLAN a baseline move only when every frozen mismatch is backed by an
exact thaw pair whose target head is proven newly merged into the candidate
main. It never writes Git or the registry itself.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.api2_frozen_registry_lifecycle_v1 import (
    VERSION as LIFECYCLE_VERSION,
    audit_registry,
    plan_baseline_forward_port,
    registry_progress,
)
from devsystem.frozen_artifact_registry_v1 import (
    git_blob_map,
    git_head_sha,
    validate_registry,
)

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP4_FROZEN_REGISTRY_AUTO_RECONCILIATION_V1"
EXPECTED_PARENT_VERSION = "API2_PROOF_ARCHITECTURE_V1_STEP6_FROZEN_REGISTRY_LIFECYCLE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class AutoReconciliationFailure(RuntimeError):
    pass


def _sha(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise AutoReconciliationFailure(f"{label} must be a full SHA")
    return text


def _eligible_targets(
    registry: Mapping[str, Any],
    *,
    merged_authority_heads: Sequence[str],
) -> set[str]:
    supplied = {_sha(value, label="merged authority head") for value in merged_authority_heads}
    known = {str(grant["target_head_sha"]).lower() for grant in registry["active_thaws"]}
    unknown = sorted(supplied - known)
    if unknown:
        raise AutoReconciliationFailure(
            "merged authority head is not an active thaw target: " + ", ".join(unknown)
        )
    return supplied


def plan_auto_reconciliation(
    registry: Mapping[str, Any],
    *,
    actual_blobs: Mapping[str, str | None],
    main_sha: str,
    merged_authority_heads: Sequence[str] = (),
) -> dict[str, Any]:
    if LIFECYCLE_VERSION != EXPECTED_PARENT_VERSION:
        raise AutoReconciliationFailure("frozen Step-6 lifecycle parent version drift")

    audit_registry(registry)
    validated = validate_registry(registry)
    main = _sha(main_sha, label="main_sha")
    eligible = _eligible_targets(
        registry,
        merged_authority_heads=merged_authority_heads,
    )

    mismatches: list[dict[str, Any]] = []
    for path, expected in sorted(validated["artifacts"].items()):
        actual_raw = actual_blobs.get(path)
        actual = str(actual_raw).lower() if actual_raw else None
        if actual == expected:
            continue
        mismatches.append({
            "path": path,
            "expected_blob": expected,
            "actual_blob": actual,
        })

    if not mismatches:
        return {
            "version": VERSION,
            "status": "GREEN",
            "decision": "REGISTRY_ALREADY_ALIGNED",
            "main_sha": main,
            "mismatch_count": 0,
            "authorized_mismatch_count": 0,
            "apply_allowed": False,
            "planned_registry": None,
            "previous_state_hash": str(registry["state_hash"]),
            "next_state_hash": str(registry["state_hash"]),
            "retry_after_apply_allowed": False,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        }

    updates: dict[str, dict[str, str]] = {}
    authorized: list[dict[str, str]] = []
    blocked: list[dict[str, Any]] = []

    for mismatch in mismatches:
        path = mismatch["path"]
        expected = str(mismatch["expected_blob"])
        actual = mismatch["actual_blob"]
        if actual is None:
            blocked.append({**mismatch, "reason": "FROZEN_ARTIFACT_DELETED"})
            continue

        matches: list[dict[str, str]] = []
        for grant in registry["active_thaws"]:
            target = str(grant["target_head_sha"]).lower()
            if target not in eligible:
                continue
            pair = grant["files"].get(path)
            if not isinstance(pair, Mapping):
                continue
            if (
                str(pair.get("from_blob") or "").lower() == expected
                and str(pair.get("to_blob") or "").lower() == actual
            ):
                matches.append({
                    "thaw_id": str(grant["thaw_id"]),
                    "target_head_sha": target,
                    "path": path,
                    "from_blob": expected,
                    "to_blob": actual,
                })

        if len(matches) != 1:
            blocked.append({
                **mismatch,
                "reason": "NO_UNIQUE_NEWLY_MERGED_EXACT_THAW",
                "matching_authorities": len(matches),
            })
            continue

        authority = matches[0]
        authorized.append(authority)
        updates[path] = {
            "from_blob": authority["from_blob"],
            "to_blob": authority["to_blob"],
        }

    if blocked:
        return {
            "version": VERSION,
            "status": "BLOCKED",
            "decision": "UNAUTHORIZED_FROZEN_DRIFT",
            "main_sha": main,
            "mismatch_count": len(mismatches),
            "authorized_mismatch_count": len(authorized),
            "blocked_mismatches": blocked,
            "apply_allowed": False,
            "planned_registry": None,
            "previous_state_hash": str(registry["state_hash"]),
            "next_state_hash": str(registry["state_hash"]),
            "retry_after_apply_allowed": False,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        }

    lifecycle = plan_baseline_forward_port(
        registry,
        updates=updates,
        source_main_sha=main,
    )
    next_hash = str(lifecycle["state_hash"])
    progress = registry_progress(str(registry["state_hash"]), next_hash)
    if progress["refetch_retry_allowed"] is not True:
        raise AutoReconciliationFailure("planned reconciliation did not advance registry state")

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "AUTO_RECONCILIATION_PLANNED",
        "main_sha": main,
        "mismatch_count": len(mismatches),
        "authorized_mismatch_count": len(authorized),
        "authorized_thaws": authorized,
        "apply_allowed": True,
        "previous_revision": int(registry["revision"]),
        "next_revision": int(lifecycle["next_revision"]),
        "previous_state_hash": str(registry["state_hash"]),
        "next_state_hash": next_hash,
        "retry_after_apply_allowed": True,
        "updated_entries": lifecycle["updated_entries"],
        "retired_thaw_file_pairs": lifecycle["retired_thaw_file_pairs"],
        "retired_empty_thaw_grants": lifecycle["retired_empty_thaw_grants"],
        "retained_thaw_count": lifecycle["retained_thaw_count"],
        "planned_registry": lifecycle["registry"],
        "protections": {
            "every_mismatch_requires_exact_thaw": True,
            "every_thaw_target_must_be_newly_merged": True,
            "all_frozen_owners_move_atomically": True,
            "obsolete_thaw_pairs_retired": True,
            "unrelated_thaws_preserved": True,
            "state_hash_must_advance": True,
            "one_retry_after_state_change_only": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def newly_merged_thaw_targets(
    registry: Mapping[str, Any],
    *,
    main_sha: str,
) -> list[str]:
    main = _sha(main_sha, label="main_sha")
    source = _sha(registry["source_main_sha"], label="registry source_main_sha")
    result: list[str] = []
    for grant in registry["active_thaws"]:
        target = _sha(grant["target_head_sha"], label="thaw target")
        merged_now = _is_ancestor(target, main)
        already_in_previous_source = _is_ancestor(target, source)
        if merged_now and not already_in_previous_source:
            result.append(target)
    return sorted(set(result))


def plan_git_head(registry: Mapping[str, Any], *, head: str = "HEAD") -> dict[str, Any]:
    validated = validate_registry(registry)
    main_sha = git_head_sha(head)
    actual = git_blob_map(head, list(validated["artifacts"]))
    eligible = newly_merged_thaw_targets(registry, main_sha=main_sha)
    return plan_auto_reconciliation(
        registry,
        actual_blobs=actual,
        main_sha=main_sha,
        merged_authority_heads=eligible,
    )


def _sample_registry() -> dict[str, Any]:
    from devsystem.api2_frozen_registry_lifecycle_v1 import _sample_registry as parent_sample
    return parent_sample()


def self_test() -> dict[str, Any]:
    sample = _sample_registry()
    actual = {
        "shared.yml": "b" * 40,
        "keep.py": "c" * 40,
    }
    planned = plan_auto_reconciliation(
        sample,
        actual_blobs=actual,
        main_sha="4" * 40,
        merged_authority_heads=["2" * 40],
    )
    if planned["decision"] != "AUTO_RECONCILIATION_PLANNED":
        raise AutoReconciliationFailure("authorized drift was not planned")
    if planned["authorized_mismatch_count"] != 1:
        raise AutoReconciliationFailure("authorized mismatch count drift")
    if len(planned["updated_entries"]) != 2:
        raise AutoReconciliationFailure("all frozen owners did not move atomically")
    if planned["retired_empty_thaw_grants"] != ["THAW-SHARED-OLD"]:
        raise AutoReconciliationFailure("obsolete thaw grant was not retired")
    if planned["retained_thaw_count"] != 1:
        raise AutoReconciliationFailure("unrelated thaw was not preserved")

    aligned = plan_auto_reconciliation(
        planned["planned_registry"],
        actual_blobs=actual,
        main_sha="4" * 40,
        merged_authority_heads=[],
    )
    if aligned["decision"] != "REGISTRY_ALREADY_ALIGNED":
        raise AutoReconciliationFailure("reconciliation is not idempotent")

    unauthorized = plan_auto_reconciliation(
        sample,
        actual_blobs=actual,
        main_sha="4" * 40,
        merged_authority_heads=[],
    )
    if unauthorized["decision"] != "UNAUTHORIZED_FROZEN_DRIFT":
        raise AutoReconciliationFailure("unauthorized drift was not blocked")

    deleted = plan_auto_reconciliation(
        sample,
        actual_blobs={"shared.yml": None, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=[],
    )
    if deleted["decision"] != "UNAUTHORIZED_FROZEN_DRIFT":
        raise AutoReconciliationFailure("frozen deletion was not blocked")

    return {
        "status": "GREEN",
        "version": VERSION,
        "authorized_drift_planned": planned["apply_allowed"] is True,
        "atomic_all_owner_move": len(planned["updated_entries"]) == 2,
        "obsolete_thaw_retired": planned["retired_empty_thaw_grants"] == ["THAW-SHARED-OLD"],
        "unrelated_thaw_preserved": planned["retained_thaw_count"] == 1,
        "state_hash_advanced": planned["previous_state_hash"] != planned["next_state_hash"],
        "one_retry_after_state_change_only": planned["retry_after_apply_allowed"] is True,
        "idempotent_second_pass": aligned["decision"] == "REGISTRY_ALREADY_ALIGNED",
        "unauthorized_drift_blocked": unauthorized["apply_allowed"] is False,
        "frozen_deletion_blocked": deleted["apply_allowed"] is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")
    plan = sub.add_parser("plan-git-head")
    plan.add_argument("--registry-file", required=True)
    plan.add_argument("--head", default="HEAD")
    plan.add_argument("--json-out")
    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        result = self_test()
        print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP4_AUTO_RECONCILIATION_GREEN")
    elif args.command == "plan-git-head":
        result = plan_git_head(_load(args.registry_file), head=args.head)
        print(f"API2_STEP4_{result['decision']}")
    else:
        raise AutoReconciliationFailure("unsupported command")

    if getattr(args, "json_out", None):
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "GREEN" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoReconciliationFailure as exc:
        print(f"API2_CONTROL_PLANE_EFFICIENCY_V1_STEP4_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
