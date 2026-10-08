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

TASK_ID = "nfl-rb-wr-render-repair-step3-data-binding"
WORKSTREAM = "nfl-rb-wr-render-repair-v1"
CANDIDATE_SHA = "5edcacdc3beb73003cec2bfafb884097d039241f"
MERGED_MAIN_SHA = "7854d5772333482947f9f2d4bda71cf73ded72b5"
PR_NUMBER = 1474
PROOF_ID = "nfl-rb-wr-render-repair-step3-data-binding-5edcacdc3beb7300-577e7269d23adc7f"
PROOF_DIGEST = "2257d03dc8ffbe2dc15289f6ff9ab7cd2abd2e4ce6dd85f0cf83a6e37aeb112a"
CHECK_ID = 113564472530
CHECK_APP_ID = 5204253

FREEZE_TOKEN = "NFL_RB_WR_RENDER_REPAIR_V1_STEP3_DATA_BINDING_FROZEN"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 208
EXPECTED_REGISTRY_HASH = "0a2262dec2bfd10d5b5a37821ec8c70f10e419830336965e58fa8275992c0885"

RECEIPT_BRANCH = "runless-proof-receipts"
RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PROOF_ID}.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
PRODUCT_LEASE_ID = "SCOPE-LEASE-NFL-RB-WR-STEP3-217"
FINALIZER_LEASE_ID = "SCOPE-LEASE-06F5FF2E2D7158C6570BD9B0"
FINALIZER_OWNER = "api2-nfl-rb-wr-render-repair-step3-finalizer"

ARTIFACT_MAP = {
    "devsystem/execution_plans/nfl-rb-wr-render-repair-step3-data-binding.json": "7628dbf3c0c470a302e0732e514d1031f25cfd72",
    "devsystem/nfl_rb_wr_render_repair_step3_data_binding_v1.py": "916df46771ff75fba4a0edc6f90468a45e5cea49",
    "devsystem/runless_proof_plans/nfl-rb-wr-render-repair-step3-data-binding.json": "fe13395b6cfcfca2e59af6861d19f19db3952f66",
    "devsystem/task_ledgers/nfl-rb-wr-render-repair-step3-data-binding.json": "1adaa1809a06377147ddaede655370e895b0bb60",
    "tests/test_nfl_rb_wr_render_repair_step3_data_binding.py": "4a6f19dba4c9587dbfdbccc23fda902016efcabf",
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


def _finalizer_holder(client) -> dict | None:
    state = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "NFL_RB_WR_STEP3_LEASE")
    )
    now = datetime.now(timezone.utc)
    return next(
        (
            holder
            for holder in state.get("holders", [])
            if holder.get("lease_id") == FINALIZER_LEASE_ID
            and holder.get("owner_id") == FINALIZER_OWNER
            and now < _utc(holder["expires_at_utc"])
        ),
        None,
    )


def should_run(client) -> bool:
    try:
        return _finalizer_holder(client) is not None
    except Exception:
        return False


def _validate_authority(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "NFL_RB_WR_STEP3_LEASE"))
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
        raise RuntimeError("NFL_RB_WR_STEP3_FINALIZER_LEASE_NOT_LIVE")
    product = next(
        (item for item in state.get("holders", []) if item.get("lease_id") == PRODUCT_LEASE_ID),
        None,
    )
    if product is None:
        raise RuntimeError("NFL_RB_WR_STEP3_PRODUCT_LEASE_MISSING")

    scope = holder.get("scope") or {}
    identity = scope.get("resource_identity") or {}
    expected_identity = {
        "candidate_sha": CANDIDATE_SHA,
        "merged_main_sha": MERGED_MAIN_SHA,
        "proof_digest": PROOF_DIGEST,
        "registry_revision": str(EXPECTED_REGISTRY_REVISION),
        "registry_state_hash": EXPECTED_REGISTRY_HASH,
    }
    if any(str(identity.get(k) or "") != v for k, v in expected_identity.items()):
        raise RuntimeError("NFL_RB_WR_STEP3_FINALIZER_IDENTITY_DRIFT")
    required_paths = {
        REGISTRY_PATH,
        LEASE_PATH,
        "runless_proof_plane/bootstrap.py",
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
    }
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("NFL_RB_WR_STEP3_FINALIZER_SCOPE_DRIFT")
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
    raise RuntimeError("NFL_RB_WR_STEP3_RUNLESS_GATE_DRIFT")


def _validate_receipt(client) -> dict:
    receipt = _decode_json(client.content(RECEIPT_PATH, ref=RECEIPT_BRANCH), "NFL_RB_WR_STEP3_RECEIPT")
    if (
        str(receipt.get("proof_id") or "") != PROOF_ID
        or str(receipt.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(receipt.get("digest") or "") != PROOF_DIGEST
        or str(receipt.get("failure_class") or "") != "NONE"
        or receipt.get("artifact_map") != ARTIFACT_MAP
    ):
        raise RuntimeError("NFL_RB_WR_STEP3_RECEIPT_DRIFT")
    return receipt


def _verify_merged_artifacts(client) -> dict[str, str]:
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("NFL_RB_WR_STEP3_MAIN_DRIFT")
    tree = client.tree_blobs(MERGED_MAIN_SHA)
    observed = {path: str(tree.get(path) or "") for path in ARTIFACT_MAP}
    if observed != ARTIFACT_MAP:
        raise RuntimeError("NFL_RB_WR_STEP3_MERGED_ARTIFACT_DRIFT")
    return observed


def _freeze_once(client) -> dict:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = validate_registry(_decode_json(raw, "NFL_RB_WR_STEP3_REGISTRY"))
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if (
            existing.get("status") == "FROZEN"
            and existing.get("checkpoint_id") == FREEZE_TOKEN
            and existing.get("source_main_sha") == MERGED_MAIN_SHA
            and existing.get("artifacts") == ARTIFACT_MAP
        ):
            return {
                "decision": "NFL_RB_WR_STEP3_ALREADY_FROZEN",
                "registry_revision": int(current["revision"]),
                "registry_state_hash": str(current["state_hash"]),
                "artifact_count": len(ARTIFACT_MAP),
            }
        raise RuntimeError("NFL_RB_WR_STEP3_FREEZE_TOKEN_CONFLICT")

    if (
        int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
        or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH
    ):
        raise RuntimeError("NFL_RB_WR_STEP3_REGISTRY_BASELINE_DRIFT")

    thaw_paths = {
        path
        for grant in current.get("active_thaws", [])
        for path in (grant.get("files") or {})
    }
    overlap = sorted(set(ARTIFACT_MAP) & thaw_paths)
    if overlap:
        raise RuntimeError("NFL_RB_WR_STEP3_ACTIVE_THAW_CONFLICT:" + ",".join(overlap))

    flattened: dict[str, str] = {}
    for entry in (current.get("entries") or {}).values():
        flattened.update(entry.get("artifacts") or {})
    conflicts = sorted(
        path for path, blob in ARTIFACT_MAP.items()
        if path in flattened and str(flattened[path]) != blob
    )
    if conflicts:
        raise RuntimeError("NFL_RB_WR_STEP3_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))

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
        "registry: freeze NFL RB WR Step3 data binding",
        raw["sha"],
    )
    return {
        "decision": "NFL_RB_WR_STEP3_FREEZE_SUBMITTED",
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
        "step": "3/5",
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
        "product_runtime_mutations": 0,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.nfl_rb_wr_step3_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.nfl_rb_wr_step3_closeout = execute(app)
        except Exception as exc:
            app.state.nfl_rb_wr_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "NFL_RB_WR_STEP3_FINAL_CLOSEOUT="
            + json.dumps(app.state.nfl_rb_wr_step3_closeout, sort_keys=True),
            flush=True,
        )

    return app
