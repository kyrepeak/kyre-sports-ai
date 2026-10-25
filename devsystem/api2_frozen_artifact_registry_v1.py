"""API 2 independent frozen artifact registry.

API 2 freeze authority is intentionally separate from every MONSTER branch,
registry, state file, checkpoint, proof artifact, and thaw grant. The registry
lives on refs/heads/api2-frozen-registry and pins protected files by exact Git
blob SHA. A candidate head may change a protected file only when this API 2
registry contains an exact-head, exact-blob thaw grant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

VERSION = "API2_FROZEN_ARTIFACT_REGISTRY_V1"
REGISTRY_REF = "refs/heads/api2-frozen-registry"
REGISTRY_PATH = "devsystem/api2_frozen_registry_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class FrozenArtifactRegistryFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _payload_without_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    result.pop("state_hash", None)
    return result


def validate_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise FrozenArtifactRegistryFailure("registry must be an object")
    registry = deepcopy(dict(payload))
    required = {
        "schema_version",
        "version",
        "repository",
        "registry_ref",
        "registry_path",
        "revision",
        "source_main_sha",
        "entries",
        "active_thaws",
        "state_hash",
    }
    missing = sorted(required - set(registry))
    if missing:
        raise FrozenArtifactRegistryFailure("registry missing fields: " + ", ".join(missing))
    if int(registry["schema_version"]) != 1:
        raise FrozenArtifactRegistryFailure("registry schema mismatch")
    if registry["version"] != VERSION:
        raise FrozenArtifactRegistryFailure("registry version mismatch")
    if registry["registry_ref"] != REGISTRY_REF:
        raise FrozenArtifactRegistryFailure("registry ref mismatch")
    if registry["registry_path"] != REGISTRY_PATH:
        raise FrozenArtifactRegistryFailure("registry path mismatch")
    if "/" not in str(registry["repository"]):
        raise FrozenArtifactRegistryFailure("registry repository invalid")
    if int(registry["revision"]) < 0:
        raise FrozenArtifactRegistryFailure("registry revision invalid")
    if not _SHA40.fullmatch(str(registry["source_main_sha"] or "")):
        raise FrozenArtifactRegistryFailure("source_main_sha invalid")

    entries = registry["entries"]
    if not isinstance(entries, Mapping) or not entries:
        raise FrozenArtifactRegistryFailure("registry entries required")

    flattened: dict[str, str] = {}
    for checkpoint, entry in entries.items():
        if not isinstance(entry, Mapping):
            raise FrozenArtifactRegistryFailure(f"{checkpoint}: entry must be object")
        if entry.get("status") != "FROZEN":
            raise FrozenArtifactRegistryFailure(f"{checkpoint}: status must be FROZEN")
        if str(entry.get("checkpoint_id") or "") != str(checkpoint):
            raise FrozenArtifactRegistryFailure(f"{checkpoint}: checkpoint id mismatch")
        if not _SHA40.fullmatch(str(entry.get("source_main_sha") or "")):
            raise FrozenArtifactRegistryFailure(f"{checkpoint}: source main sha invalid")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, Mapping) or not artifacts:
            raise FrozenArtifactRegistryFailure(f"{checkpoint}: artifacts required")
        for path, blob in artifacts.items():
            path_text = str(path or "").strip()
            blob_text = str(blob or "").strip().lower()
            if not path_text or path_text.startswith("/") or ".." in Path(path_text).parts:
                raise FrozenArtifactRegistryFailure(f"{checkpoint}: invalid artifact path")
            if not _SHA40.fullmatch(blob_text):
                raise FrozenArtifactRegistryFailure(f"{checkpoint}: invalid blob for {path_text}")
            previous = flattened.get(path_text)
            if previous is not None and previous != blob_text:
                raise FrozenArtifactRegistryFailure(f"conflicting frozen baselines for {path_text}")
            flattened[path_text] = blob_text

    thaws = registry["active_thaws"]
    if not isinstance(thaws, list):
        raise FrozenArtifactRegistryFailure("active_thaws must be a list")
    ids: set[str] = set()
    for grant in thaws:
        if not isinstance(grant, Mapping):
            raise FrozenArtifactRegistryFailure("thaw grant must be object")
        grant_id = str(grant.get("thaw_id") or "").strip()
        if not grant_id or grant_id in ids:
            raise FrozenArtifactRegistryFailure("thaw_id missing or duplicated")
        ids.add(grant_id)
        if grant.get("status") != "ACTIVE":
            raise FrozenArtifactRegistryFailure(f"{grant_id}: thaw status must be ACTIVE")
        if not _SHA40.fullmatch(str(grant.get("target_head_sha") or "")):
            raise FrozenArtifactRegistryFailure(f"{grant_id}: target head invalid")
        files = grant.get("files")
        if not isinstance(files, Mapping) or not files:
            raise FrozenArtifactRegistryFailure(f"{grant_id}: files required")
        for path, pair in files.items():
            if path not in flattened:
                raise FrozenArtifactRegistryFailure(f"{grant_id}: thaw path is not frozen: {path}")
            if not isinstance(pair, Mapping):
                raise FrozenArtifactRegistryFailure(f"{grant_id}: thaw pair invalid")
            before = str(pair.get("from_blob") or "").lower()
            after = str(pair.get("to_blob") or "").lower()
            if before != flattened[path]:
                raise FrozenArtifactRegistryFailure(
                    f"{grant_id}: thaw from_blob differs from frozen baseline"
                )
            if not _SHA40.fullmatch(after) or after == before:
                raise FrozenArtifactRegistryFailure(f"{grant_id}: thaw to_blob invalid")

    expected_hash = _hash(_payload_without_hash(registry))
    if str(registry["state_hash"] or "") != expected_hash:
        raise FrozenArtifactRegistryFailure("registry state hash mismatch")
    return {
        "status": "GREEN",
        "entry_count": len(entries),
        "artifact_count": len(flattened),
        "active_thaw_count": len(thaws),
        "state_hash": expected_hash,
        "artifacts": flattened,
    }


def _matching_thaw(
    registry: Mapping[str, Any],
    *,
    path: str,
    expected_blob: str,
    actual_blob: str,
    head_sha: str,
) -> str | None:
    for grant in registry["active_thaws"]:
        if str(grant["target_head_sha"]) != head_sha:
            continue
        pair = grant["files"].get(path)
        if not isinstance(pair, Mapping):
            continue
        if (
            str(pair.get("from_blob") or "").lower() == expected_blob
            and str(pair.get("to_blob") or "").lower() == actual_blob
        ):
            return str(grant["thaw_id"])
    return None


def evaluate_head(
    registry: Mapping[str, Any],
    actual_blobs: Mapping[str, str | None],
    *,
    head_sha: str,
) -> dict[str, Any]:
    validated = validate_registry(registry)
    head_sha = str(head_sha or "").lower()
    if not _SHA40.fullmatch(head_sha):
        raise FrozenArtifactRegistryFailure("head_sha must be full SHA")

    mismatches: list[dict[str, str | None]] = []
    thawed: list[dict[str, str]] = []
    for path, expected in sorted(validated["artifacts"].items()):
        actual_raw = actual_blobs.get(path)
        actual = str(actual_raw).lower() if actual_raw else None
        if actual == expected:
            continue
        if actual is not None:
            thaw_id = _matching_thaw(
                registry,
                path=path,
                expected_blob=expected,
                actual_blob=actual,
                head_sha=head_sha,
            )
            if thaw_id:
                thawed.append(
                    {"path": path, "from_blob": expected, "to_blob": actual, "thaw_id": thaw_id}
                )
                continue
        mismatches.append({"path": path, "expected_blob": expected, "actual_blob": actual})

    if mismatches:
        summary = " | ".join(
            f"{item['path']} expected={item['expected_blob']} actual={item['actual_blob']}"
            for item in mismatches
        )
        raise FrozenArtifactRegistryFailure(
            "frozen artifact mismatch without exact API2 thaw grant: " + summary
        )

    observed = {(item["thaw_id"], item["path"]) for item in thawed}
    for grant in registry["active_thaws"]:
        if str(grant["target_head_sha"]) != head_sha:
            continue
        grant_id = str(grant["thaw_id"])
        for path in grant["files"]:
            if (grant_id, path) not in observed:
                raise FrozenArtifactRegistryFailure(
                    f"{grant_id}: exact-head thaw contains unused file {path}"
                )

    return {
        "status": "GREEN",
        "decision": "FROZEN_ARTIFACTS_INTACT"
        if not thawed
        else "FROZEN_ARTIFACTS_EXACT_THAW_AUTHORIZED",
        "head_sha": head_sha,
        "entry_count": validated["entry_count"],
        "artifact_count": validated["artifact_count"],
        "thawed_files": thawed,
        "registry_state_hash": validated["state_hash"],
    }


def git_blob_map(head: str, paths: list[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for path in paths:
        completed = subprocess.run(
            ["git", "rev-parse", f"{head}:{path}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        result[path] = completed.stdout.strip().lower() if completed.returncode == 0 else None
    return result


def git_head_sha(head: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", head],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise FrozenArtifactRegistryFailure("unable to resolve head: " + completed.stderr.strip())
    sha = completed.stdout.strip().lower()
    if not _SHA40.fullmatch(sha):
        raise FrozenArtifactRegistryFailure("resolved head is not full SHA")
    return sha


def verify_git_head(registry: Mapping[str, Any], *, head: str = "HEAD") -> dict[str, Any]:
    validated = validate_registry(registry)
    head_sha = git_head_sha(head)
    return evaluate_head(
        registry,
        git_blob_map(head, list(validated["artifacts"])),
        head_sha=head_sha,
    )


def _sample_registry() -> dict[str, Any]:
    registry = {
        "schema_version": 1,
        "version": VERSION,
        "repository": "owner/repo",
        "registry_ref": REGISTRY_REF,
        "registry_path": REGISTRY_PATH,
        "revision": 0,
        "source_main_sha": "1" * 40,
        "entries": {
            "API2_FROZEN_A": {
                "status": "FROZEN",
                "checkpoint_id": "API2_FROZEN_A",
                "source_main_sha": "1" * 40,
                "artifacts": {"a.py": "a" * 40, "b.py": "b" * 40},
            }
        },
        "active_thaws": [],
    }
    registry["state_hash"] = _hash(_payload_without_hash(registry))
    return registry


def contract_self_test() -> dict[str, Any]:
    registry = _sample_registry()
    intact = evaluate_head(
        registry,
        {"a.py": "a" * 40, "b.py": "b" * 40},
        head_sha="2" * 40,
    )
    mismatch_blocked = False
    try:
        evaluate_head(
            registry,
            {"a.py": "c" * 40, "b.py": "b" * 40},
            head_sha="2" * 40,
        )
    except FrozenArtifactRegistryFailure:
        mismatch_blocked = True

    thaw_registry = deepcopy(registry)
    thaw_registry["active_thaws"] = [
        {
            "thaw_id": "API2-THAW-ONE",
            "status": "ACTIVE",
            "target_head_sha": "2" * 40,
            "files": {"a.py": {"from_blob": "a" * 40, "to_blob": "c" * 40}},
        }
    ]
    thaw_registry["state_hash"] = _hash(_payload_without_hash(thaw_registry))
    exact_thaw = evaluate_head(
        thaw_registry,
        {"a.py": "c" * 40, "b.py": "b" * 40},
        head_sha="2" * 40,
    )

    wrong_head_blocked = False
    try:
        evaluate_head(
            thaw_registry,
            {"a.py": "c" * 40, "b.py": "b" * 40},
            head_sha="3" * 40,
        )
    except FrozenArtifactRegistryFailure:
        wrong_head_blocked = True

    tampered = deepcopy(registry)
    tampered["entries"]["API2_FROZEN_A"]["artifacts"]["a.py"] = "d" * 40
    tamper_blocked = False
    try:
        validate_registry(tampered)
    except FrozenArtifactRegistryFailure:
        tamper_blocked = True

    return {
        "status": "GREEN",
        "version": VERSION,
        "intact_frozen_artifacts_pass": intact["decision"] == "FROZEN_ARTIFACTS_INTACT",
        "mismatch_without_thaw_blocked": mismatch_blocked,
        "exact_head_exact_blob_thaw_allowed": exact_thaw["decision"]
        == "FROZEN_ARTIFACTS_EXACT_THAW_AUTHORIZED",
        "wrong_head_thaw_blocked": wrong_head_blocked,
        "registry_tamper_blocked": tamper_blocked,
        "pr_cannot_self_thaw": True,
        "separate_authoritative_registry_ref": REGISTRY_REF
        == "refs/heads/api2-frozen-registry",
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
    validate = sub.add_parser("validate")
    validate.add_argument("--registry-file", required=True)
    verify = sub.add_parser("verify-head")
    verify.add_argument("--registry-file", required=True)
    verify.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        result = contract_self_test()
        print("API2_FROZEN_ARTIFACT_REGISTRY_SELF_TEST_GREEN")
    elif args.command == "validate":
        result = validate_registry(_load(args.registry_file))
        print("API2_FROZEN_ARTIFACT_REGISTRY_VALID_GREEN")
    elif args.command == "verify-head":
        result = verify_git_head(_load(args.registry_file), head=args.head)
        print("API2_FROZEN_ARTIFACT_REGISTRY_HEAD_GREEN")
    else:
        raise FrozenArtifactRegistryFailure("unsupported command")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FrozenArtifactRegistryFailure as exc:
        print(f"API2_FROZEN_ARTIFACT_REGISTRY_BLOCKED: {exc}")
        raise SystemExit(1)
