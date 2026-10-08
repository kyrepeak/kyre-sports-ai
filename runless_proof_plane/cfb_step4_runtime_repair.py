from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_state,
)

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PREDICTION_MARKET_FROZEN"
THAW_ID = "THAW-CFB-GAME-TOTAL-PAGE1-V2-STEP4-RUNTIME-REPAIR-R1"
OWNER_ID = "api2-cfb-game-total-page1-v2-step4-runtime-repair"
TARGET_HEAD = "861d732878b5478364e5fc680a81ed165a08b944"
BASE_MAIN = "091226472ad03d11d86fa2843fc37c3dc2830023"
RUNLESS_APP_ID = 5204253
AUTHORIZATION_ID = "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-RUNTIME-REPAIR-R1"
TASK_ID = "cfb-game-total-page1-v2-step4-prediction-market"
WORKSTREAM = "cfb-game-total-page1-v2"

THAW_FILES = {
    "cfb_game_total_page1_v2_step4_activation.py": {
        "from_blob": "9fc633200a38a7f0c560696f9a57cb2c0ed09c0f",
        "to_blob": "4b347939afe92feea0365068265ecf8887da0360",
    },
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json": {
        "from_blob": "35999cee728a22394c869622651e884effbb58b5",
        "to_blob": "7b4e473dc700cbcee8f6fab08ade6c61db88dabe",
    },
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json": {
        "from_blob": "a454afcbb0e77084c4d9628d3ba74dc8201a98b3",
        "to_blob": "8de9a5c0a2d2865db08a3f4b3354a741c8020a81",
    },
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json": {
        "from_blob": "62caa31ab79084df184896813dde4726bda04325",
        "to_blob": "f52d1977494a822e923bfe6053e120e6447c1675",
    },
}

ARTIFACT_PATHS = (
    "cfb_game_total_page1_step4_prediction_market_v1.py",
    "cfb_game_total_page1_step4_side_market_v1.py",
    "cfb_game_total_clean_page_v37.py",
    "cfb_game_total_clean_page_v38.py",
    "cfb_game_total_page1_v2_step4_activation.py",
    "kyre_universal_components_v1.py",
    "tests/test_cfb_game_total_page1_v2_step4_prediction_market.py",
    "tests/test_cfb_game_total_page1_v2_step4_runtime_repair.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json",
)
WRITE_PATHS = (
    "cfb_game_total_clean_page_v38.py",
    "cfb_game_total_page1_v2_step4_activation.py",
    "tests/test_cfb_game_total_page1_v2_step4_runtime_repair.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json",
)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _decode(raw: Mapping[str, Any] | None, error: str) -> dict[str, Any]:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(error)
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError(error) from exc


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    payload = _decode(raw, "CFB_STEP4_REPAIR_REGISTRY_READ_FAILED")
    validate_registry(payload)
    return payload, str(raw["sha"])


def _read_lease_state(client):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    payload = validate_scope_state(_decode(raw, "CFB_STEP4_REPAIR_LEASE_READ_FAILED"))
    return payload, str(raw["sha"])


def _candidate_tree(client) -> dict[str, str]:
    tree = client.tree_blobs(TARGET_HEAD)
    for path, pair in THAW_FILES.items():
        if tree.get(path) != pair["to_blob"]:
            raise RuntimeError("CFB_STEP4_REPAIR_CANDIDATE_BLOB_DRIFT:" + path)
    for path in ARTIFACT_PATHS:
        if path not in tree:
            raise RuntimeError("CFB_STEP4_REPAIR_ARTIFACT_MISSING:" + path)
    return tree


def ensure_exact_thaw(client) -> dict[str, Any]:
    if client.branch_sha("main") != BASE_MAIN:
        raise RuntimeError("CFB_STEP4_REPAIR_MAIN_DRIFT")
    _candidate_tree(client)
    current, blob_sha = _read_registry(client)
    entry = (current.get("entries") or {}).get(FREEZE_TOKEN) or {}
    if entry.get("status") != "FROZEN" or entry.get("source_main_sha") != BASE_MAIN:
        raise RuntimeError("CFB_STEP4_REPAIR_FROZEN_BASELINE_DRIFT")
    frozen = entry.get("artifacts") or {}
    for path, pair in THAW_FILES.items():
        if frozen.get(path) != pair["from_blob"]:
            raise RuntimeError("CFB_STEP4_REPAIR_FROM_BLOB_DRIFT:" + path)

    exact = None
    thaw_paths = set(THAW_FILES)
    for grant in current.get("active_thaws", []):
        files = set((grant.get("files") or {}).keys())
        if str(grant.get("thaw_id")) == THAW_ID:
            exact = grant
            continue
        if thaw_paths & files:
            raise RuntimeError("CFB_STEP4_REPAIR_CONFLICTING_THAW:" + str(grant.get("thaw_id")))
    expected_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": TARGET_HEAD,
        "files": deepcopy(THAW_FILES),
    }
    if exact is not None:
        if exact != expected_grant:
            raise RuntimeError("CFB_STEP4_REPAIR_THAW_ID_CONFLICT")
        return {"status": "GREEN", "idempotent": True, "thaw_id": THAW_ID,
                "revision": int(current["revision"]), "state_hash": str(current["state_hash"])}

    updated = deepcopy(current)
    updated["revision"] = int(current["revision"]) + 1
    updated["active_thaws"] = deepcopy(current.get("active_thaws", [])) + [expected_grant]
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(REGISTRY_PATH, text, REGISTRY_BRANCH, f"registry: authorize {THAW_ID}", blob_sha)
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc
    readback, _ = _read_registry(client)
    matches = [g for g in readback.get("active_thaws", []) if str(g.get("thaw_id")) == THAW_ID]
    if len(matches) != 1 or matches[0] != expected_grant:
        raise RuntimeError("CFB_STEP4_REPAIR_THAW_READBACK_MISMATCH")
    return {"status": "GREEN", "idempotent": False, "thaw_id": THAW_ID,
            "revision": int(readback["revision"]), "state_hash": str(readback["state_hash"])}


def ensure_scope_lease(client, ttl_seconds: int = 3600) -> dict[str, Any]:
    state, content_sha = _read_lease_state(client)
    now = datetime.now(timezone.utc)
    for holder in state.get("holders", []):
        expires = datetime.fromisoformat(str(holder["expires_at_utc"]).replace("Z", "+00:00"))
        identity = (holder.get("scope") or {}).get("resource_identity") or {}
        if holder.get("owner_id") == OWNER_ID and expires > now and identity.get("candidate") == TARGET_HEAD:
            return {"status": "GREEN", "idempotent": True, "lease_id": str(holder["lease_id"]),
                    "revision": int(state["revision"]), "state_hash": str(state["state_hash"])}
    scope = build_scope(
        write_paths=WRITE_PATHS,
        shared_resources=("cfb-game-total-page1-v2",),
        resource_identity={"candidate": TARGET_HEAD, "main": BASE_MAIN, "repair": "step4-runtime-r1"},
        exclusive=False,
    )
    outcome = claim_scope(
        state,
        owner_id=OWNER_ID,
        now_utc=now.isoformat().replace("+00:00", "Z"),
        scope=scope,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
        ttl_seconds=ttl_seconds,
        frozen_paths=tuple(THAW_FILES),
        thawed_paths=tuple(THAW_FILES),
    )
    result = outcome["result"]
    if result.get("allowed") is not True:
        raise RuntimeError("CFB_STEP4_REPAIR_SCOPE_BLOCKED:" + str(result.get("decision")))
    updated = outcome["state"]
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(LEASE_PATH, text, LEASE_BRANCH, "lease: claim CFB Step4 runtime repair", content_sha)
    except Exception as exc:
        raise RuntimeError("WAIT_SCOPE_LEASE_RECONCILIATION") from exc
    readback, _ = _read_lease_state(client)
    lease_id = str(result["lease_id"])
    matches = [h for h in readback.get("holders", []) if h.get("lease_id") == lease_id and h.get("owner_id") == OWNER_ID]
    if len(matches) != 1:
        raise RuntimeError("CFB_STEP4_REPAIR_LEASE_READBACK_MISMATCH")
    return {"status": "GREEN", "idempotent": False, "lease_id": lease_id,
            "revision": int(readback["revision"]), "state_hash": str(readback["state_hash"])}


def prepare_and_prove(client, *, settings, orchestrator, receipts) -> dict[str, Any]:
    thaw = ensure_exact_thaw(client)
    lease = ensure_scope_lease(client)
    from .models import ProofRequest
    from .prove import execute_proof_request
    request = ProofRequest(
        task_id=TASK_ID, workstream=WORKSTREAM, candidate_sha=TARGET_HEAD,
        lease_id=lease["lease_id"], authorization_id=AUTHORIZATION_ID,
        expected_main_sha=BASE_MAIN,
    )
    proof = execute_proof_request(request, settings=settings, github_client=client,
                                  orchestrator=orchestrator, receipts=receipts)
    if proof.get("status") != "MERGE_AUTHORIZED" and proof.get("state") != "MERGE_AUTHORIZED":
        raise RuntimeError("CFB_STEP4_REPAIR_RUNLESS_NOT_AUTHORIZED:" + str(proof.get("status") or proof.get("state")))
    return {"status": "GREEN", "phase": "PREPARED_AND_PROVEN", "candidate_sha": TARGET_HEAD,
            "thaw": thaw, "lease": lease, "proof": proof, "github_actions_fallback": 0}


def _require_candidate_gate(client) -> dict[str, Any]:
    checks = client.request("GET", f"/commits/{TARGET_HEAD}/check-runs") or {}
    matches = []
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        if (check.get("name") == "runless-final-gate" and check.get("head_sha") == TARGET_HEAD
                and check.get("status") == "completed" and check.get("conclusion") == "success"
                and int(app.get("id") or 0) == RUNLESS_APP_ID):
            matches.append(check)
    if len(matches) != 1:
        raise RuntimeError("CFB_STEP4_REPAIR_CANDIDATE_RUNLESS_GREEN_REQUIRED")
    summary = str(((matches[0].get("output") or {}).get("summary") or ""))
    receipt = summary.removeprefix("receipt=").strip()
    if len(receipt) != 64:
        raise RuntimeError("CFB_STEP4_REPAIR_CANDIDATE_RECEIPT_REQUIRED")
    return {"check_id": int(matches[0]["id"]), "receipt": receipt}


def _publish_merged_tree_reuse_gate(client, merged_sha: str, receipt: str) -> int:
    existing = client.request("GET", f"/commits/{merged_sha}/check-runs") or {}
    for check in existing.get("check_runs", []):
        app = check.get("app") or {}
        if (check.get("name") == "runless-final-gate" and check.get("head_sha") == merged_sha
                and check.get("status") == "completed" and check.get("conclusion") == "success"
                and int(app.get("id") or 0) == RUNLESS_APP_ID):
            return int(check["id"])
    created = client.publish_check(
        merged_sha, "runless-final-gate", "success",
        {"title": "Runless Proof Plane • exact-tree post-merge reuse", "summary": f"receipt={receipt}"},
    )
    return int(created["id"])


def _release_target_lease(client) -> dict[str, Any]:
    state, content_sha = _read_lease_state(client)
    matches = [h for h in state.get("holders", []) if h.get("owner_id") == OWNER_ID]
    if not matches:
        return {"status": "GREEN", "idempotent": True, "released": True}
    if len(matches) != 1:
        raise RuntimeError("CFB_STEP4_REPAIR_LEASE_DUPLICATED")
    lease_id = str(matches[0]["lease_id"])
    outcome = release_scope(state, owner_id=OWNER_ID, lease_id=lease_id,
                            expected_revision=int(state["revision"]), expected_state_hash=str(state["state_hash"]))
    result = outcome["result"]
    if result.get("allowed") is not True:
        raise RuntimeError("CFB_STEP4_REPAIR_LEASE_RELEASE_BLOCKED:" + str(result.get("decision")))
    updated = outcome["state"]
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(LEASE_PATH, text, LEASE_BRANCH, "lease: release CFB Step4 runtime repair", content_sha)
    except Exception as exc:
        raise RuntimeError("WAIT_SCOPE_LEASE_RELEASE_RECONCILIATION") from exc
    readback, _ = _read_lease_state(client)
    if any(h.get("owner_id") == OWNER_ID for h in readback.get("holders", [])):
        raise RuntimeError("CFB_STEP4_REPAIR_LEASE_RELEASE_READBACK_MISMATCH")
    return {"status": "GREEN", "idempotent": False, "released": True, "lease_id": lease_id}


def finalize_freeze(client, merged_sha: str) -> dict[str, Any]:
    merged_sha = str(merged_sha or "").strip().lower()
    if len(merged_sha) != 40:
        raise RuntimeError("CFB_STEP4_REPAIR_MERGED_SHA_REQUIRED")
    if client.branch_sha("main") != merged_sha:
        raise RuntimeError("CFB_STEP4_REPAIR_MAIN_SHA_DRIFT")
    candidate_commit = client.commit(TARGET_HEAD)
    merged_commit = client.commit(merged_sha)
    candidate_tree_sha = str(((candidate_commit.get("commit") or {}).get("tree") or {}).get("sha") or "")
    merged_tree_sha = str(((merged_commit.get("commit") or {}).get("tree") or {}).get("sha") or "")
    if not candidate_tree_sha or candidate_tree_sha != merged_tree_sha:
        raise RuntimeError("CFB_STEP4_REPAIR_POSTMERGE_TREE_DRIFT")
    runless = _require_candidate_gate(client)
    merged_gate_id = _publish_merged_tree_reuse_gate(client, merged_sha, runless["receipt"])
    tree = client.tree_blobs(merged_sha)
    missing = [path for path in ARTIFACT_PATHS if path not in tree]
    if missing:
        raise RuntimeError("CFB_STEP4_REPAIR_FREEZE_ARTIFACTS_MISSING:" + ",".join(missing))
    artifacts = dict(sorted((path, tree[path]) for path in ARTIFACT_PATHS))

    current, content_sha = _read_registry(client)
    entry = (current.get("entries") or {}).get(FREEZE_TOKEN)
    grants = current.get("active_thaws", [])
    target_grants = [g for g in grants if str(g.get("thaw_id")) == THAW_ID]
    unrelated = [deepcopy(g) for g in grants if str(g.get("thaw_id")) != THAW_ID]
    already_exact = (isinstance(entry, Mapping) and entry.get("status") == "FROZEN"
                     and entry.get("checkpoint_id") == FREEZE_TOKEN and entry.get("source_main_sha") == merged_sha
                     and entry.get("artifacts") == artifacts and not target_grants)
    if not already_exact:
        if len(target_grants) != 1:
            raise RuntimeError("CFB_STEP4_REPAIR_EXACT_THAW_REQUIRED")
        expected_grant = {"thaw_id": THAW_ID, "status": "ACTIVE", "target_head_sha": TARGET_HEAD,
                          "files": deepcopy(THAW_FILES)}
        if target_grants[0] != expected_grant:
            raise RuntimeError("CFB_STEP4_REPAIR_THAW_DRIFT")
        updated = deepcopy(current)
        updated["entries"][FREEZE_TOKEN] = {"status": "FROZEN", "checkpoint_id": FREEZE_TOKEN,
                                                   "source_main_sha": merged_sha, "artifacts": artifacts}
        updated["active_thaws"] = unrelated
        updated["revision"] = int(current["revision"]) + 1
        updated["source_main_sha"] = merged_sha
        updated["state_hash"] = _state_hash(updated)
        validate_registry(updated)
        text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        try:
            client.update_content(REGISTRY_PATH, text, REGISTRY_BRANCH,
                                  f"registry: refreeze {FREEZE_TOKEN} after runtime repair", content_sha)
        except Exception as exc:
            raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc
        readback, _ = _read_registry(client)
    else:
        readback = current

    frozen = (readback.get("entries") or {}).get(FREEZE_TOKEN) or {}
    if (frozen.get("status") != "FROZEN" or frozen.get("source_main_sha") != merged_sha
            or frozen.get("artifacts") != artifacts
            or any(str(g.get("thaw_id")) == THAW_ID for g in readback.get("active_thaws", []))):
        raise RuntimeError("CFB_STEP4_REPAIR_FREEZE_READBACK_MISMATCH")
    release = _release_target_lease(client)
    return {"status": "GREEN_FROZEN", "phase": "FINALIZED", "candidate_sha": TARGET_HEAD,
            "merged_sha": merged_sha, "candidate_tree_sha": candidate_tree_sha, "merged_tree_sha": merged_tree_sha,
            "runless_candidate_check_id": runless["check_id"], "runless_receipt": runless["receipt"],
            "merged_runless_check_id": merged_gate_id, "freeze_token": FREEZE_TOKEN,
            "registry_revision": int(readback["revision"]), "registry_state_hash": str(readback["state_hash"]),
            "artifact_count": len(artifacts), "lease_release": release, "github_actions_fallback": 0}
