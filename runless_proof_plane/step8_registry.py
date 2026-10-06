from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry
from .registry import GithubRegistryBackend, _state_hash

FREEZE_TOKEN = "WNBA_PRA_REPAIR_V1_STEP8_FROZEN"
STEP8_ARTIFACTS = (
    "requirements.txt",
    "devsystem/wnba_pra_repair_v1_step8_runtime_recovery_cert.py",
    "tests/test_wnba_pra_repair_v1_step8.py",
    "devsystem/runless_proof_plans/wnba-pra-repair-v1-step8-runtime-recovery.json",
    "devsystem/task_ledgers/wnba-pra-repair-v1-step8-runtime-recovery.json",
)


def _baseline_map(registry):
    result = {}
    for entry in registry["entries"].values():
        for path, blob in entry["artifacts"].items():
            previous = result.get(path)
            if previous is not None and previous != blob:
                raise RuntimeError("STEP8_CONFLICTING_FROZEN_BASELINE:" + path)
            result[path] = blob
    return result


def _write_registry(backend, updated, message):
    validate_registry(updated)
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        backend.client.update_content(
            backend.path,
            text,
            backend.branch,
            message,
            backend._blob_sha,
        )
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc
    readback = backend.read_registry()
    if readback != updated:
        raise RuntimeError("STEP8_REGISTRY_READBACK_MISMATCH")
    return readback


class Step8RegistryBackend(GithubRegistryBackend):
    def _artifacts(self, merged_sha):
        blobs = self.client.tree_blobs(merged_sha)
        missing = [path for path in STEP8_ARTIFACTS if path not in blobs]
        if missing:
            raise RuntimeError("STEP8_FREEZE_ARTIFACTS_MISSING:" + ",".join(missing))
        return {path: blobs[path] for path in sorted(STEP8_ARTIFACTS)}


def freeze_step8(client, merged_sha, freeze_token=FREEZE_TOKEN):
    backend = Step8RegistryBackend(client)
    current = backend.read_registry()
    artifacts = backend._artifacts(merged_sha)

    existing = current["entries"].get(freeze_token)
    if existing:
        if existing.get("source_main_sha") == merged_sha and existing.get("artifacts") == artifacts:
            return {
                "status": "GREEN",
                "decision": "STEP8_FREEZE_ALREADY_COMMITTED",
                "revision": current["revision"],
                "state_hash": current["state_hash"],
                "frozen_token": freeze_token,
                "merged_sha": merged_sha,
                "artifact_count": len(artifacts),
                "active_thaw_count": len(current.get("active_thaws", [])),
            }
        raise RuntimeError("STEP8_FREEZE_TOKEN_CONFLICT")

    thaw_paths = {
        path
        for grant in current.get("active_thaws", [])
        for path in (grant.get("files") or {})
    }
    overlap = sorted(set(artifacts) & thaw_paths)
    if overlap:
        raise RuntimeError("STEP8_CONFLICTING_THAW:" + ",".join(overlap))

    baselines = _baseline_map(current)
    conflicts = [
        path for path, blob in artifacts.items()
        if path in baselines and baselines[path] != blob
    ]
    if conflicts:
        raise RuntimeError("STEP8_FROZEN_BASELINE_CONFLICT:" + ",".join(sorted(conflicts)))

    preserved_thaws = deepcopy(current.get("active_thaws", []))
    updated = deepcopy(current)
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = merged_sha
    updated["entries"][freeze_token] = {
        "status": "FROZEN",
        "checkpoint_id": freeze_token,
        "source_main_sha": merged_sha,
        "artifacts": artifacts,
    }
    updated["active_thaws"] = preserved_thaws
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    readback = _write_registry(
        backend,
        updated,
        f"registry: freeze {freeze_token}",
    )
    entry = readback["entries"].get(freeze_token)
    if not entry or entry.get("source_main_sha") != merged_sha or entry.get("artifacts") != artifacts:
        raise RuntimeError("STEP8_FREEZE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != preserved_thaws:
        raise RuntimeError("STEP8_UNRELATED_THAWS_CHANGED")

    return {
        "status": "GREEN",
        "decision": "STEP8_FROZEN",
        "revision": readback["revision"],
        "state_hash": readback["state_hash"],
        "frozen_token": freeze_token,
        "merged_sha": merged_sha,
        "artifact_count": len(artifacts),
        "active_thaw_count": len(readback.get("active_thaws", [])),
    }


__all__ = ["FREEZE_TOKEN", "STEP8_ARTIFACTS", "freeze_step8"]
