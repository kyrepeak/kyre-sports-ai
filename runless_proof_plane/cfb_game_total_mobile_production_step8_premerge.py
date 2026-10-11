from __future__ import annotations

import base64
import json

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_state

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend

TASK_ID = "cfb-game-total-mobile-production-step8-premerge-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
BRANCH = "cfb-game-total-mobile-production-step8-v1"
CANDIDATE_SHA = "c3b80e23631ce7e4042c88e3df9be4bb4e279a94"
MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
AUTHORIZATION_ID = "AUTH-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
THAW_ID = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
FROZEN_PATH = "cfb_game_total_clean_page_v43.py"
FROM_BLOB = "ebb7bfa20489598a62891ec4e5e868fe350c8712"
TO_BLOB = "33b032014ddb8d9316e9282510d896ec61df603a"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8"


class Step8PremergeFailure(RuntimeError):
    pass


def _decode(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Step8PremergeFailure(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _exact_lease(client) -> str:
    state = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE"))
    found = [
        h for h in state.get("holders", [])
        if h.get("owner_id") == LEASE_OWNER
        and (h.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") == CANDIDATE_SHA
    ]
    if len(found) != 1:
        raise Step8PremergeFailure("EXACT_LEASE_MISSING")
    return str(found[0]["lease_id"])


def _verify_thaw(client) -> dict:
    registry = GithubRegistryBackend(client).read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise Step8PremergeFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    expected = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    found = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if found != [expected]:
        raise Step8PremergeFailure("EXACT_THAW_MISSING")
    return {"revision": int(registry["revision"]), "state_hash": str(registry["state_hash"])}


def _existing_gate(client):
    payload = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100") or {}
    for run in payload.get("check_runs", []):
        if run.get("head_sha") == CANDIDATE_SHA and run.get("status") == "completed" and run.get("conclusion") == "success":
            return run
    return None


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8PremergeFailure("MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise Step8PremergeFailure("CANDIDATE_DRIFT")
    thaw = _verify_thaw(client)
    lease_id = _exact_lease(client)
    existing = _existing_gate(client)
    if existing:
        return {
            "status": "GREEN",
            "decision": "STEP8_ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "check_run_id": existing.get("id"),
            "lease_id": lease_id,
            "thaw": thaw,
            "github_actions_fallback": 0,
        }
    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=lease_id,
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
        "decision": "STEP8_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "lease_id": lease_id,
        "thaw": thaw,
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_step8_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_step8_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5000],
            }
        print("CFB_GAME_TOTAL_STEP8_PREMERGE=" + json.dumps(app.state.cfb_game_total_step8_premerge, sort_keys=True, default=str), flush=True)

    return app


__all__ = ["execute", "install_startup"]
