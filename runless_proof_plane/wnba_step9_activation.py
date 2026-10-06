from __future__ import annotations

import base64
import json
import os
from typing import Any, Mapping
from urllib.parse import quote

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from .github_client import GithubClient

PRODUCT_BRANCH = "api2-wnba-step9-segmented-date-r1"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
APP_PATH = "app.py"
EXPECTED_APP_BLOB = "b649282cd6fc771c6621cc09a655414f9422791a"
THAW_ID = "THAW-WNBA-PRA-REPAIR-V1-STEP9-GAME-HANDOFF-APP"
STEP7_MARKER = (
    'WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_RUNTIME = '
    '"WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_2026_10_06_R1"'
)
STEP9_MARKER = (
    'WNBA_PRA_STEP9_GAME_HANDOFF_RUNTIME = '
    '"WNBA_PRA_STEP9_GAME_CENTER_RESPONSE_HANDOFF_2026_10_06_R1"'
)
OLD_IMPORT = (
    "    from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
    "import record_bootstrap_import_ms, render_app"
)
NEW_IMPORT = (
    "    from streamlit_memory_lazy_router_wnba_pra_step9_game_handoff "
    "import record_bootstrap_import_ms, render_app"
)
STEP7_COMPAT = (
    "    # Frozen WNBA PRA Repair V1 Step 7 compatibility: "
    "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
    "import record_bootstrap_import_ms, render_app"
)


class Step9ActivationFailure(RuntimeError):
    pass


def _decode_content(item: Mapping[str, Any]) -> str:
    raw = str(item.get("content") or "").replace("\n", "")
    return base64.b64decode(raw).decode("utf-8")


def _read_registry(client: GithubClient) -> tuple[dict[str, Any], str]:
    item = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not isinstance(item, Mapping):
        raise Step9ActivationFailure("STEP9_REGISTRY_CONTENT_MISSING")
    payload = json.loads(_decode_content(item))
    validate_registry(payload)
    return payload, str(item.get("sha") or "")


def _exact_thaw(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for grant in payload.get("active_thaws") or []:
        if isinstance(grant, Mapping) and str(grant.get("thaw_id") or "") == THAW_ID:
            return grant
    return None


def _assert_app_baseline(payload: Mapping[str, Any]) -> None:
    blobs: set[str] = set()
    for entry in (payload.get("entries") or {}).values():
        artifacts = entry.get("artifacts") if isinstance(entry, Mapping) else None
        if isinstance(artifacts, Mapping) and APP_PATH in artifacts:
            blobs.add(str(artifacts[APP_PATH]).lower())
    if not blobs:
        raise Step9ActivationFailure("STEP9_APP_NOT_FROZEN")
    if blobs != {EXPECTED_APP_BLOB}:
        raise Step9ActivationFailure(
            "STEP9_APP_FROZEN_BASELINE_DRIFT:" + ",".join(sorted(blobs))
        )
    for grant in payload.get("active_thaws") or []:
        if not isinstance(grant, Mapping) or str(grant.get("status") or "") != "ACTIVE":
            continue
        files = grant.get("files") if isinstance(grant.get("files"), Mapping) else {}
        if APP_PATH in files and str(grant.get("thaw_id") or "") != THAW_ID:
            raise Step9ActivationFailure(
                "STEP9_APP_COMPETING_THAW:" + str(grant.get("thaw_id") or "")
            )


def _target_app_blob(client: GithubClient, target_sha: str) -> str:
    blobs = client.tree_blobs(target_sha)
    return str(blobs.get(APP_PATH) or "").lower()


def _verify_existing_thaw(
    client: GithubClient,
    grant: Mapping[str, Any],
    expected_head: str,
) -> tuple[str, str]:
    files = grant.get("files") if isinstance(grant.get("files"), Mapping) else {}
    pair = files.get(APP_PATH) if isinstance(files.get(APP_PATH), Mapping) else None
    if pair is None:
        raise Step9ActivationFailure("STEP9_THAW_APP_PAIR_MISSING")
    if str(pair.get("from_blob") or "").lower() != EXPECTED_APP_BLOB:
        raise Step9ActivationFailure("STEP9_THAW_FROM_BLOB_DRIFT")
    target_sha = str(grant.get("target_head_sha") or "").lower()
    to_blob = str(pair.get("to_blob") or "").lower()
    if len(target_sha) != 40 or len(to_blob) != 40:
        raise Step9ActivationFailure("STEP9_THAW_IDENTITY_INVALID")
    target = client.commit(target_sha)
    parents = [str(p.get("sha") or "").lower() for p in target.get("parents") or []]
    if expected_head.lower() not in parents:
        raise Step9ActivationFailure("STEP9_THAW_TARGET_PARENT_DRIFT")
    if _target_app_blob(client, target_sha) != to_blob:
        raise Step9ActivationFailure("STEP9_THAW_TARGET_BLOB_DRIFT")
    return target_sha, to_blob


def _stage_target(client: GithubClient, expected_head: str) -> tuple[str, str]:
    app = client.content(APP_PATH, ref=PRODUCT_BRANCH)
    if not isinstance(app, Mapping):
        raise Step9ActivationFailure("STEP9_APP_CONTENT_MISSING")
    if str(app.get("sha") or "").lower() != EXPECTED_APP_BLOB:
        raise Step9ActivationFailure("STEP9_APP_BRANCH_BLOB_DRIFT")
    text = _decode_content(app)
    if text.count(STEP7_MARKER) != 1:
        raise Step9ActivationFailure("STEP9_STEP7_MARKER_COUNT_INVALID")
    if STEP9_MARKER in text or NEW_IMPORT in text:
        raise Step9ActivationFailure("STEP9_APP_ALREADY_PARTIALLY_ACTIVATED")
    if text.count(OLD_IMPORT) != 1:
        raise Step9ActivationFailure("STEP9_OLD_IMPORT_COUNT_INVALID")
    new_text = text.replace(STEP7_MARKER, STEP7_MARKER + "\n" + STEP9_MARKER, 1)
    new_text = new_text.replace(OLD_IMPORT, NEW_IMPORT + "\n" + STEP7_COMPAT, 1)

    blob = client.request(
        "POST",
        "/git/blobs",
        json={"content": new_text, "encoding": "utf-8"},
    )
    new_blob = str(blob.get("sha") or "").lower()
    base_commit = client.commit(expected_head)
    base_tree = str(((base_commit.get("commit") or {}).get("tree") or {}).get("sha") or "")
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
            "message": "fix: activate WNBA Step 9 Game Center response handoff",
            "tree": str(tree.get("sha") or ""),
            "parents": [expected_head],
        },
    )
    target_sha = str(commit.get("sha") or "").lower()
    if len(target_sha) != 40 or _target_app_blob(client, target_sha) != new_blob:
        raise Step9ActivationFailure("STEP9_STAGED_TARGET_IDENTITY_INVALID")
    return target_sha, new_blob


def _grant_thaw(
    client: GithubClient,
    payload: Mapping[str, Any],
    registry_blob: str,
    target_sha: str,
    to_blob: str,
) -> None:
    current = json.loads(json.dumps(payload))
    current["active_thaws"].append(
        {
            "files": {
                APP_PATH: {
                    "from_blob": EXPECTED_APP_BLOB,
                    "to_blob": to_blob,
                }
            },
            "status": "ACTIVE",
            "target_head_sha": target_sha,
            "thaw_id": THAW_ID,
        }
    )
    current["revision"] = int(current["revision"]) + 1
    current["state_hash"] = _hash(_payload_without_hash(current))
    validate_registry(current)
    text = json.dumps(current, indent=2, sort_keys=True) + "\n"
    client.update_content(
        REGISTRY_PATH,
        text,
        REGISTRY_BRANCH,
        f"registry: grant {THAW_ID}",
        registry_blob,
    )


def activate(client: GithubClient, *, expected_head: str) -> dict[str, Any]:
    expected = str(expected_head or "").lower()
    if len(expected) != 40:
        raise Step9ActivationFailure("STEP9_EXPECTED_HEAD_REQUIRED")

    branch_head = client.branch_sha(PRODUCT_BRANCH).lower()
    registry, registry_blob = _read_registry(client)
    _assert_app_baseline(registry)
    thaw = _exact_thaw(registry)

    if branch_head != expected:
        if thaw is None:
            raise Step9ActivationFailure("STEP9_PRODUCT_HEAD_DRIFT_WITHOUT_THAW")
        target_sha, to_blob = _verify_existing_thaw(client, thaw, expected)
        if branch_head != target_sha:
            raise Step9ActivationFailure("STEP9_PRODUCT_HEAD_FOREIGN_DRIFT")
        app = client.content(APP_PATH, ref=PRODUCT_BRANCH)
        if str(app.get("sha") or "").lower() != to_blob:
            raise Step9ActivationFailure("STEP9_ACTIVATED_APP_BLOB_DRIFT")
        return {
            "status": "GREEN",
            "decision": "STEP9_APP_ALREADY_ACTIVATED",
            "product_head": branch_head,
            "app_blob": to_blob,
            "thaw_id": THAW_ID,
        }

    if thaw is None:
        target_sha, to_blob = _stage_target(client, expected)
        _grant_thaw(client, registry, registry_blob, target_sha, to_blob)
        registry, _ = _read_registry(client)
        thaw = _exact_thaw(registry)
        if thaw is None:
            raise Step9ActivationFailure("STEP9_THAW_READBACK_MISSING")
        verified_target, verified_blob = _verify_existing_thaw(client, thaw, expected)
        if verified_target != target_sha or verified_blob != to_blob:
            raise Step9ActivationFailure("STEP9_THAW_READBACK_MISMATCH")
    else:
        target_sha, to_blob = _verify_existing_thaw(client, thaw, expected)

    if client.branch_sha(PRODUCT_BRANCH).lower() != expected:
        raise Step9ActivationFailure("STEP9_PRODUCT_HEAD_CHANGED_BEFORE_ACTIVATION")
    client.request(
        "PATCH",
        f"/git/refs/heads/{quote(PRODUCT_BRANCH, safe='/')}",
        json={"sha": target_sha, "force": False},
    )
    if client.branch_sha(PRODUCT_BRANCH).lower() != target_sha:
        raise Step9ActivationFailure("STEP9_PRODUCT_REF_READBACK_MISMATCH")
    app = client.content(APP_PATH, ref=PRODUCT_BRANCH)
    if str(app.get("sha") or "").lower() != to_blob:
        raise Step9ActivationFailure("STEP9_APP_BLOB_READBACK_MISMATCH")
    text = _decode_content(app)
    if STEP9_MARKER not in text or NEW_IMPORT not in text:
        raise Step9ActivationFailure("STEP9_APP_TEXT_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "decision": "STEP9_APP_ACTIVATED_WITH_EXACT_THAW",
        "previous_head": expected,
        "product_head": target_sha,
        "app_blob": to_blob,
        "thaw_id": THAW_ID,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
    }


def activate_from_env(client: GithubClient) -> dict[str, Any]:
    return activate(
        client,
        expected_head=os.getenv("RPP_WNBA_STEP9_PRODUCT_HEAD", "").strip(),
    )
