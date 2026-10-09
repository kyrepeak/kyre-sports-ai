from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import (
    _hash as frozen_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

TASK_ID = "cfb-game-total-page1-visual-cleanup-step1-target-lock"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
STEP = "1/5"
CANDIDATE_SHA = "f314be11cd775e23f4d4490f0a2b22edcc2409b5"
MERGED_MAIN_SHA = "e43e244328fae9c55e10b66d7d86ed752edfe518"
PR_NUMBER = 1479
PROOF_ID = "cfb-game-total-page1-visual-cleanup-step1-target-lock-f314be11cd775e23-0789dff2206270c3"
PROOF_DIGEST = "2836224fe804bd9828d4a4b970511d7061e41a7c5f9dfaa1607e2cf63eee0ee5"
CHECK_ID = 113664847748
CHECK_APP_ID = 5204253

FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP1_TARGET_LOCK_FROZEN"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 211
EXPECTED_REGISTRY_HASH = "a3e4f9346dcf790804ed33526776dd6a02722886b5d04aafb2a310e8d1d6b3a1"

RECEIPT_BRANCH = "runless-proof-receipts"
RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PROOF_ID}.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
PRODUCT_LEASE_ID = "SCOPE-LEASE-CFB-GT-P1-VISUAL-CLEANUP-STEP1-240"
FINALIZER_LEASE_ID = "SCOPE-LEASE-0302C7C3D85D70CC0920E7C5"
FINALIZER_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step1-finalizer"

ARTIFACT_MAP = {
    "devsystem/cfb_game_total_page1_visual_cleanup_step1_target_lock_v1.py": "aaa6a84f93c22ab8023b1483059567b9fc922a5a",
    "devsystem/execution_plans/cfb-game-total-page1-visual-cleanup-step1-target-lock.json": "a63796325e2fc48a4d312269c4c42ba058d5bd21",
    "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step1-target-lock.json": "fa21822e966a7762e6891046e68bcbc9af49279f",
    "devsystem/task_ledgers/cfb-game-total-page1-visual-cleanup-step1-target-lock.json": "71368283f11127f10f6dc461f47deea9e2237db6",
    "docs/superpowers/plans/2026-10-09-cfb-game-total-page1-visual-cleanup-step1-target-lock.md": "1ecf5fa700c7518e7e4d6a1d3fcbd8167c7139cf",
    "tests/test_cfb_game_total_page1_visual_cleanup_step1_target_lock.py": "65809d25c11f3af029c9cd64fb1cbbefc553e1a8",
}


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError(label + "_DECODE_FAILED") from exc


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _live_finalizer_holder(client) -> dict | None:
    state = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "CFB_GT_VISUAL_STEP1_LEASE")
    )
    now = datetime.now(timezone.utc)
    return next(
        (
            holder for holder in state.get("holders", [])
            if holder.get("lease_id") == FINALIZER_LEASE_ID
            and holder.get("owner_id") == FINALIZER_OWNER
            and now < _utc(holder["expires_at_utc"])
        ),
        None,
    )


def should_run(client) -> bool:
    try:
        return _live_finalizer_holder(client) is not None
    except Exception:
        return False


def _validate_authority(client) -> dict:
    state = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "CFB_GT_VISUAL_STEP1_LEASE")
    )
    holder = _live_finalizer_holder(client)
    if holder is None:
        raise RuntimeError("CFB_GT_VISUAL_STEP1_FINALIZER_LEASE_NOT_LIVE")
    if not any(item.get("lease_id") == PRODUCT_LEASE_ID for item in state.get("holders", [])):
        raise RuntimeError("CFB_GT_VISUAL_STEP1_PRODUCT_LEASE_MISSING")

    scope = holder.get("scope") or {}
    identity = scope.get("resource_identity") or {}
    expected_identity = {
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MERGED_MAIN_SHA,
        "receipt_digest": PROOF_DIGEST,
        "registry_revision": str(EXPECTED_REGISTRY_REVISION),
        "registry_state_hash": EXPECTED_REGISTRY_HASH,
    }
    if any(str(identity.get(k) or "") != value for k, value in expected_identity.items()):
        raise RuntimeError("CFB_GT_VISUAL_STEP1_FINALIZER_IDENTITY_DRIFT")
    required_paths = {
        REGISTRY_PATH,
        LEASE_PATH,
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
        "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step1_closeout.py",
    }
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("CFB_GT_VISUAL_STEP1_FINALIZER_SCOPE_DRIFT")
    return state


def _validate_gate(client) -> dict:
    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + PROOF_DIGEST
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            int(run.get("id") or 0) == CHECK_ID
            and str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("name") or "") == "runless-final-gate"
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
            and str(output.get("summary") or "") == expected_summary
        ):
            return {"check_id": CHECK_ID, "app_id": CHECK_APP_ID, "conclusion": "success"}
    raise RuntimeError("CFB_GT_VISUAL_STEP1_RUNLESS_GATE_DRIFT")


def _validate_receipt(client) -> dict:
    receipt = _decode_json(client.content(RECEIPT_PATH, ref=RECEIPT_BRANCH), "CFB_GT_VISUAL_STEP1_RECEIPT")
    if (
        str(receipt.get("proof_id") or "") != PROOF_ID
        or str(receipt.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(receipt.get("digest") or "") != PROOF_DIGEST
        or str(receipt.get("failure_class") or "") != "NONE"
        or receipt.get("artifact_map") != ARTIFACT_MAP
    ):
        raise RuntimeError("CFB_GT_VISUAL_STEP1_RECEIPT_DRIFT")
    return receipt


def _verify_merged_artifacts(client) -> dict[str, str]:
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("CFB_GT_VISUAL_STEP1_MAIN_DRIFT")
    tree = client.tree_blobs(MERGED_MAIN_SHA)
    observed = {path: str(tree.get(path) or "") for path in ARTIFACT_MAP}
    if observed != ARTIFACT_MAP:
        raise RuntimeError("CFB_GT_VISUAL_STEP1_MERGED_ARTIFACT_DRIFT")
    return observed


def _freeze_once(client) -> dict:
    registry_head = client.branch_sha(REGISTRY_BRANCH)
    raw = client.content(REGISTRY_PATH, ref=registry_head)
    current = _decode_json(raw, "CFB_GT_VISUAL_STEP1_REGISTRY")
    validate_registry(current)

    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if (
            existing.get("status") == "FROZEN"
            and existing.get("checkpoint_id") == FREEZE_TOKEN
            and existing.get("source_main_sha") == MERGED_MAIN_SHA
            and existing.get("artifacts") == ARTIFACT_MAP
        ):
            return {
                "decision": "CFB_GT_VISUAL_STEP1_ALREADY_FROZEN",
                "registry_revision": int(current["revision"]),
                "registry_state_hash": str(current["state_hash"]),
                "artifact_count": len(ARTIFACT_MAP),
                "active_thaw_count": len(current.get("active_thaws") or []),
            }
        raise RuntimeError("CFB_GT_VISUAL_STEP1_FREEZE_TOKEN_CONFLICT")

    if (
        int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
        or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH
    ):
        raise RuntimeError(
            "CFB_GT_VISUAL_STEP1_REGISTRY_BASELINE_DRIFT:"
            f"observed_revision={current.get('revision')}:"
            f"observed_hash={current.get('state_hash')}:"
            f"registry_head={registry_head}"
        )

    thaw_paths = {
        path for grant in current.get("active_thaws", [])
        for path in (grant.get("files") or {})
    }
    overlap = sorted(set(ARTIFACT_MAP) & thaw_paths)
    if overlap:
        raise RuntimeError("CFB_GT_VISUAL_STEP1_ACTIVE_THAW_CONFLICT:" + ",".join(overlap))

    flattened: dict[str, str] = {}
    for entry in (current.get("entries") or {}).values():
        flattened.update(entry.get("artifacts") or {})
    conflicts = sorted(
        path for path, blob in ARTIFACT_MAP.items()
        if path in flattened and str(flattened[path]) != blob
    )
    if conflicts:
        raise RuntimeError("CFB_GT_VISUAL_STEP1_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))

    updated = deepcopy(current)
    updated["revision"] = EXPECTED_REGISTRY_REVISION + 1
    updated["source_main_sha"] = MERGED_MAIN_SHA
    updated["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_MAIN_SHA,
        "artifacts": dict(sorted(ARTIFACT_MAP.items())),
    }
    updated["active_thaws"] = deepcopy(current.get("active_thaws", []))
    updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        "registry: freeze CFB Game Total visual cleanup Step1 target lock",
        raw["sha"],
    )
    return {
        "decision": "CFB_GT_VISUAL_STEP1_FREEZE_SUBMITTED",
        "registry_revision": int(updated["revision"]),
        "registry_state_hash": str(updated["state_hash"]),
        "artifact_count": len(ARTIFACT_MAP),
        "active_thaw_count": len(updated.get("active_thaws") or []),
    }


def execute(app) -> dict:
    client = app.state.github_client
    _validate_authority(client)
    gate = _validate_gate(client)
    receipt = _validate_receipt(client)
    _verify_merged_artifacts(client)
    freeze = _freeze_once(client)
    return {
        "status": "GREEN",
        "decision": freeze["decision"],
        "step": STEP,
        "main_sha": MERGED_MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "pr_number": PR_NUMBER,
        "proof_id": PROOF_ID,
        "receipt_digest": PROOF_DIGEST,
        "gate": gate,
        "receipt_failure_class": receipt.get("failure_class"),
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": freeze["registry_revision"],
        "registry_state_hash": freeze["registry_state_hash"],
        "frozen_artifact_count": freeze["artifact_count"],
        "active_thaw_count": freeze["active_thaw_count"],
        "product_runtime_mutations": 0,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step1_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP1_FINAL_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step1_closeout, sort_keys=True),
            flush=True,
        )

    return app
