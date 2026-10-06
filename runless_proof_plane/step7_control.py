from __future__ import annotations

import base64
import json
from copy import deepcopy
from urllib.parse import quote

from devsystem.frozen_artifact_registry_v1 import validate_registry
from .registry import GithubRegistryBackend, _state_hash

TARGET_BRANCH = "api2-wnba-pra-repair-v1-step7-final-integration-r1"
EXPECTED_PRE_APP_HEAD = "8dbe817a50b409009c15e704c8f5dd82a1f71cb4"
THAW_ID = "THAW-WNBA-PRA-REPAIR-V1-STEP7-APP"
APP_PATH = "app.py"
RUNTIME_MARKER = (
    'WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_RUNTIME = '
    '"WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_2026_10_06_R1"'
)
OLD_IMPORT = (
    "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback "
    "import record_bootstrap_import_ms, render_app"
)
NEW_IMPORT = (
    "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
    "import record_bootstrap_import_ms, render_app"
)
STEP5_MARKER = (
    'WNBA_PRA_REPAIR_V1_STEP5_DECISION_FALLBACK_RUNTIME = '
    '"WNBA_PRA_REPAIR_V1_STEP5_DECISION_FALLBACK_2026_10_06_R1"'
)
STEP5_COMPAT = (
    "    # Frozen WNBA PRA Repair V1 Step 5 compatibility: "
    "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback "
    "import record_bootstrap_import_ms, render_app"
)


def _decode_content(payload: dict) -> str:
    raw = str(payload.get("content") or "").replace("\n", "")
    return base64.b64decode(raw).decode("utf-8")


def _patched_app(text: str) -> str:
    if RUNTIME_MARKER in text and NEW_IMPORT in text:
        return text
    if text.count(STEP5_MARKER) != 1:
        raise RuntimeError("STEP7_APP_STEP5_MARKER_DRIFT")
    if text.count(OLD_IMPORT) != 1:
        raise RuntimeError("STEP7_APP_ACTIVE_IMPORT_DRIFT")
    text = text.replace(STEP5_MARKER, STEP5_MARKER + "\n" + RUNTIME_MARKER, 1)
    text = text.replace(OLD_IMPORT, NEW_IMPORT + "\n" + STEP5_COMPAT, 1)
    return text


def _baseline_for(registry: dict, path: str) -> str:
    found = set()
    for entry in registry.get("entries", {}).values():
        artifacts = entry.get("artifacts") if isinstance(entry, dict) else None
        if isinstance(artifacts, dict) and path in artifacts:
            found.add(str(artifacts[path]).lower())
    if len(found) != 1:
        raise RuntimeError("STEP7_APP_FROZEN_BASELINE_AMBIGUOUS")
    return next(iter(found))


def _write_registry(backend: GithubRegistryBackend, updated: dict) -> dict:
    validate_registry(updated)
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        backend.client.update_content(
            backend.path,
            text,
            backend.branch,
            f"registry: grant {THAW_ID}",
            backend._blob_sha,
        )
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc
    readback = backend.read_registry()
    if readback != updated:
        raise RuntimeError("STEP7_THAW_REGISTRY_READBACK_MISMATCH")
    return readback


def _commit_app_patch(client, head_sha: str, app_payload: dict, new_text: str) -> tuple[str, str]:
    blob = client.request(
        "POST",
        "/git/blobs",
        json={"content": new_text, "encoding": "utf-8"},
    )
    new_blob = str(blob["sha"]).lower()
    base_commit = client.commit(head_sha)
    base_tree = str(base_commit["commit"]["tree"]["sha"])
    tree = client.request(
        "POST",
        "/git/trees",
        json={
            "base_tree": base_tree,
            "tree": [
                {"path": APP_PATH, "mode": "100644", "type": "blob", "sha": new_blob}
            ],
        },
    )
    commit = client.request(
        "POST",
        "/git/commits",
        json={
            "message": "WNBA Step 7 — activate exact final integration runtime",
            "tree": tree["sha"],
            "parents": [head_sha],
        },
    )
    return str(commit["sha"]).lower(), new_blob


def _move_target_ref(client, expected_head: str, candidate_sha: str) -> None:
    observed = client.branch_sha(TARGET_BRANCH)
    if observed == candidate_sha:
        return
    if observed != expected_head:
        raise RuntimeError("STEP7_TARGET_BRANCH_HEAD_DRIFT")
    client.request(
        "PATCH",
        f"/git/refs/heads/{quote(TARGET_BRANCH, safe='/')}",
        json={"sha": candidate_sha, "force": False},
    )
    if client.branch_sha(TARGET_BRANCH) != candidate_sha:
        raise RuntimeError("STEP7_TARGET_BRANCH_READBACK_MISMATCH")


def apply_step7_app_patch(client) -> dict:
    head = client.branch_sha(TARGET_BRANCH)
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    existing = next(
        (grant for grant in registry.get("active_thaws", []) if grant.get("thaw_id") == THAW_ID),
        None,
    )

    if existing:
        candidate = str(existing.get("target_head_sha") or "").lower()
        pair = (existing.get("files") or {}).get(APP_PATH) or {}
        if not candidate or not pair:
            raise RuntimeError("STEP7_EXISTING_THAW_INVALID")
        if head not in {EXPECTED_PRE_APP_HEAD, candidate}:
            raise RuntimeError("STEP7_EXISTING_THAW_HEAD_DRIFT")
        commit = client.commit(candidate)
        parent_shas = [str(item.get("sha") or "") for item in commit.get("parents", [])]
        blobs = client.tree_blobs(candidate)
        if EXPECTED_PRE_APP_HEAD not in parent_shas or blobs.get(APP_PATH) != pair.get("to_blob"):
            raise RuntimeError("STEP7_EXISTING_THAW_CANDIDATE_MISMATCH")
        _move_target_ref(client, EXPECTED_PRE_APP_HEAD, candidate)
        return {
            "status": "GREEN",
            "decision": "STEP7_APP_PATCH_ALREADY_PREPARED",
            "candidate_sha": candidate,
            "app_from_blob": str(pair.get("from_blob")),
            "app_to_blob": str(pair.get("to_blob")),
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "thaw_id": THAW_ID,
        }

    if head != EXPECTED_PRE_APP_HEAD:
        raise RuntimeError("STEP7_PRE_APP_HEAD_MISMATCH")

    app_payload = client.content(APP_PATH, TARGET_BRANCH)
    old_blob = str(app_payload.get("sha") or "").lower()
    baseline = _baseline_for(registry, APP_PATH)
    if old_blob != baseline:
        raise RuntimeError("STEP7_APP_DOES_NOT_MATCH_FROZEN_BASELINE")
    for grant in registry.get("active_thaws", []):
        if APP_PATH in (grant.get("files") or {}):
            raise RuntimeError("STEP7_APP_ALREADY_THAWED_BY_OTHER_OWNER")

    old_text = _decode_content(app_payload)
    new_text = _patched_app(old_text)
    if new_text == old_text:
        raise RuntimeError("STEP7_APP_PATCH_NOOP_WITHOUT_THAW")

    candidate_sha, new_blob = _commit_app_patch(client, head, app_payload, new_text)
    updated = deepcopy(registry)
    updated["active_thaws"].append(
        {
            "thaw_id": THAW_ID,
            "status": "ACTIVE",
            "target_head_sha": candidate_sha,
            "files": {
                APP_PATH: {
                    "from_blob": old_blob,
                    "to_blob": new_blob,
                }
            },
        }
    )
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    readback = _write_registry(backend, updated)

    grant = next(
        (item for item in readback.get("active_thaws", []) if item.get("thaw_id") == THAW_ID),
        None,
    )
    if not grant or grant.get("target_head_sha") != candidate_sha:
        raise RuntimeError("STEP7_THAW_READBACK_MISMATCH")

    _move_target_ref(client, head, candidate_sha)
    return {
        "status": "GREEN",
        "decision": "STEP7_APP_PATCH_AND_THAW_COMMITTED",
        "candidate_sha": candidate_sha,
        "app_from_blob": old_blob,
        "app_to_blob": new_blob,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "thaw_id": THAW_ID,
    }


__all__ = [
    "APP_PATH",
    "EXPECTED_PRE_APP_HEAD",
    "RUNTIME_MARKER",
    "TARGET_BRANCH",
    "THAW_ID",
    "apply_step7_app_patch",
]
