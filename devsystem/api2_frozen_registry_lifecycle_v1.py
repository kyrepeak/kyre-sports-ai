"""API2 Proof Architecture V1 Step 6 — independent frozen registry lifecycle.

This layer audits and plans lifecycle transitions only for the API 2 frozen
artifact registry. It never reads, imports, fetches, or mutates another
system's registry authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import re
import sys
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.api2_frozen_artifact_registry_v1 import (
    FrozenArtifactRegistryFailure,
    REGISTRY_PATH,
    REGISTRY_REF,
    VERSION as REGISTRY_VERSION,
    _hash,
    _payload_without_hash,
    validate_registry,
)

VERSION = "API2_PROOF_ARCHITECTURE_V1_STEP6_FROZEN_REGISTRY_LIFECYCLE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class RegistryLifecycleFailure(RuntimeError):
    pass


def _baseline_map(registry: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for checkpoint, entry in (registry.get("entries") or {}).items():
        artifacts = entry.get("artifacts") if isinstance(entry, Mapping) else None
        if not isinstance(artifacts, Mapping):
            raise RegistryLifecycleFailure(f"{checkpoint}: artifacts unavailable")
        for path, blob in artifacts.items():
            path_text = str(path)
            blob_text = str(blob).lower()
            previous = result.get(path_text)
            if previous is not None and previous != blob_text:
                raise RegistryLifecycleFailure(f"conflicting frozen baseline for {path_text}")
            result[path_text] = blob_text
    return result


def audit_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validated = validate_registry(payload)
    except FrozenArtifactRegistryFailure as exc:
        raise RegistryLifecycleFailure(
            "AUTHORITATIVE_REGISTRY_LIFECYCLE_BLOCKED: " + str(exc)
        ) from exc

    baselines = _baseline_map(payload)
    pair_count = 0
    target_heads: set[str] = set()
    for grant in payload["active_thaws"]:
        target_heads.add(str(grant["target_head_sha"]))
        pair_count += len(grant["files"])

    return {
        "version": VERSION,
        "registry_version": REGISTRY_VERSION,
        "registry_ref": REGISTRY_REF,
        "registry_path": REGISTRY_PATH,
        "status": "GREEN",
        "decision": "REGISTRY_LIFECYCLE_CLEAN",
        "revision": int(payload["revision"]),
        "source_main_sha": str(payload["source_main_sha"]),
        "entry_count": int(validated["entry_count"]),
        "artifact_count": int(validated["artifact_count"]),
        "active_thaw_count": len(payload["active_thaws"]),
        "active_thaw_file_pair_count": pair_count,
        "active_target_head_count": len(target_heads),
        "baseline_count": len(baselines),
        "state_hash": str(validated["state_hash"]),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def plan_baseline_forward_port(
    payload: Mapping[str, Any],
    *,
    updates: Mapping[str, Mapping[str, str]],
    source_main_sha: str,
) -> dict[str, Any]:
    """Return one atomic, hash-valid API 2 registry state for a baseline move."""
    audit_registry(payload)
    if not _SHA40.fullmatch(str(source_main_sha or "").lower()):
        raise RegistryLifecycleFailure("source_main_sha must be full SHA")
    if not isinstance(updates, Mapping) or not updates:
        raise RegistryLifecycleFailure("at least one baseline update is required")

    before = deepcopy(dict(payload))
    baselines = _baseline_map(before)
    normalized: dict[str, tuple[str, str]] = {}
    for raw_path, raw_pair in updates.items():
        path = str(raw_path or "").strip()
        if not path or not isinstance(raw_pair, Mapping):
            raise RegistryLifecycleFailure("invalid baseline update")
        old = str(raw_pair.get("from_blob") or "").lower()
        new = str(raw_pair.get("to_blob") or "").lower()
        if path not in baselines:
            raise RegistryLifecycleFailure(f"update path is not frozen: {path}")
        if old != baselines[path]:
            raise RegistryLifecycleFailure(
                f"update from_blob differs from frozen baseline: {path}"
            )
        if not _SHA40.fullmatch(new) or new == old:
            raise RegistryLifecycleFailure(f"update to_blob invalid: {path}")
        normalized[path] = (old, new)

    result = deepcopy(before)
    updated_entries: list[dict[str, str]] = []
    for checkpoint, entry in result["entries"].items():
        for path, (old, new) in normalized.items():
            if entry["artifacts"].get(path) == old:
                entry["artifacts"][path] = new
                updated_entries.append(
                    {
                        "checkpoint": str(checkpoint),
                        "path": path,
                        "from_blob": old,
                        "to_blob": new,
                    }
                )

    retired_pairs: list[dict[str, str]] = []
    retained_grants: list[dict[str, Any]] = []
    retired_grants: list[str] = []
    for grant in result["active_thaws"]:
        kept_files: dict[str, Any] = {}
        for path, pair in grant["files"].items():
            if path in normalized:
                _, new = normalized[path]
                retired_pairs.append(
                    {
                        "thaw_id": str(grant["thaw_id"]),
                        "target_head_sha": str(grant["target_head_sha"]),
                        "path": str(path),
                        "from_blob": str(pair["from_blob"]),
                        "to_blob": str(pair["to_blob"]),
                        "new_frozen_baseline": new,
                    }
                )
                continue
            kept_files[str(path)] = deepcopy(pair)
        if kept_files:
            kept = deepcopy(grant)
            kept["files"] = kept_files
            retained_grants.append(kept)
        else:
            retired_grants.append(str(grant["thaw_id"]))

    result["active_thaws"] = retained_grants
    result["revision"] = int(before["revision"]) + 1
    result["source_main_sha"] = str(source_main_sha).lower()
    result["state_hash"] = _hash(_payload_without_hash(result))

    try:
        validated = validate_registry(result)
    except FrozenArtifactRegistryFailure as exc:
        raise RegistryLifecycleFailure(
            "planned forward-port is not registry-valid: " + str(exc)
        ) from exc

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "FROZEN_BASELINE_FORWARD_PORT_PLANNED",
        "previous_revision": int(before["revision"]),
        "next_revision": int(result["revision"]),
        "source_main_sha": str(result["source_main_sha"]),
        "updated_entries": updated_entries,
        "retired_thaw_file_pairs": retired_pairs,
        "retired_empty_thaw_grants": retired_grants,
        "retained_thaw_count": len(retained_grants),
        "state_hash": str(validated["state_hash"]),
        "registry": result,
        "input_mutated": payload != before,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def registry_progress(previous_state_hash: str | None, current_state_hash: str) -> dict[str, Any]:
    current = str(current_state_hash or "").lower()
    previous = str(previous_state_hash or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", current):
        raise RegistryLifecycleFailure("current state hash invalid")
    if previous and not re.fullmatch(r"[0-9a-f]{64}", previous):
        raise RegistryLifecycleFailure("previous state hash invalid")
    changed = not previous or previous != current
    return {
        "status": "GREEN",
        "decision": "REGISTRY_STATE_ADVANCED" if changed else "REGISTRY_STATE_UNCHANGED",
        "refetch_retry_allowed": bool(changed),
        "previous_state_hash": previous or None,
        "current_state_hash": current,
    }


def _sample_registry() -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "version": REGISTRY_VERSION,
        "repository": "owner/repo",
        "registry_ref": REGISTRY_REF,
        "registry_path": REGISTRY_PATH,
        "revision": 7,
        "source_main_sha": "1" * 40,
        "entries": {
            "STEP_A": {
                "status": "FROZEN",
                "checkpoint_id": "STEP_A",
                "source_main_sha": "1" * 40,
                "artifacts": {"shared.yml": "a" * 40, "keep.py": "c" * 40},
            },
            "STEP_B": {
                "status": "FROZEN",
                "checkpoint_id": "STEP_B",
                "source_main_sha": "1" * 40,
                "artifacts": {"shared.yml": "a" * 40},
            },
        },
        "active_thaws": [
            {
                "thaw_id": "API2-THAW-SHARED-OLD",
                "status": "ACTIVE",
                "target_head_sha": "2" * 40,
                "files": {"shared.yml": {"from_blob": "a" * 40, "to_blob": "b" * 40}},
            },
            {
                "thaw_id": "API2-THAW-KEEP",
                "status": "ACTIVE",
                "target_head_sha": "3" * 40,
                "files": {"keep.py": {"from_blob": "c" * 40, "to_blob": "d" * 40}},
            },
        ],
    }
    payload["state_hash"] = _hash(_payload_without_hash(payload))
    return payload


def contract_self_test() -> dict[str, Any]:
    sample = _sample_registry()
    audit = audit_registry(sample)
    original = deepcopy(sample)
    plan = plan_baseline_forward_port(
        sample,
        updates={"shared.yml": {"from_blob": "a" * 40, "to_blob": "b" * 40}},
        source_main_sha="4" * 40,
    )
    if sample != original:
        raise RegistryLifecycleFailure("planner mutated input registry")
    if len(plan["updated_entries"]) != 2:
        raise RegistryLifecycleFailure("shared baseline did not advance atomically")
    if len(plan["retired_thaw_file_pairs"]) != 1:
        raise RegistryLifecycleFailure("obsolete thaw pair was not retired")
    if plan["retired_empty_thaw_grants"] != ["API2-THAW-SHARED-OLD"]:
        raise RegistryLifecycleFailure("empty obsolete thaw grant was not retired")
    if plan["retained_thaw_count"] != 1:
        raise RegistryLifecycleFailure("unrelated thaw grant was not preserved")
    validate_registry(plan["registry"])

    wrong_from_blocked = False
    try:
        plan_baseline_forward_port(
            sample,
            updates={"shared.yml": {"from_blob": "c" * 40, "to_blob": "b" * 40}},
            source_main_sha="4" * 40,
        )
    except RegistryLifecycleFailure:
        wrong_from_blocked = True
    if not wrong_from_blocked:
        raise RegistryLifecycleFailure("wrong baseline forward-port was not blocked")

    h1 = hashlib.sha256(b"one").hexdigest()
    h2 = hashlib.sha256(b"two").hexdigest()
    advanced = registry_progress(h1, h2)
    unchanged = registry_progress(h2, h2)
    if advanced["refetch_retry_allowed"] is not True:
        raise RegistryLifecycleFailure("advanced registry state did not allow bounded retry")
    if unchanged["refetch_retry_allowed"] is not False:
        raise RegistryLifecycleFailure("unchanged registry state allowed loop retry")

    return {
        "status": "GREEN",
        "version": VERSION,
        "clean_registry_audit": audit["status"] == "GREEN",
        "atomic_multi_checkpoint_forward_port": len(plan["updated_entries"]) == 2,
        "obsolete_thaw_pair_retired": len(plan["retired_thaw_file_pairs"]) == 1,
        "empty_obsolete_grant_retired": plan["retired_empty_thaw_grants"]
        == ["API2-THAW-SHARED-OLD"],
        "unrelated_thaw_preserved": plan["retained_thaw_count"] == 1,
        "wrong_from_blob_blocked": wrong_from_blocked,
        "state_progress_required_for_retry": unchanged["refetch_retry_allowed"] is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")
    audit = sub.add_parser("audit")
    audit.add_argument("--registry-file", required=True)
    audit.add_argument("--json-out")
    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        result = contract_self_test()
        print("API2_PROOF_ARCHITECTURE_V1_STEP6_REGISTRY_LIFECYCLE_GREEN")
    elif args.command == "audit":
        result = audit_registry(_load(args.registry_file))
        print("API2_STEP6_AUTHORITATIVE_REGISTRY_LIFECYCLE_GREEN")
    else:
        raise RegistryLifecycleFailure("unsupported command")

    if getattr(args, "json_out", None):
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RegistryLifecycleFailure as exc:
        print(
            f"API2_PROOF_ARCHITECTURE_V1_STEP6_REGISTRY_LIFECYCLE_BLOCKED: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
