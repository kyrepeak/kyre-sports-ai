from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_state,
)

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-backend-preservation-step2-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
BRANCH = "cfb-game-total-backend-preservation-step2-v1"
CANDIDATE_SHA = "e44a0e3b15204033c2003302183da168f2e3d120"
MAIN_SHA = "21b6d7a0dad7edd7f6768a3f98a121572fc859fa"
AUTHORIZATION_ID = "AUTH-CFB-GT-BACKEND-PRESERVATION-STEP2-R1"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-backend-preservation-step2"
WRITE_PATHS = (
    "devsystem/cfb_game_total_backend_preservation_step2_v1.py",
    "tests/test_devsystem_cfb_game_total_backend_preservation_step2_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-backend-preservation-step2-v1.json",
    "devsystem/task_ledgers/cfb-game-total-backend-preservation-step2-v1.json",
)
PROTECTED_BACKEND_BLOBS = {
    "cfb_freeze_manifest_v12.json": "3ff2a727967e80dddbe03f747d9f32090cc39539",
    "cfb_game_total_model_v1.py": "88e98c2b78c689e48f81f049cb1a64c0e958e964",
    "cfb_game_total_final_v1.py": "78fbeaeb77e3101cc83c579b15f9cd6d485df952",
    "cfb_game_total_slate_v1.py": "777beb82b1dc3dd7df76f8f4d8d37f87eeb9b872",
    "cfb_game_total_model_input_v1.py": "0d270126b6265ec22c29ea0a73faaf57235f4b8e",
    "cfb_game_total_slate_v2.py": "1acc2859bc1666b968e8ea54fb7fadc905781d81",
    "cfb_game_total_step3_form_v1.py": "ea7bad697064625588ec31971fe642446d2f8b34",
}


class BackendPreservationStep2PremergeFailure(RuntimeError):
    pass


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise BackendPreservationStep2PremergeFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise BackendPreservationStep2PremergeFailure(label + "_DECODE_FAILED") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _verify_heads(client) -> dict[str, str]:
    if client.branch_sha("main") != MAIN_SHA:
        raise BackendPreservationStep2PremergeFailure("MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise BackendPreservationStep2PremergeFailure("CANDIDATE_DRIFT")

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)

    for path in WRITE_PATHS:
        if not candidate_tree.get(path):
            raise BackendPreservationStep2PremergeFailure("CANDIDATE_ARTIFACT_MISSING:" + path)
        if main_tree.get(path):
            raise BackendPreservationStep2PremergeFailure("STEP2_ADDITIVE_PATH_COLLISION:" + path)

    for path, expected_blob in PROTECTED_BACKEND_BLOBS.items():
        main_blob = str(main_tree.get(path) or "")
        candidate_blob = str(candidate_tree.get(path) or "")
        if main_blob != expected_blob:
            raise BackendPreservationStep2PremergeFailure("MAIN_BACKEND_BLOB_DRIFT:" + path)
        if candidate_blob != expected_blob:
            raise BackendPreservationStep2PremergeFailure("CANDIDATE_BACKEND_BLOB_DRIFT:" + path)

    return candidate_tree


def _ensure_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode_json(raw, "LEASE"))
    owned = [h for h in state.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
    exact = [
        h
        for h in owned
        if (h.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") == CANDIDATE_SHA
    ]
    if exact:
        if len(owned) != 1 or len(exact) != 1:
            raise BackendPreservationStep2PremergeFailure("LEASE_DUPLICATE")
        return {
            "created": False,
            "replaced": False,
            "lease_id": str(exact[0]["lease_id"]),
            "revision": int(state["revision"]),
            "state_hash": str(state["state_hash"]),
        }
    if len(owned) > 1:
        raise BackendPreservationStep2PremergeFailure("LEASE_DUPLICATE")

    working = state
    released_id = ""
    if owned:
        released_id = str(owned[0]["lease_id"])
        released = release_scope(
            working,
            owner_id=LEASE_OWNER,
            lease_id=released_id,
            expected_revision=int(working["revision"]),
            expected_state_hash=str(working["state_hash"]),
        )
        if released["result"].get("allowed") is not True:
            raise BackendPreservationStep2PremergeFailure("STALE_LEASE_RELEASE_BLOCKED")
        working = released["state"]

    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("cfb:game-total:backend-preservation:step2",),
        shared_resources=("backend:cfb:game-total",),
        resource_identity={"candidate_sha": CANDIDATE_SHA, "main_sha": MAIN_SHA},
        exclusive=False,
    )
    claimed = claim_scope(
        working,
        owner_id=LEASE_OWNER,
        now_utc=_now(),
        scope=scope,
        expected_revision=int(working["revision"]),
        expected_state_hash=str(working["state_hash"]),
        ttl_seconds=3600,
        frozen_paths=(),
        thawed_paths=(),
    )
    if claimed["result"].get("allowed") is not True:
        raise BackendPreservationStep2PremergeFailure(
            "LEASE_BLOCKED:" + str(claimed["result"].get("decision") or "UNKNOWN")
        )

    updated = claimed["state"]
    holders = [h for h in updated.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
    if len(holders) != 1:
        raise BackendPreservationStep2PremergeFailure("LEASE_ID_UNRESOLVED")
    lease_id = str(holders[0]["lease_id"])
    client.update_content(
        LEASE_PATH,
        _json_text(updated),
        LEASE_BRANCH,
        "lease: claim CFB Game Total backend preservation Step 2 scope",
        raw["sha"],
    )
    readback = validate_scope_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK")
    )
    found = [
        h
        for h in readback.get("holders", [])
        if h.get("lease_id") == lease_id and h.get("owner_id") == LEASE_OWNER
    ]
    if len(found) != 1:
        raise BackendPreservationStep2PremergeFailure("LEASE_READBACK_MISMATCH")
    return {
        "created": True,
        "replaced": bool(released_id),
        "released_lease_id": released_id,
        "lease_id": lease_id,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def _existing_gate(client) -> dict | None:
    payload = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in payload.get("check_runs", []):
        if (
            run.get("head_sha") == CANDIDATE_SHA
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
        ):
            return run
    return None


def execute(app):
    client = app.state.github_client
    _verify_heads(client)
    lease = _ensure_lease(client)
    existing = _existing_gate(client)
    if existing:
        return {
            "status": "GREEN",
            "decision": "BACKEND_PRESERVATION_STEP2_ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
            "lease": lease,
            "check_run_id": existing.get("id"),
            "github_actions_fallback": 0,
        }

    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=lease["lease_id"],
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=MAIN_SHA,
    )
    proof = execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )
    return {
        "status": "GREEN" if proof.get("status") == "MERGE_AUTHORIZED" else str(proof.get("status") or "UNKNOWN"),
        "decision": "BACKEND_PRESERVATION_STEP2_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "lease": lease,
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_backend_preservation_step2_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_backend_preservation_step2_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_backend_preservation_step2_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:4200],
            }
        print(
            "CFB_GAME_TOTAL_BACKEND_PRESERVATION_STEP2_PREMERGE="
            + json.dumps(
                app.state.cfb_game_total_backend_preservation_step2_premerge,
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
