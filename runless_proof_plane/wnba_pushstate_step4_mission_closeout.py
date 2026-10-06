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
RUNLESS_APP_ID = 5204253
STEP3_MAIN_CHECK_ID = 112548903890
STEP3_MAIN_RECEIPT = "b4a95f0f286fc010fc5b8f86225bb3b3314086d5bf7c1cde5ff5f0875dc11814"
PUBLIC_PROOF_DEPLOY = "dep-db2nvdui0phs738muphg"
PUBLIC_PROOF_HEAD = "dd218685476b48fc64baf73b819cdd6494063c16"
PUBLIC_PROOF_DATE = "2026-10-07"

PRIOR_STEPS = {
    "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN": "896bd5f78ef6b6f7d7084413cc1e35ac6489fdc2",
    "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN": "897f0ce90b5105477592a92279a9055ef27afbf8",
    "WNBA_PUSHSTATE_REPAIR_V1_STEP3_FROZEN": MAIN_SHA,
}
FREEZE_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP4_FROZEN"
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
        raise RuntimeError("WNBA_PUSHSTATE_STEP4_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_step3_main_gate(client) -> dict[str, Any]:
    checks = client.request("GET", f"/commits/{MAIN_SHA}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            int(check.get("id") or 0) == STEP3_MAIN_CHECK_ID
            and check.get("name") == "runless-final-gate"
            and check.get("head_sha") == MAIN_SHA
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={STEP3_MAIN_RECEIPT}"
        ):
            return {
                "check_id": STEP3_MAIN_CHECK_ID,
                "receipt": STEP3_MAIN_RECEIPT,
            }
    raise RuntimeError("WNBA_PUSHSTATE_STEP4_STEP3_MAIN_GATE_MISSING")


def _collect_frozen_mission(client, registry: Mapping[str, Any]) -> dict[str, str]:
    if str(client.branch_sha("main")).lower() != MAIN_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP4_MAIN_SHA_DRIFT")

    entries = registry.get("entries") or {}
    mission_artifacts: dict[str, str] = {}
    for token, expected_source in PRIOR_STEPS.items():
        entry = entries.get(token)
        if not isinstance(entry, Mapping):
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_PRIOR_FREEZE_MISSING:" + token)
        if str(entry.get("status") or "") != "FROZEN":
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_PRIOR_NOT_FROZEN:" + token)
        if str(entry.get("checkpoint_id") or "") != token:
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_PRIOR_CHECKPOINT_DRIFT:" + token)
        if str(entry.get("source_main_sha") or "").lower() != expected_source:
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_PRIOR_SOURCE_DRIFT:" + token)
        artifacts = entry.get("artifacts") or {}
        if not isinstance(artifacts, Mapping) or not artifacts:
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_PRIOR_ARTIFACTS_MISSING:" + token)
        for raw_path, raw_blob in artifacts.items():
            path = str(raw_path)
            blob = str(raw_blob).lower()
            prior = mission_artifacts.get(path)
            if prior is not None and prior != blob:
                raise RuntimeError("WNBA_PUSHSTATE_STEP4_FROZEN_CONFLICT:" + path)
            mission_artifacts[path] = blob

    tree = client.tree_blobs(MAIN_SHA)
    for path, blob in mission_artifacts.items():
        if str(tree.get(path) or "").lower() != blob:
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_MAIN_ARTIFACT_DRIFT:" + path)

    for grant in registry.get("active_thaws") or []:
        overlap = sorted(set(grant.get("files") or {}) & set(mission_artifacts))
        if overlap:
            raise RuntimeError(
                "WNBA_PUSHSTATE_STEP4_ACTIVE_THAW_OVERLAP:"
                + str(grant.get("thaw_id") or "")
                + ":"
                + ",".join(overlap)
            )
    return dict(sorted(mission_artifacts.items()))


def _publish_final_gate(client, *, artifacts: Mapping[str, str], registry: Mapping[str, Any]) -> tuple[int, str]:
    step3_gate = _require_step3_main_gate(client)
    evidence = {
        "main_sha": MAIN_SHA,
        "prior_freeze_tokens": sorted(PRIOR_STEPS),
        "artifact_count": len(artifacts),
        "step3_main_gate": step3_gate,
        "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
        "public_proof_head": PUBLIC_PROOF_HEAD,
        "public_future_date": PUBLIC_PROOF_DATE,
        "public_chain": [
            "SLATE_GREEN",
            "GAME_CENTER_GREEN",
            "PLAYER_PRA_GREEN",
            "PLAYER_BACK_GAME_GREEN",
            "GAME_BACK_SLATE_GREEN",
            "NO_PUSHSTATE_ERROR_GREEN",
            "NO_PAST_GAMES_GREEN",
        ],
        "product_runtime_mutation_by_step4": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step4-mission-{MAIN_SHA[:16]}",
        task_id="wnba-pushstate-repair-v1-step4-final-mission-closeout",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step4",
        step="4/4-final-production-certification",
        candidate_sha=MAIN_SHA,
        artifact_map=dict(artifacts),
        dependency_map={
            "step1_freeze": "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN",
            "step2_freeze": "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN",
            "step3_freeze": "WNBA_PUSHSTATE_REPAIR_V1_STEP3_FROZEN",
            "step3_main_check_id": STEP3_MAIN_CHECK_ID,
            "step3_main_receipt": STEP3_MAIN_RECEIPT,
            "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
            "public_proof_head": PUBLIC_PROOF_HEAD,
            "public_future_date": PUBLIC_PROOF_DATE,
            "proof_authority": "Runless Proof Plane + frozen Step-3 terminal public Playwright proof",
        },
        registry_before={
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "source_main_sha": str(registry["source_main_sha"]),
        },
        registry_after={
            "freeze_token": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "mode": "mission-final-freeze",
        },
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, MAIN_SHA, "success", receipt)
    return int(check["id"]), str(receipt["digest"])


def _freeze(client, *, artifacts: Mapping[str, str], check_id: int, receipt_digest: str) -> dict[str, Any]:
    current, content_sha = _read_registry(client)
    current_artifacts = _collect_frozen_mission(client, current)
    if current_artifacts != dict(artifacts):
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")

    desired = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(artifacts),
    }
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if existing != desired:
            raise RuntimeError("WNBA_PUSHSTATE_STEP4_FREEZE_TOKEN_CONFLICT")
        return {
            "status": "GREEN",
            "freeze_token": FREEZE_TOKEN,
            "main_sha": MAIN_SHA,
            "revision": int(current["revision"]),
            "state_hash": str(current["state_hash"]),
            "artifact_count": len(artifacts),
            "runless_check_id": check_id,
            "runless_receipt": receipt_digest,
            "idempotent": True,
        }

    preserved_thaws = deepcopy(list(current.get("active_thaws") or []))
    updated = deepcopy(current)
    updated.setdefault("entries", {})[FREEZE_TOKEN] = desired
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
    entry = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    if entry != desired:
        raise RuntimeError("WNBA_PUSHSTATE_STEP4_FREEZE_READBACK_MISMATCH")
    if list(readback.get("active_thaws") or []) != preserved_thaws:
        raise RuntimeError("WNBA_PUSHSTATE_STEP4_UNRELATED_THAW_DRIFT")
    if int(readback.get("revision") or -1) != int(current["revision"]) + 1:
        raise RuntimeError("WNBA_PUSHSTATE_STEP4_REGISTRY_REVISION_READBACK_FAILED")
    if str(readback.get("source_main_sha") or "").lower() != MAIN_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP4_REGISTRY_SOURCE_READBACK_FAILED")
    validate_registry(readback)

    return {
        "status": "GREEN",
        "freeze_token": FREEZE_TOKEN,
        "main_sha": MAIN_SHA,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(artifacts),
        "runless_check_id": check_id,
        "runless_receipt": receipt_digest,
        "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
        "idempotent": False,
    }


def closeout_step4(client) -> dict[str, Any]:
    registry, _ = _read_registry(client)
    artifacts = _collect_frozen_mission(client, registry)
    check_id, receipt_digest = _publish_final_gate(client, artifacts=artifacts, registry=registry)
    return _freeze(client, artifacts=artifacts, check_id=check_id, receipt_digest=receipt_digest)


def install_startup_closeout(app):
    app.state.wnba_pushstate_step4_mission_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _closeout_wnba_pushstate_step4():
        try:
            app.state.wnba_pushstate_step4_mission_closeout = closeout_step4(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step4_mission_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
