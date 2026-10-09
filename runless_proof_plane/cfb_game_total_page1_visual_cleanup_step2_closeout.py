from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

TASK_ID = "cfb-game-total-page1-visual-cleanup-step2-top-shell"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
STEP = "2/5"
SOURCE_MAIN_SHA = "e43e244328fae9c55e10b66d7d86ed752edfe518"
CANDIDATE_SHA = "fedf0fbb530ece2b600b0b54b3c7d446c96b3539"
MAIN_SHA = "036dbb2ab3a0e24ce3e1cb16c1b2f9469cfce2f4"
PR_NUMBER = 1480
PREMERGE_PROOF_ID = "cfb-game-total-page1-visual-cleanup-step2-top-shell-fedf0fbb530ece2b-24ffc3aefb77e103"
PREMERGE_DIGEST = "0e5ef2e5241c42aae505421a39f843142af5c2a458d9056ba86ba796c6dbd589"
PREMERGE_CHECK_ID = 113682881194
POSTMERGE_PROOF_ID = "cfb-game-total-page1-visual-cleanup-step2-top-shell-036dbb2ab3a0e24c-postmerge-reuse"
POSTMERGE_DIGEST = "cd283a7ab539ecc358b475fee181d6ffb59665b3adf10948f7005e9be26fe632"
CHECK_APP_ID = 5204253
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP2_TOP_SHELL_FROZEN"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 212
EXPECTED_REGISTRY_HASH = "379aca9256a2333dbfeb6d5a4d1411682430c010e9e15b84560f3c3029c5bcea"
EXPECTED_ACTIVE_THAWS = (
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
)

RECEIPT_BRANCH = "runless-proof-receipts"
POSTMERGE_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{POSTMERGE_PROOF_ID}.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
FINALIZER_LEASE_ID = "SCOPE-LEASE-23950CFC381FC218093BD9D3"
FINALIZER_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step2-finalizer"

ARTIFACT_MAP = {
    "cfb_game_total_page1_visual_cleanup_step2_activation_v1.py": "113f4075d1de69dd87e19877b7b398132225e072",
    "cfb_game_total_page1_visual_cleanup_step2_top_shell_v1.py": "978595051a1cda0ed31694fcb177928877a897c4",
    "devsystem/execution_plans/cfb-game-total-page1-visual-cleanup-step2-top-shell.json": "c1bdbcbc61c4b13a2cfcb303a642d46441c71b04",
    "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step2-top-shell.json": "8af8ccac3ceac0ac35e106d5145baa499ce35bec",
    "devsystem/task_ledgers/cfb-game-total-page1-visual-cleanup-step2-top-shell.json": "6082b887bf036af2caef082f6ee5dca950d55787",
    "kyre_game_total_theme_v1.py": "e7156c7f0d5e09cd42fcb811286c8e4e2437ead2",
    "tests/test_cfb_game_total_page1_visual_cleanup_step2_top_shell.py": "fd9a024e78e5de3c40f3677a05f868006adf2314",
}

DEPENDENCY_MAP = {
    "cfb_game_total_clean_page_v34.py": "d130880220b749bcfde38b4949780313a3609fb7",
    "cfb_game_total_clean_page_v36.py": "3970337b170ccdc44870699a8a35cf800dea6867",
    "cfb_game_total_clean_page_v38.py": "556b1204da18858d68e48dcb44571fc8f5be2d70",
    "cfb_game_total_page1_step3_presentation_v1.py": "13c0deabcacba311999447608eafd07eef778565",
    "cfb_game_total_page1_v2_step4_public_repair_v1.py": "6e969228a46d36a00737f941fb2bf6f7f2a2ab8c",
    "devsystem/cfb_game_total_page1_visual_cleanup_step1_target_lock_v1.py": "aaa6a84f93c22ab8023b1483059567b9fc922a5a",
    "kyre_universal_shell_runtime_v1.py": "40a37ff350262256f590a430ea9494d52c0c5304",
    "streamlit_memory_lazy_router_v160.py": "913cf8ac7478fdc105995238b254f28d1d411bc6",
    "streamlit_memory_lazy_router_v181.py": "8adc51774159470d50377c6f8e0591abb1c7f60d",
    "streamlit_memory_lazy_router_v190.py": "fca1442c144d8ff02868ed0371a92f72257d697e",
    "streamlit_memory_lazy_router_v191.py": "1a4a2df127a060519d62ed96dd39f6c14bb79449",
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


def validate_postmerge_receipt(receipt: dict) -> dict:
    checks = {
        "proof_id": POSTMERGE_PROOF_ID,
        "digest": POSTMERGE_DIGEST,
        "failure_class": "NONE",
        "proof_reuse_decision": "REUSE_APPROVED",
        "merged_main_sha": MAIN_SHA,
        "source_candidate_sha": CANDIDATE_SHA,
        "freeze_token": FREEZE_TOKEN,
    }
    for key, expected in checks.items():
        if str(receipt.get(key) or "") != expected:
            raise RuntimeError(f"CFB_GT_VISUAL_STEP2_POSTMERGE_RECEIPT_DRIFT:{key}")
    if int(receipt.get("github_actions_fallback", -1)) != 0:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_ACTIONS_FALLBACK_DRIFT")
    if receipt.get("all_artifact_blobs_identical") is not True:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_ARTIFACT_REUSE_NOT_PROVEN")
    if receipt.get("all_dependency_blobs_identical") is not True:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_DEPENDENCY_REUSE_NOT_PROVEN")
    if receipt.get("artifact_map") != ARTIFACT_MAP:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_ARTIFACT_MAP_DRIFT")
    if receipt.get("dependency_map") != DEPENDENCY_MAP:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_DEPENDENCY_MAP_DRIFT")
    if str(receipt.get("premerge_runless_proof_id") or "") != PREMERGE_PROOF_ID:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_PREMERGE_PROOF_ID_DRIFT")
    if str(receipt.get("premerge_runless_receipt_digest") or "") != PREMERGE_DIGEST:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_PREMERGE_DIGEST_DRIFT")
    return receipt


def _load_postmerge_receipt(client) -> dict:
    return validate_postmerge_receipt(
        _decode_json(client.content(POSTMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH), "CFB_GT_VISUAL_STEP2_POSTMERGE_RECEIPT")
    )


def _validate_premerge_gate(client) -> dict:
    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + PREMERGE_DIGEST
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            int(run.get("id") or 0) == PREMERGE_CHECK_ID
            and str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("name") or "") == "runless-final-gate"
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
            and str(output.get("summary") or "") == expected_summary
        ):
            return {"id": PREMERGE_CHECK_ID, "app_id": CHECK_APP_ID, "receipt_digest": PREMERGE_DIGEST}
    raise RuntimeError("CFB_GT_VISUAL_STEP2_PREMERGE_GATE_DRIFT")


def _validate_merge_and_content(client) -> dict:
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        not pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != SOURCE_MAIN_SHA
        or str(pr.get("merge_commit_sha") or "") != MAIN_SHA
    ):
        raise RuntimeError("CFB_GT_VISUAL_STEP2_MERGE_PROVENANCE_DRIFT")
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    main_tree = client.tree_blobs(MAIN_SHA)
    for label, mapping in (("ARTIFACT", ARTIFACT_MAP), ("DEPENDENCY", DEPENDENCY_MAP)):
        for path, blob in mapping.items():
            if str(candidate_tree.get(path) or "") != blob or str(main_tree.get(path) or "") != blob:
                raise RuntimeError(f"CFB_GT_VISUAL_STEP2_{label}_IDENTITY_DRIFT:{path}")
    return {"artifact_count": len(ARTIFACT_MAP), "dependency_count": len(DEPENDENCY_MAP)}


def _merged_gate(client) -> dict | None:
    runs = client.request(
        "GET",
        f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + POSTMERGE_DIGEST
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            str(run.get("head_sha") or "") == MAIN_SHA
            and str(run.get("name") or "") == "runless-final-gate"
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
            and str(output.get("summary") or "") == expected_summary
        ):
            return {
                "id": int(run.get("id") or 0),
                "app_id": CHECK_APP_ID,
                "receipt_digest": POSTMERGE_DIGEST,
                "reused": True,
            }
    return None


def _publish_or_reuse_merged_gate(client) -> dict:
    existing = _merged_gate(client)
    if existing is not None:
        return existing
    client.publish_check(
        MAIN_SHA,
        "runless-final-gate",
        "success",
        {
            "title": "Runless Proof Plane",
            "summary": "receipt=" + POSTMERGE_DIGEST,
        },
    )
    published = _merged_gate(client)
    if published is None:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_MERGED_GATE_READBACK_FAILED")
    published["reused"] = False
    return published


def _validate_finalizer_lease(client) -> dict:
    from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

    state = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "CFB_GT_VISUAL_STEP2_LEASE")
    )
    now = datetime.now(timezone.utc)
    holder = next(
        (
            item
            for item in state.get("holders", [])
            if item.get("lease_id") == FINALIZER_LEASE_ID
            and item.get("owner_id") == FINALIZER_OWNER
            and now < _utc(item["expires_at_utc"])
        ),
        None,
    )
    if holder is None:
        raise RuntimeError("CFB_GT_VISUAL_STEP2_FINALIZER_LEASE_NOT_LIVE")
    scope = holder.get("scope") or {}
    required_paths = {REGISTRY_PATH, "devsystem/runless_proof_receipts"}
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("CFB_GT_VISUAL_STEP2_FINALIZER_SCOPE_DRIFT")
    identity = scope.get("resource_identity") or {}
    if (
        str(identity.get("main_sha") or "") != MAIN_SHA
        or str(identity.get("registry_state_hash") or "") != EXPECTED_REGISTRY_HASH
        or str(identity.get("workstream") or "") != WORKSTREAM
    ):
        raise RuntimeError("CFB_GT_VISUAL_STEP2_FINALIZER_IDENTITY_DRIFT")
    return holder


def _freeze_and_readback(client) -> dict:
    from devsystem.frozen_artifact_registry_v1 import _hash as frozen_hash
    from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry

    _validate_finalizer_lease(client)
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = _decode_json(raw, "CFB_GT_VISUAL_STEP2_REGISTRY")
    validate_registry(current)
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is None:
        if (
            int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
            or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH
            or str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA
        ):
            raise RuntimeError("CFB_GT_VISUAL_STEP2_REGISTRY_BASELINE_DRIFT")
        thaw_ids = tuple(sorted(str(item.get("thaw_id") or "") for item in current.get("active_thaws", [])))
        if thaw_ids != tuple(sorted(EXPECTED_ACTIVE_THAWS)):
            raise RuntimeError("CFB_GT_VISUAL_STEP2_ACTIVE_THAW_SET_DRIFT")
        thaw_paths = {
            path
            for grant in current.get("active_thaws", [])
            for path in (grant.get("files") or {})
        }
        overlap = sorted(set(ARTIFACT_MAP) & thaw_paths)
        if overlap:
            raise RuntimeError("CFB_GT_VISUAL_STEP2_ACTIVE_THAW_CONFLICT:" + ",".join(overlap))
        flattened: dict[str, str] = {}
        for entry in (current.get("entries") or {}).values():
            flattened.update(entry.get("artifacts") or {})
        conflicts = sorted(
            path for path, blob in ARTIFACT_MAP.items()
            if path in flattened and str(flattened[path]) != blob
        )
        if conflicts:
            raise RuntimeError("CFB_GT_VISUAL_STEP2_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))
        updated = deepcopy(current)
        updated["revision"] = EXPECTED_REGISTRY_REVISION + 1
        updated["source_main_sha"] = MAIN_SHA
        updated["entries"][FREEZE_TOKEN] = {
            "status": "FROZEN",
            "checkpoint_id": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "artifacts": dict(sorted(ARTIFACT_MAP.items())),
        }
        updated["active_thaws"] = deepcopy(current.get("active_thaws") or [])
        updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
        validate_registry(updated)
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            REGISTRY_BRANCH,
            "registry: freeze CFB Game Total visual cleanup Step2 top shell",
            raw["sha"],
        )
    readback = _decode_json(
        client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH),
        "CFB_GT_VISUAL_STEP2_REGISTRY_READBACK",
    )
    validate_registry(readback)
    frozen = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    thaw_ids = tuple(sorted(str(item.get("thaw_id") or "") for item in readback.get("active_thaws", [])))
    if (
        not frozen
        or frozen.get("status") != "FROZEN"
        or frozen.get("checkpoint_id") != FREEZE_TOKEN
        or frozen.get("source_main_sha") != MAIN_SHA
        or frozen.get("artifacts") != dict(sorted(ARTIFACT_MAP.items()))
        or thaw_ids != tuple(sorted(EXPECTED_ACTIVE_THAWS))
    ):
        raise RuntimeError("CFB_GT_VISUAL_STEP2_REGISTRY_READBACK_MISMATCH")
    return {
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws") or []),
        "artifact_count": len(frozen.get("artifacts") or {}),
    }


def should_run(client) -> bool:
    try:
        _validate_finalizer_lease(client)
        return client.branch_sha("main") == MAIN_SHA
    except Exception:
        return False


def execute(app) -> dict:
    client = app.state.github_client
    receipt = _load_postmerge_receipt(client)
    premerge_gate = _validate_premerge_gate(client)
    content = _validate_merge_and_content(client)
    merged_gate = _publish_or_reuse_merged_gate(client)
    freeze = _freeze_and_readback(client)
    return {
        "status": "GREEN",
        "decision": "CFB_GT_VISUAL_STEP2_GREEN_FROZEN",
        "step": STEP,
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "pr_number": PR_NUMBER,
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "postmerge_proof_id": POSTMERGE_PROOF_ID,
        "postmerge_receipt_digest": receipt["digest"],
        "premerge_gate": premerge_gate,
        "merged_gate": merged_gate,
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": freeze["registry_revision"],
        "registry_state_hash": freeze["registry_state_hash"],
        "frozen_artifact_count": freeze["artifact_count"],
        "active_thaw_count": freeze["active_thaw_count"],
        "content_identity": content,
        "static_evidence_reexecuted": False,
        "product_runtime_mutations": 0,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step2_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step2_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step2_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP2_FINAL_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step2_closeout, sort_keys=True),
            flush=True,
        )

    return app
