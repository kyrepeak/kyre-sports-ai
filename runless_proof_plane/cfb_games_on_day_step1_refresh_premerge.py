from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import (
    _hash as registry_hash,
    _payload_without_hash,
    validate_registry,
)

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-games-on-day-step1-runtime-refresh-r1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
MAIN_SHA = "60da7cbd5cf05413f2c9d8ce3e8921adb2f58648"
BRANCH = "cfb-game-total-games-on-day-step1-runtime-refresh-r1"
BRANCH_PRE_THAW_SHA = "e6b04afc6b3e1689d96ddef6111c2d2b78aa94d6"
CANDIDATE_SHA = "b4ff5f9271e5e3f65dc8446ef62495ed1240502c"
LEASE_ID = "SCOPE-LEASE-CE9FDE29B716004089C59117"
AUTHORIZATION_ID = "AUTH-CFB-GT-GAMES-ON-DAY-STEP1-REFRESH-R1"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-STEP1-RUNTIME-REFRESH-R1"
FROZEN_PATH = "requirements.txt"
FROM_BLOB = "2904ed539d5a2e8a195675b96b756fb6ba6a3c74"
TO_BLOB = "1022d95a71b3c04aa5310b5057de74978e4cffa4"


class RefreshPremergeFailure(RuntimeError):
    pass


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _ensure_exact_thaw(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise RefreshPremergeFailure("REFRESH_REGISTRY_MAIN_DRIFT")
    if str(validated["artifacts"].get(FROZEN_PATH) or "") != FROM_BLOB:
        raise RefreshPremergeFailure("REFRESH_REQUIREMENTS_BASELINE_DRIFT")

    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if matches:
        if len(matches) != 1 or matches[0] != exact:
            raise RefreshPremergeFailure("REFRESH_THAW_IDENTITY_COLLISION")
        return registry

    before_ids = [str(g.get("thaw_id") or "") for g in registry.get("active_thaws", [])]
    updated = deepcopy(registry)
    updated["active_thaws"] = list(updated.get("active_thaws", [])) + [exact]
    updated["revision"] = int(updated["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    if client.branch_sha("main") != MAIN_SHA:
        raise RefreshPremergeFailure("REFRESH_MAIN_MOVED_BEFORE_THAW")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: exact thaw CFB Games on This Day Step 1 runtime refresh",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    read_ids = [str(g.get("thaw_id") or "") for g in readback.get("active_thaws", [])]
    if read_ids[:-1] != before_ids or read_ids[-1:] != [THAW_ID]:
        raise RefreshPremergeFailure("REFRESH_UNRELATED_THAW_DRIFT")
    found = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if len(found) != 1 or found[0] != exact:
        raise RefreshPremergeFailure("REFRESH_THAW_READBACK_MISMATCH")
    return readback


def _promote_exact_candidate(client) -> None:
    current = client.branch_sha(BRANCH)
    if current == CANDIDATE_SHA:
        return
    if current != BRANCH_PRE_THAW_SHA:
        raise RefreshPremergeFailure("REFRESH_BRANCH_PRE_THAW_DRIFT")
    commit = client.commit(CANDIDATE_SHA)
    if str(commit.get("sha") or "") != CANDIDATE_SHA:
        raise RefreshPremergeFailure("REFRESH_CANDIDATE_MISSING")
    tree = client.tree_blobs(CANDIDATE_SHA)
    if str(tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise RefreshPremergeFailure("REFRESH_REQUIREMENTS_BLOB_DRIFT")
    client.request(
        "PATCH",
        f"/git/refs/heads/{BRANCH}",
        json={"sha": CANDIDATE_SHA, "force": False},
    )
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RefreshPremergeFailure("REFRESH_BRANCH_PROMOTION_READBACK_MISMATCH")


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise RefreshPremergeFailure("REFRESH_MAIN_DRIFT")
    registry = _ensure_exact_thaw(client)
    _promote_exact_candidate(client)
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
        "decision": "CFB_GAMES_ON_DAY_STEP1_RUNTIME_REFRESH_PREMERGE",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "lease_id": LEASE_ID,
        "thaw_id": THAW_ID,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_refresh_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_refresh_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_refresh_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_REFRESH_PREMERGE="
            + json.dumps(app.state.cfb_games_on_day_step1_refresh_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
