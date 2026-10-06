from __future__ import annotations

import json
from copy import deepcopy

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry
from .registry import GithubRegistryBackend, _state_hash

THAW_ID = "THAW-WNBA-PRA-REPAIR-V1-STEP7-APP"
FREEZE_TOKEN = "WNBA_PRA_REPAIR_V1_STEP7_FROZEN"
STEP7_ARTIFACTS = (
    "app.py",
    "wnba_pra_repair_v1_step7_final_integration.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py",
    "tests/test_wnba_pra_repair_v1_step7.py",
    "devsystem/wnba_pra_repair_v1_step7_final_integration_cert.py",
    "devsystem/runless_proof_plans/wnba-pra-repair-v1-step7-final-integration.json",
    "devsystem/task_ledgers/wnba-pra-repair-v1-step7-final-integration.json",
)


def _baseline_map(registry):
    result = {}
    for entry in registry["entries"].values():
        for path, blob in entry["artifacts"].items():
            previous = result.get(path)
            if previous is not None and previous != blob:
                raise RuntimeError("STEP7_CONFLICTING_FROZEN_BASELINE:" + path)
            result[path] = blob
    return result


def _step7_thaw(current):
    matches = [
        grant for grant in current.get("active_thaws", [])
        if grant.get("thaw_id") == THAW_ID
    ]
    if len(matches) != 1:
        raise RuntimeError("STEP7_THAW_REQUIRED")
    grant = matches[0]
    files = grant.get("files") or {}
    if set(files) != {"app.py"}:
        raise RuntimeError("STEP7_THAW_SCOPE_MISMATCH")
    for other in current.get("active_thaws", []):
        if other.get("thaw_id") == THAW_ID:
            continue
        if "app.py" in (other.get("files") or {}):
            raise RuntimeError("STEP7_APP_THAW_OWNERSHIP_CONFLICT")
    return grant


def build_step7_registry_update(current, artifacts, merged_sha, freeze_token=FREEZE_TOKEN):
    validate_registry(current)
    if set(artifacts) != set(STEP7_ARTIFACTS):
        raise RuntimeError("STEP7_FREEZE_ARTIFACT_SCOPE_MISMATCH")

    grant = _step7_thaw(current)
    pair = grant["files"]["app.py"]
    old_app = str(pair.get("from_blob") or "").lower()
    new_app = str(pair.get("to_blob") or "").lower()
    if str(artifacts.get("app.py") or "").lower() != new_app:
        raise RuntimeError("STEP7_APP_THAW_TARGET_MISMATCH")

    baselines = _baseline_map(current)
    if baselines.get("app.py") != old_app:
        raise RuntimeError("STEP7_APP_FROZEN_BASELINE_MISMATCH")

    unrelated_before = deepcopy([
        grant for grant in current.get("active_thaws", [])
        if grant.get("thaw_id") != THAW_ID
    ])
    plan = plan_baseline_forward_port(
        current,
        updates={"app.py": {"from_blob": old_app, "to_blob": new_app}},
        source_main_sha=merged_sha,
    )
    updated = plan["registry"]

    if any(grant.get("thaw_id") == THAW_ID for grant in updated.get("active_thaws", [])):
        raise RuntimeError("STEP7_THAW_NOT_RETIRED")
    if updated.get("active_thaws", []) != unrelated_before:
        raise RuntimeError("STEP7_UNRELATED_THAWS_CHANGED")

    thaw_paths = {
        path
        for grant in updated.get("active_thaws", [])
        for path in (grant.get("files") or {})
    }
    overlap = sorted(set(artifacts) & thaw_paths)
    if overlap:
        raise RuntimeError("STEP7_CONFLICTING_THAW:" + ",".join(overlap))

    forwarded = _baseline_map(updated)
    conflicts = [
        path for path, blob in artifacts.items()
        if path in forwarded and forwarded[path] != blob
    ]
    if conflicts:
        raise RuntimeError("STEP7_FROZEN_BASELINE_CONFLICT:" + ",".join(sorted(conflicts)))

    if freeze_token in updated["entries"]:
        raise RuntimeError("STEP7_FREEZE_TOKEN_CONFLICT")
    updated["entries"][freeze_token] = {
        "status": "FROZEN",
        "checkpoint_id": freeze_token,
        "source_main_sha": merged_sha,
        "artifacts": dict(artifacts),
    }
    updated["source_main_sha"] = merged_sha
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    return updated


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
        raise RuntimeError("STEP7_REGISTRY_READBACK_MISMATCH")
    return readback


class Step7RegistryBackend(GithubRegistryBackend):
    def _artifacts(self, merged_sha):
        blobs = self.client.tree_blobs(merged_sha)
        missing = [path for path in STEP7_ARTIFACTS if path not in blobs]
        if missing:
            raise RuntimeError("STEP7_FREEZE_ARTIFACTS_MISSING:" + ",".join(missing))
        return {path: blobs[path] for path in sorted(STEP7_ARTIFACTS)}


def freeze_step7(client, merged_sha, freeze_token=FREEZE_TOKEN):
    backend = Step7RegistryBackend(client)
    current = backend.read_registry()
    artifacts = backend._artifacts(merged_sha)

    existing = current["entries"].get(freeze_token)
    if existing:
        if existing.get("source_main_sha") == merged_sha and existing.get("artifacts") == artifacts:
            if any(grant.get("thaw_id") == THAW_ID for grant in current.get("active_thaws", [])):
                raise RuntimeError("STEP7_FREEZE_EXISTS_BUT_THAW_ACTIVE")
            return {
                "status": "GREEN",
                "decision": "STEP7_FREEZE_ALREADY_COMMITTED",
                "revision": current["revision"],
                "state_hash": current["state_hash"],
                "frozen_token": freeze_token,
                "merged_sha": merged_sha,
                "artifact_count": len(artifacts),
                "active_thaw_count": len(current.get("active_thaws", [])),
            }
        raise RuntimeError("STEP7_FREEZE_TOKEN_CONFLICT")

    grant = _step7_thaw(current)
    commit = client.commit(merged_sha)
    parents = {str(parent.get("sha") or "").lower() for parent in commit.get("parents", [])}
    if str(grant.get("target_head_sha") or "").lower() not in parents:
        raise RuntimeError("STEP7_THAW_TARGET_NOT_MERGED_PARENT")

    updated = build_step7_registry_update(current, artifacts, merged_sha, freeze_token)
    readback = _write_registry(
        backend,
        updated,
        f"registry: freeze {freeze_token} and retire {THAW_ID}",
    )

    entry = readback["entries"].get(freeze_token)
    if not entry or entry.get("source_main_sha") != merged_sha or entry.get("artifacts") != artifacts:
        raise RuntimeError("STEP7_FREEZE_READBACK_MISMATCH")
    if any(grant.get("thaw_id") == THAW_ID for grant in readback.get("active_thaws", [])):
        raise RuntimeError("STEP7_THAW_REMAINS_ACTIVE")

    return {
        "status": "GREEN",
        "decision": "STEP7_FROZEN",
        "revision": readback["revision"],
        "state_hash": readback["state_hash"],
        "frozen_token": freeze_token,
        "merged_sha": merged_sha,
        "artifact_count": len(artifacts),
        "active_thaw_count": len(readback.get("active_thaws", [])),
        "app_baseline_to": artifacts["app.py"],
    }


__all__ = [
    "FREEZE_TOKEN",
    "STEP7_ARTIFACTS",
    "THAW_ID",
    "build_step7_registry_update",
    "freeze_step7",
]
