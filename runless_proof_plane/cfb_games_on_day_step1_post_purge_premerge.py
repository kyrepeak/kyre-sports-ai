from __future__ import annotations

import json
import time
from copy import deepcopy

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-games-on-day-step1-card-layout-v1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
CANDIDATE_SHA = "58f237846007e2a0d036471d238b6c6fd9edcdc7"
MAIN_SHA = "f15fe559fdaab801deb77c43c6451bc811159fed"
PRIOR_MAIN_SHA = "60da7cbd5cf05413f2c9d8ce3e8921adb2f58648"
LEASE_ID = "SCOPE-LEASE-1E6EB6A9E37AEFB89F845E21"
AUTHORIZATION_ID = "AUTH-CFB-GT-GAMES-ON-DAY-STEP1-POST-PURGE-R1"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-STEP1-RUNTIME-REFRESH-R1"
FROZEN_PATH = "requirements.txt"
FROM_BLOB = "2904ed539d5a2e8a195675b96b756fb6ba6a3c74"
TO_BLOB = "1022d95a71b3c04aa5310b5057de74978e4cffa4"


class PostPurgePremergeFailure(RuntimeError):
    pass


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _existing_green_gate(client) -> dict | None:
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


def _reconcile_registry(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    source = str(registry.get("source_main_sha") or "")
    if source == MAIN_SHA:
        if any(g.get("thaw_id") == THAW_ID for g in registry.get("active_thaws", [])):
            raise PostPurgePremergeFailure("REFRESH_THAW_SURVIVED_RECONCILED_MAIN")
        return registry
    if source != PRIOR_MAIN_SHA:
        raise PostPurgePremergeFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgePremergeFailure("MAIN_DRIFT_BEFORE_REGISTRY_RECONCILE")

    main_tree = client.tree_blobs(MAIN_SHA)
    if str(main_tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise PostPurgePremergeFailure("MERGED_REQUIREMENTS_BLOB_DRIFT")
    thaw_ids = [str(g.get("thaw_id") or "") for g in registry.get("active_thaws", [])]
    if THAW_ID not in thaw_ids:
        raise PostPurgePremergeFailure("EXPECTED_REFRESH_THAW_MISSING")
    unrelated_before = [item for item in deepcopy(registry.get("active_thaws", [])) if item.get("thaw_id") != THAW_ID]

    plan = plan_baseline_forward_port(
        registry,
        updates={FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
        source_main_sha=MAIN_SHA,
    )
    updated = plan["registry"]
    if THAW_ID not in plan.get("retired_empty_thaw_grants", []):
        raise PostPurgePremergeFailure("REFRESH_THAW_NOT_RETIRED")
    if updated.get("active_thaws", []) != unrelated_before:
        raise PostPurgePremergeFailure("UNRELATED_THAW_DRIFT")
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: reconcile merged CFB Step 1 runtime refresh baseline",
        backend._blob_sha,
    )

    last = None
    for _ in range(8):
        last = backend.read_registry()
        validate_registry(last)
        if (
            str(last.get("source_main_sha") or "") == MAIN_SHA
            and not any(g.get("thaw_id") == THAW_ID for g in last.get("active_thaws", []))
            and last.get("active_thaws", []) == unrelated_before
        ):
            return last
        time.sleep(0.75)
    raise PostPurgePremergeFailure("REGISTRY_RECONCILE_READBACK_MISMATCH")


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgePremergeFailure("POST_PURGE_MAIN_DRIFT")
    commit = client.commit(CANDIDATE_SHA)
    if str(commit.get("sha") or "") != CANDIDATE_SHA:
        raise PostPurgePremergeFailure("POST_PURGE_CANDIDATE_DRIFT")

    registry = _reconcile_registry(client)
    existing = _existing_green_gate(client)
    if existing:
        return {
            "status": "GREEN",
            "decision": "POST_PURGE_ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
            "lease_id": LEASE_ID,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "check_run_id": existing.get("id"),
            "github_actions_fallback": 0,
        }

    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=LEASE_ID,
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
        "decision": "POST_PURGE_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "lease_id": LEASE_ID,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_post_purge_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_post_purge_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_post_purge_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_POST_PURGE_PREMERGE="
            + json.dumps(app.state.cfb_games_on_day_step1_post_purge_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
