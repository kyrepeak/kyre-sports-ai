from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "ec301504ee74fe247eaf62d992b78929d4b2f6ed"
PATCH_MERGE_SHA = "5701d5a27482d3d4f82cc75b29e081fea733ada8"
PATCH_CANDIDATE_SHA = "bb9ef2fea11b6cb9d7617e911dc7dabcecd6e2e4"
PATCH_RECEIPT = "7aea051484ebdb1ae6151cb2da993d955d5e1f26b576ae1b9881f8e35fc45276"
REDEPLOY_CANDIDATE_SHA = "9bb69a4cc3d4f50381c6f19679ae50290c0b7d6a"
REDEPLOY_RECEIPT = "854ff17e3f9cf21295e077dbfe02002ecfbc4d38dfbe35b5e529bfff1965800d"
RUNLESS_APP_ID = 5204253

TARGET_FILE = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
TEST_FILE = "tests/test_wnba_pushstate_repair_v1_step3_game_handoff.py"
OLD_BLOB = "ff4829124afc1004311e0aa4272646a5875c20c8"
NEW_BLOB = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
TEST_BLOB = "54f669061b71049c9c153db96ceada68983611b3"
THAW_ID = "THAW-API2-WNBA-PUSHSTATE-STEP3-GAME-HANDOFF"
FREEZE_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP3_FROZEN"

PUBLIC_PROOF_DEPLOY = "dep-db2nvdui0phs738muphg"
PUBLIC_PROOF_HEAD = "dd218685476b48fc64baf73b819cdd6494063c16"
PUBLIC_PROOF_TOKENS = (
    "WNBA_PUSHSTATE_STEP3_DEPLOYED_SHA=" + MAIN_SHA,
    "WNBA_PUSHSTATE_STEP3_EXACT_DEPLOYMENT_GREEN",
    "WNBA_PUSHSTATE_STEP3_SLATE_GREEN",
    "WNBA_PUSHSTATE_STEP3_GAME_CENTER_GREEN",
    "WNBA_PUSHSTATE_STEP3_PLAYER_PRA_GREEN",
    "WNBA_PUSHSTATE_STEP3_PLAYER_BACK_GAME_GREEN",
    "WNBA_PUSHSTATE_STEP3_GAME_BACK_SLATE_GREEN",
    "WNBA_PUSHSTATE_STEP3_NO_PUSHSTATE_ERROR_GREEN",
    "WNBA_PUSHSTATE_STEP3_NO_PAST_GAMES_GREEN",
    "WNBA_PUSHSTATE_STEP3_PUBLIC_CERT_GREEN",
)

EXPECTED_REGISTRY_REVISION = 145
EXPECTED_REGISTRY_HASH = "92ddb9ff031f74f59e1ab600199b14ea2416958136787c03793c3ca92bbd9199"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_gate(client, sha: str, receipt: str) -> int:
    checks = client.request("GET", f"/commits/{sha}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == sha
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={receipt}"
        ):
            return int(check["id"])
    raise RuntimeError("WNBA_PUSHSTATE_STEP3_REQUIRED_RUNLESS_GATE_MISSING:" + sha)


def _verify_identity(client) -> dict[str, Any]:
    if str(client.branch_sha("main")).lower() != MAIN_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_MAIN_SHA_DRIFT")

    main_commit = client.request("GET", f"/commits/{MAIN_SHA}") or {}
    main_parents = {str(item.get("sha") or "").lower() for item in main_commit.get("parents", [])}
    if PATCH_MERGE_SHA not in main_parents or REDEPLOY_CANDIDATE_SHA not in main_parents:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_FINAL_MERGE_PARENT_DRIFT")

    patch_merge = client.request("GET", f"/commits/{PATCH_MERGE_SHA}") or {}
    patch_parents = {str(item.get("sha") or "").lower() for item in patch_merge.get("parents", [])}
    if PATCH_CANDIDATE_SHA not in patch_parents:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_PATCH_MERGE_PARENT_DRIFT")

    patch_check = _require_gate(client, PATCH_CANDIDATE_SHA, PATCH_RECEIPT)
    redeploy_check = _require_gate(client, REDEPLOY_CANDIDATE_SHA, REDEPLOY_RECEIPT)

    tree = client.tree_blobs(MAIN_SHA)
    if str(tree.get(TARGET_FILE) or "") != NEW_BLOB:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_RUNTIME_BLOB_DRIFT")
    if str(tree.get(TEST_FILE) or "") != TEST_BLOB:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_TEST_BLOB_DRIFT")

    return {
        "patch_candidate_check_id": patch_check,
        "redeploy_candidate_check_id": redeploy_check,
        "runtime_blob": NEW_BLOB,
        "test_blob": TEST_BLOB,
    }


def _publish_main_gate(client, identity: Mapping[str, Any]) -> tuple[int, str]:
    evidence = {
        "main_sha": MAIN_SHA,
        "patch_merge_sha": PATCH_MERGE_SHA,
        "patch_candidate_sha": PATCH_CANDIDATE_SHA,
        "redeploy_candidate_sha": REDEPLOY_CANDIDATE_SHA,
        "identity": dict(identity),
        "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
        "public_proof_head": PUBLIC_PROOF_HEAD,
        "public_proof_tokens": list(PUBLIC_PROOF_TOKENS),
        "public_future_date": "2026-10-07",
        "original_pushstate_error_absent": True,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step3-final-{MAIN_SHA[:16]}",
        task_id="wnba-pushstate-repair-v1-step3-final-closeout",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step3",
        step="3/4-final-public-closeout",
        candidate_sha=MAIN_SHA,
        artifact_map={TARGET_FILE: NEW_BLOB, TEST_FILE: TEST_BLOB},
        dependency_map={
            "patch_merge_sha": PATCH_MERGE_SHA,
            "patch_candidate_sha": PATCH_CANDIDATE_SHA,
            "patch_receipt": PATCH_RECEIPT,
            "redeploy_candidate_sha": REDEPLOY_CANDIDATE_SHA,
            "redeploy_receipt": REDEPLOY_RECEIPT,
            "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
            "public_proof_head": PUBLIC_PROOF_HEAD,
            "proof_authority": "Runless Proof Plane + terminal public Playwright",
        },
        registry_before={
            "revision": EXPECTED_REGISTRY_REVISION,
            "state_hash": EXPECTED_REGISTRY_HASH,
            "thaw_id": THAW_ID,
        },
        registry_after={"freeze_token": FREEZE_TOKEN, "mode": "pending_atomic_forward_port"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, MAIN_SHA, "success", receipt)
    return int(check["id"]), str(receipt["digest"])


def _freeze_registry(client, *, check_id: int, receipt_digest: str) -> dict[str, Any]:
    current, content_sha = _read_registry(client)
    if int(current.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
    if str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")

    entries = current.get("entries") or {}
    owners = []
    for token, entry in entries.items():
        artifacts = entry.get("artifacts") or {}
        if TARGET_FILE in artifacts:
            owners.append((str(token), str(artifacts[TARGET_FILE])))
    if not owners or any(blob != OLD_BLOB for _, blob in owners):
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_FROZEN_BASELINE_DRIFT")

    exact_thaw = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": PATCH_CANDIDATE_SHA,
        "files": {TARGET_FILE: {"from_blob": OLD_BLOB, "to_blob": NEW_BLOB}},
    }
    current_thaws = list(current.get("active_thaws") or [])
    matches = [grant for grant in current_thaws if str(grant.get("thaw_id")) == THAW_ID]
    if matches != [exact_thaw]:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_EXACT_THAW_DRIFT")
    for grant in current_thaws:
        if str(grant.get("thaw_id")) == THAW_ID:
            continue
        if TARGET_FILE in (grant.get("files") or {}):
            raise RuntimeError("WNBA_PUSHSTATE_STEP3_CONFLICTING_THAW")

    updated = deepcopy(current)
    for entry in (updated.get("entries") or {}).values():
        artifacts = entry.get("artifacts") or {}
        if artifacts.get(TARGET_FILE) == OLD_BLOB:
            artifacts[TARGET_FILE] = NEW_BLOB

    updated["active_thaws"] = [
        deepcopy(grant) for grant in current_thaws if str(grant.get("thaw_id")) != THAW_ID
    ]
    existing = (updated.get("entries") or {}).get(FREEZE_TOKEN)
    desired_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": {TARGET_FILE: NEW_BLOB, TEST_FILE: TEST_BLOB},
    }
    if existing is not None and existing != desired_entry:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_FREEZE_TOKEN_CONFLICT")
    updated.setdefault("entries", {})[FREEZE_TOKEN] = desired_entry
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(
            REGISTRY_PATH,
            text,
            REGISTRY_BRANCH,
            f"registry: freeze {FREEZE_TOKEN}",
            content_sha,
        )
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc

    readback, _ = _read_registry(client)
    entry = (readback.get("entries") or {}).get(FREEZE_TOKEN) or {}
    if entry != desired_entry:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_FREEZE_READBACK_MISMATCH")
    if any(str(grant.get("thaw_id")) == THAW_ID for grant in readback.get("active_thaws", [])):
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_THAW_RETIRE_READBACK_FAILED")
    for token, frozen in (readback.get("entries") or {}).items():
        artifacts = frozen.get("artifacts") or {}
        if TARGET_FILE in artifacts and str(artifacts[TARGET_FILE]) != NEW_BLOB:
            raise RuntimeError("WNBA_PUSHSTATE_STEP3_BASELINE_FORWARD_PORT_READBACK_FAILED:" + str(token))
    if int(readback.get("revision") or -1) != EXPECTED_REGISTRY_REVISION + 1:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REGISTRY_REVISION_READBACK_FAILED")

    return {
        "status": "GREEN",
        "freeze_token": FREEZE_TOKEN,
        "main_sha": MAIN_SHA,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws", [])),
        "runless_check_id": check_id,
        "runless_receipt": receipt_digest,
        "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
    }


def closeout_step3(client) -> dict[str, Any]:
    identity = _verify_identity(client)
    check_id, receipt_digest = _publish_main_gate(client, identity)
    return _freeze_registry(client, check_id=check_id, receipt_digest=receipt_digest)


def install_startup_closeout(app):
    app.state.wnba_pushstate_step3_final_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _closeout_wnba_pushstate_step3():
        try:
            app.state.wnba_pushstate_step3_final_closeout = closeout_step3(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step3_final_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
