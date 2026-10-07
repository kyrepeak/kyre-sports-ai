from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "46d3dc27923ec65af7cdce5eb7b548e8b772e51c"
CANDIDATE_SHA = "ecea19ba1f2a64aaf43c1a1973fdacd845624004"
MERGED_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
CANDIDATE_CHECK_ID = 112566439455
CANDIDATE_RECEIPT = "627228c40d1c94fd4d9054eb92b707bfb30b2b38253f1c642884e7b4e75a56c8"
RUNLESS_APP_ID = 5204253
FREEZE_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN"
STEP1_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_FROZEN"
PUSHSTATE_FINAL_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP4_FROZEN"
EXPECTED_REGISTRY_REVISION = 148
EXPECTED_REGISTRY_HASH = "d7ffd0dbb09a959d792001b26bf56b4c22020f18879e46cb22ed59b207e5eef2"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")

ARTIFACT_PATHS = tuple(sorted((
    "wnba_players_v25.py",
    "wnba_data_completeness_repair_v1_step2_stats_gate.py",
    "tests/test_wnba_data_completeness_repair_v1_step2.py",
    "devsystem/wnba_data_completeness_repair_v1_step2_player_game_stats_cert.py",
    "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-player-game-stats.json",
    "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-player-game-stats.json",
)))


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
        raise RuntimeError("WNBA_DATA_STEP2_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_candidate_gate(client) -> None:
    checks = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            int(check.get("id") or 0) == CANDIDATE_CHECK_ID
            and check.get("name") == "runless-final-gate"
            and check.get("head_sha") == CANDIDATE_SHA
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={CANDIDATE_RECEIPT}"
        ):
            return
    raise RuntimeError("WNBA_DATA_STEP2_CANDIDATE_GATE_MISSING")


def _verify_merged_identity(client):
    if client.branch_sha("main") != MERGED_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_MAIN_SHA_DRIFT")
    commit = client.request("GET", f"/commits/{MERGED_SHA}") or {}
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if BASE_SHA not in parents or CANDIDATE_SHA not in parents:
        raise RuntimeError("WNBA_DATA_STEP2_MERGE_PARENT_DRIFT")
    _require_candidate_gate(client)
    tree = client.tree_blobs(MERGED_SHA)
    artifacts = {path: str(tree.get(path) or "") for path in ARTIFACT_PATHS}
    if any(len(blob) != 40 for blob in artifacts.values()):
        raise RuntimeError("WNBA_DATA_STEP2_MERGED_ARTIFACT_MISSING")
    return artifacts


def _publish_main_gate(client, artifacts):
    evidence = {
        "main_sha": MERGED_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "candidate_check_id": CANDIDATE_CHECK_ID,
        "artifacts": artifacts,
        "root_cause": "partial cross-provider ID overlap deleted valid WNBA production rows",
        "patch": "current-roster production gate matches by exact ID or normalized name and preserves league-guarded production when roster feed is unavailable",
        "other_pages_changed": 0,
        "other_sports_changed": 0,
        "navigation_changed": False,
        "projection_math_changed": False,
        "probability_changed": False,
        "market_changed": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step2-merged-{MERGED_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-player-game-stats",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2",
        step="2/5-merged-main-closeout",
        candidate_sha=MERGED_SHA,
        artifact_map=artifacts,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "candidate_sha": CANDIDATE_SHA,
            "candidate_check_id": CANDIDATE_CHECK_ID,
            "candidate_receipt": CANDIDATE_RECEIPT,
            "github_actions_fallback": False,
        },
        registry_before={"revision": EXPECTED_REGISTRY_REVISION, "state_hash": EXPECTED_REGISTRY_HASH, "step1": STEP1_TOKEN},
        registry_after={"freeze_token": FREEZE_TOKEN, "mode": "pending_atomic_write"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, MERGED_SHA, "success", receipt)
    return int(check["id"]), str(receipt["digest"])


def _freeze_registry(client, artifacts, check_id: int, receipt_digest: str):
    current, content_sha = _read_registry(client)
    desired = {"status": "FROZEN", "checkpoint_id": FREEZE_TOKEN, "source_main_sha": MERGED_SHA, "artifacts": dict(artifacts)}
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if existing != desired:
            raise RuntimeError("WNBA_DATA_STEP2_FREEZE_TOKEN_CONFLICT")
        return {"status": "GREEN", "freeze_token": FREEZE_TOKEN, "revision": int(current["revision"]), "state_hash": str(current["state_hash"]), "runless_check_id": check_id, "runless_receipt": receipt_digest, "idempotent": True}

    if int(current.get("revision") or -1) != EXPECTED_REGISTRY_REVISION or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
    if ((current.get("entries") or {}).get(STEP1_TOKEN) or {}).get("status") != "FROZEN":
        raise RuntimeError("WNBA_DATA_STEP2_STEP1_PROTECTION_MISSING")
    if ((current.get("entries") or {}).get(PUSHSTATE_FINAL_TOKEN) or {}).get("status") != "FROZEN":
        raise RuntimeError("WNBA_DATA_STEP2_PUSHSTATE_PROTECTION_MISSING")

    original_thaws = deepcopy(list(current.get("active_thaws") or []))
    for grant in original_thaws:
        overlap = set((grant.get("files") or {}).keys()) & set(artifacts.keys())
        if overlap:
            raise RuntimeError("WNBA_DATA_STEP2_ACTIVE_THAW_OVERLAP:" + ",".join(sorted(overlap)))
    for token, entry in (current.get("entries") or {}).items():
        for path, blob in (entry.get("artifacts") or {}).items():
            if path in artifacts and str(blob) != artifacts[path]:
                raise RuntimeError("WNBA_DATA_STEP2_FROZEN_ARTIFACT_CONFLICT:" + token + ":" + path)

    updated = deepcopy(current)
    updated.setdefault("entries", {})[FREEZE_TOKEN] = desired
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = MERGED_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(REGISTRY_PATH, json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n", REGISTRY_BRANCH, f"registry: freeze {FREEZE_TOKEN}", content_sha)

    readback, _ = _read_registry(client)
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != desired:
        raise RuntimeError("WNBA_DATA_STEP2_FREEZE_READBACK_MISMATCH")
    if list(readback.get("active_thaws") or []) != original_thaws:
        raise RuntimeError("WNBA_DATA_STEP2_UNRELATED_THAW_DRIFT")
    if int(readback.get("revision") or -1) != EXPECTED_REGISTRY_REVISION + 1:
        raise RuntimeError("WNBA_DATA_STEP2_REVISION_READBACK_FAILED")
    if str(readback.get("source_main_sha") or "") != MERGED_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_SOURCE_SHA_READBACK_FAILED")
    return {"status": "GREEN", "freeze_token": FREEZE_TOKEN, "main_sha": MERGED_SHA, "revision": int(readback["revision"]), "state_hash": str(readback["state_hash"]), "active_thaw_count": len(readback.get("active_thaws", [])), "runless_check_id": check_id, "runless_receipt": receipt_digest, "idempotent": False}


def closeout_step2(client):
    artifacts = _verify_merged_identity(client)
    check_id, receipt_digest = _publish_main_gate(client, artifacts)
    return _freeze_registry(client, artifacts, check_id, receipt_digest)


def install_startup_closeout(app):
    app.state.wnba_data_step2_closeout = {"status": "NOT_RUN"}
    @app.on_event("startup")
    def _closeout():
        try:
            app.state.wnba_data_step2_closeout = closeout_step2(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step2_closeout = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:500]}
    return app
