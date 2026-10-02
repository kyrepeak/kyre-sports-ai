"""API2 Proof Architecture V1 Step 3 — Dependency Chain Auto Refresh.

Child workflows register parent paths, not parent blob constants. On every
proof run this engine resolves the current base/head parent blobs, reports
whether the parent changed, and verifies that the child workflow is wired to
wake and run compatibility proof whenever a registered parent changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

VERSION = "API2_DEPENDENCY_CHAIN_AUTO_REFRESH_V1"
REGISTRY_VERSION = "API2_DEPENDENCY_CHAIN_REGISTRY_V1"
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "devsystem/dependency_chain_registry_v1.json"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class DependencyChainFailure(RuntimeError):
    pass


def _load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != REGISTRY_VERSION:
        raise DependencyChainFailure("dependency registry version drift")
    deps = payload.get("dependencies")
    if not isinstance(deps, Mapping) or not deps:
        raise DependencyChainFailure("dependency registry requires dependencies")
    return payload


def _git_blob(ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip().lower()
    return value if _SHA40.fullmatch(value) else None


def _resolve_ref(ref: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise DependencyChainFailure(f"unable to resolve ref {ref!r}")
    value = proc.stdout.strip().lower()
    if not _SHA40.fullmatch(value):
        raise DependencyChainFailure(f"ref is not full SHA: {ref!r}")
    return value


def _validate_spec(dependency_id: str, spec: Mapping[str, Any]) -> None:
    if not dependency_id.strip():
        raise DependencyChainFailure("dependency id required")
    for key in ("workflow_path", "parent_paths", "child_paths", "compatibility_tests"):
        if key not in spec:
            raise DependencyChainFailure(f"{dependency_id}: missing {key}")
    if spec.get("wake_on_parent_change") is not True:
        raise DependencyChainFailure(f"{dependency_id}: parent wake must be enabled")
    if spec.get("static_parent_blob_pins_forbidden") is not True:
        raise DependencyChainFailure(f"{dependency_id}: static parent pins must be forbidden")
    for key in ("parent_paths", "child_paths", "compatibility_tests"):
        values = spec.get(key)
        if not isinstance(values, list) or not values:
            raise DependencyChainFailure(f"{dependency_id}: {key} must be non-empty")
        if len(values) != len(set(str(v) for v in values)):
            raise DependencyChainFailure(f"{dependency_id}: duplicate {key}")


def _validate_workflow_contract(spec: Mapping[str, Any]) -> None:
    workflow = ROOT / str(spec["workflow_path"])
    text = workflow.read_text(encoding="utf-8")
    if "dependency_chain_auto_refresh_v1 verify" not in text:
        raise DependencyChainFailure("child workflow does not invoke dependency auto-refresh")
    for path in spec["parent_paths"]:
        path = str(path)
        if text.count(path) < 2:
            raise DependencyChainFailure(f"child workflow does not wake on parent path: {path}")
        if f"git hash-object {path}" in text:
            raise DependencyChainFailure(f"static parent blob pin still present: {path}")
    for test_path in spec["compatibility_tests"]:
        if not (ROOT / str(test_path)).exists():
            raise DependencyChainFailure(f"compatibility test missing: {test_path}")


def build_snapshot(
    dependency_id: str,
    *,
    base: str,
    head: str,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(registry or _load_registry())
    spec = payload["dependencies"].get(dependency_id)
    if not isinstance(spec, Mapping):
        raise DependencyChainFailure(f"unknown dependency id: {dependency_id}")
    _validate_spec(dependency_id, spec)
    _validate_workflow_contract(spec)

    base_sha = _resolve_ref(base)
    head_sha = _resolve_ref(head)
    base_blobs: dict[str, str | None] = {}
    head_blobs: dict[str, str] = {}
    changed: list[str] = []

    for raw_path in spec["parent_paths"]:
        path = str(raw_path)
        before = _git_blob(base_sha, path)
        after = _git_blob(head_sha, path)
        if after is None:
            raise DependencyChainFailure(f"parent path missing at head: {path}")
        base_blobs[path] = before
        head_blobs[path] = after
        if before != after:
            changed.append(path)

    snapshot_payload = {
        "dependency_id": dependency_id,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "parent_blobs": head_blobs,
        "changed_parent_paths": sorted(changed),
    }
    digest = hashlib.sha256(
        json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "DEPENDENCY_REFRESHED" if changed else "DEPENDENCY_CURRENT",
        "dependency_id": dependency_id,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "base_parent_blobs": base_blobs,
        "parent_blobs": head_blobs,
        "changed_parent_paths": sorted(changed),
        "parent_change_detected": bool(changed),
        "child_wake_required": bool(changed),
        "static_parent_blob_pin": False,
        "compatibility_tests": list(spec["compatibility_tests"]),
        "snapshot_digest": digest,
    }


def contract_self_test() -> dict[str, Any]:
    payload = _load_registry()
    for dep_id, spec in payload["dependencies"].items():
        _validate_spec(dep_id, spec)
        _validate_workflow_contract(spec)
    return {
        "status": "GREEN",
        "version": VERSION,
        "registered_dependency_count": len(payload["dependencies"]),
        "dynamic_parent_identity": True,
        "parent_change_wakes_child": True,
        "static_parent_blob_pins_forbidden": True,
        "product_runtime_mutation": False,
        "network_calls": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")
    verify = sub.add_parser("verify")
    verify.add_argument("--dependency-id", required=True)
    verify.add_argument("--base", required=True)
    verify.add_argument("--head", required=True)
    verify.add_argument("--json-out")
    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        result = contract_self_test()
        print("API2_DEPENDENCY_CHAIN_AUTO_REFRESH_V1_GREEN")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "verify":
        result = build_snapshot(args.dependency_id, base=args.base, head=args.head)
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print("API2_DEPENDENCY_CHAIN_AUTO_REFRESH_V1_GREEN")
        print(f"API2_DEPENDENCY_DECISION={result['decision']}")
        print(f"API2_DEPENDENCY_SNAPSHOT={result['snapshot_digest']}")
        return 0

    raise DependencyChainFailure("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
