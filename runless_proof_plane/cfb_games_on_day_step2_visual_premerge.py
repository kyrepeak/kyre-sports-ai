from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import (
    _hash as registry_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    validate_state as validate_scope_lease_state,
)

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-games-on-day-step2-visual-v1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
BRANCH = "cfb-game-total-games-on-day-step2-visual-v1"
CANDIDATE_SHA = "570a7205fe1b79ebff3b4635f1cd3b30cd32fab5"
MAIN_SHA = "403e3cb9d7b0e11c4bfc15de512fb1a862e88549"
AUTHORIZATION_ID = "AUTH-CFB-GT-GAMES-ON-DAY-STEP2-VISUAL-R1"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-STEP2-VISUAL-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
FROM_BLOB = "154760d34b4f33aed1efafdf2b026262eb0e332b"
TO_BLOB = "7bcb675379ef63f21fd0e6400c9076e746a69b9a"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-games-on-day-step2-visual"
WRITE_PATHS = (
    "cfb_game_total_games_on_day_step2_visual_v1.py",
    ROUTER_PATH,
    "tests/test_cfb_game_total_games_on_day_step2_visual_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-games-on-day-step2-visual-v1.json",
    "devsystem/task_ledgers/cfb-game-total-games-on-day-step2-visual-v1.json",
)


class Step2VisualPremergeFailure(RuntimeError):
    pass


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Step2VisualPremergeFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Step2VisualPremergeFailure(label + "_DECODE_FAILED") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _verify_heads(client) -> tuple[dict[str, str], dict[str, str]]:
    if client.branch_sha("main") != MAIN_SHA:
        raise Step2VisualPremergeFailure("MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise Step2VisualPremergeFailure("CANDIDATE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(ROUTER_PATH) or "") != FROM_BLOB:
        raise Step2VisualPremergeFailure("ROUTER_FROM_BLOB_DRIFT")
    if str(candidate_tree.get(ROUTER_PATH) or "") != TO_BLOB:
        raise Step2VisualPremergeFailure("ROUTER_TO_BLOB_DRIFT")
    for path in WRITE_PATHS:
        if not candidate_tree.get(path):
            raise Step2VisualPremergeFailure("CANDIDATE_ARTIFACT_MISSING:" + path)
    return main_tree, candidate_tree


def _ensure_exact_thaw(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise Step2VisualPremergeFailure("REGISTRY_SOURCE_MAIN_DRIFT")

    matches = [
        grant for grant in registry.get("active_thaws", [])
        if str(grant.get("thaw_id") or "") == THAW_ID
    ]
    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {
            ROUTER_PATH: {
                "from_blob": FROM_BLOB,
                "to_blob": TO_BLOB,
            }
        },
    }
    if matches:
        if len(matches) != 1 or matches[0] != exact:
            raise Step2VisualPremergeFailure("THAW_ID_COLLISION")
        return {
            "created": False,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "active_thaw_count": len(registry.get("active_thaws", [])),
        }

    updated = deepcopy(registry)
    updated["active_thaws"].append(exact)
    updated["active_thaws"] = sorted(updated["active_thaws"], key=lambda row: str(row.get("thaw_id") or ""))
    updated["revision"] = int(updated["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: authorize CFB Games on This Day Step 2 exact-head thaw",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    found = [
        grant for grant in readback.get("active_thaws", [])
        if str(grant.get("thaw_id") or "") == THAW_ID
    ]
    if found != [exact]:
        raise Step2VisualPremergeFailure("THAW_READBACK_MISMATCH")
    return {
        "created": True,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws", [])),
    }


def _ensure_scope_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    existing = [
        holder for holder in state.get("holders", [])
        if str(holder.get("owner_id") or "") == LEASE_OWNER
        and str((holder.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") or "") == CANDIDATE_SHA
    ]
    if existing:
        if len(existing) != 1:
            raise Step2VisualPremergeFailure("LEASE_DUPLICATE")
        return {
            "created": False,
            "lease_id": str(existing[0]["lease_id"]),
            "revision": int(state["revision"]),
            "state_hash": str(state["state_hash"]),
        }

    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("cfb:game-total:games-on-day:step2-visual",),
        shared_resources=("route:cfb:game-total",),
        resource_identity={
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
        },
        exclusive=False,
    )
    claimed = claim_scope(
        state,
        owner_id=LEASE_OWNER,
        now_utc=_now(),
        scope=scope,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
        ttl_seconds=1800,
        frozen_paths=(ROUTER_PATH,),
        thawed_paths=(ROUTER_PATH,),
    )
    result = claimed["result"]
    if result.get("allowed") is not True:
        raise Step2VisualPremergeFailure("LEASE_BLOCKED:" + str(result.get("decision") or "UNKNOWN"))
    updated = claimed["state"]
    lease_id = str(result.get("lease_id") or "")
    if not lease_id:
        candidates = [h for h in updated.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
        if len(candidates) != 1:
            raise Step2VisualPremergeFailure("LEASE_ID_UNRESOLVED")
        lease_id = str(candidates[0]["lease_id"])

    client.update_content(
        LEASE_PATH,
        _json_text(updated),
        LEASE_BRANCH,
        "lease: claim CFB Games on This Day Step 2 visual scope",
        raw["sha"],
    )
    readback = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
    holders = [h for h in readback.get("holders", []) if h.get("lease_id") == lease_id]
    if len(holders) != 1 or holders[0].get("owner_id") != LEASE_OWNER:
        raise Step2VisualPremergeFailure("LEASE_READBACK_MISMATCH")
    return {
        "created": True,
        "lease_id": lease_id,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def _existing_green_gate(client) -> dict | None:
    payload = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in payload.get("check_runs", []):
        if run.get("head_sha") == CANDIDATE_SHA and run.get("status") == "completed" and run.get("conclusion") == "success":
            return run
    return None


def execute(app):
    client = app.state.github_client
    _verify_heads(client)
    thaw = _ensure_exact_thaw(client)
    lease = _ensure_scope_lease(client)

    existing = _existing_green_gate(client)
    if existing:
        return {
            "status": "GREEN",
            "decision": "STEP2_VISUAL_ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
            "thaw": thaw,
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
        "decision": "STEP2_VISUAL_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "thaw": thaw,
        "lease": lease,
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step2_visual_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step2_visual_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step2_visual_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP2_VISUAL_PREMERGE="
            + json.dumps(app.state.cfb_games_on_day_step2_visual_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
