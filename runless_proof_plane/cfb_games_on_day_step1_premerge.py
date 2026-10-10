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

TASK_ID = "cfb-game-total-games-on-day-step1-card-layout-v1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
CANDIDATE_SHA = "b8b3e77e9106a6240c6abddfbb6f4f22ea2d5d07"
EXPECTED_MAIN_SHA = "3876d4cbe7fe541c94cf3d8e71cc0103b1a6ec66"
AUTHORIZATION_ID = "AUTH-CFB-GT-GAMES-ON-DAY-STEP1-R1"
OWNER_ID = "api2-cfb-games-on-day-step1"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-STEP1-LAYOUT-R1"
FROZEN_PATH = "kyre_remaining_pages_theme_v1.py"
FROM_BLOB = "1695d5046107b22e22e2304e33adec622d083785"
TO_BLOB = "97d735edd788c554051ea7864e2cad50cdec82bc"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
WRITE_PATHS = (
    "cfb_game_total_games_on_day_step1_layout_v1.py",
    "kyre_remaining_pages_theme_v1.py",
    "tests/test_cfb_game_total_games_on_day_step1_layout_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-games-on-day-step1-card-layout-v1.json",
    "devsystem/task_ledgers/cfb-game-total-games-on-day-step1-card-layout-v1.json",
)


class CfbGamesOnDayStep1Failure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise CfbGamesOnDayStep1Failure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise CfbGamesOnDayStep1Failure(label + "_DECODE_FAILED") from exc


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_exact_identities(client) -> None:
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise CfbGamesOnDayStep1Failure("STEP2A_MAIN_DRIFT")
    commit = client.commit(CANDIDATE_SHA)
    if str(commit.get("sha") or "") != CANDIDATE_SHA:
        raise CfbGamesOnDayStep1Failure("STEP2A_CANDIDATE_DRIFT")
    tree = client.tree_blobs(CANDIDATE_SHA)
    if str(tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise CfbGamesOnDayStep1Failure("STEP2A_CANDIDATE_THEME_BLOB_DRIFT")
    main_tree = client.tree_blobs(EXPECTED_MAIN_SHA)
    if str(main_tree.get(FROZEN_PATH) or "") != FROM_BLOB:
        raise CfbGamesOnDayStep1Failure("STEP2A_MAIN_THEME_BLOB_DRIFT")


def _ensure_scope_lease(client, frozen_paths: list[str]) -> str:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    now_utc = _now()
    now_dt = datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
    reusable = []
    for holder in state.get("holders", []):
        expires = datetime.fromisoformat(str(holder["expires_at_utc"]).replace("Z", "+00:00"))
        identity = (holder.get("scope") or {}).get("resource_identity") or {}
        if (
            holder.get("owner_id") == OWNER_ID
            and identity.get("candidate_sha") == CANDIDATE_SHA
            and now_dt < expires
        ):
            reusable.append(holder)
    if len(reusable) == 1:
        return str(reusable[0]["lease_id"])
    if reusable:
        raise CfbGamesOnDayStep1Failure("DUPLICATE_AUTHORITATIVE_LEASE")

    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("cfb_game_total_v163_selector", "cfb_game_total_theme_activation"),
        shared_resources=("route:cfb:game-total",),
        resource_identity={
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": EXPECTED_MAIN_SHA,
        },
        exclusive=False,
    )
    claimed = claim_scope(
        state,
        owner_id=OWNER_ID,
        now_utc=now_utc,
        scope=scope,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
        ttl_seconds=3600,
        frozen_paths=frozen_paths,
        thawed_paths=(FROZEN_PATH,),
    )
    result = claimed["result"]
    if result.get("allowed") is not True:
        raise CfbGamesOnDayStep1Failure("LEASE_BLOCKED:" + str(result.get("decision") or "UNKNOWN"))
    updated = claimed["state"]
    client.update_content(
        LEASE_PATH,
        _json_text(updated),
        LEASE_BRANCH,
        "lease: claim CFB Games on This Day Step 1 exact scope",
        raw["sha"],
    )
    readback = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
    matches = [h for h in readback.get("holders", []) if h.get("lease_id") == result["lease_id"]]
    if len(matches) != 1:
        raise CfbGamesOnDayStep1Failure("LEASE_READBACK_MISMATCH")
    return str(result["lease_id"])


def _ensure_exact_thaw(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != EXPECTED_MAIN_SHA:
        raise CfbGamesOnDayStep1Failure("REGISTRY_MAIN_IDENTITY_DRIFT")
    if str(validated["artifacts"].get(FROZEN_PATH) or "") != FROM_BLOB:
        raise CfbGamesOnDayStep1Failure("REGISTRY_FROZEN_BASELINE_DRIFT")

    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {
            FROZEN_PATH: {
                "from_blob": FROM_BLOB,
                "to_blob": TO_BLOB,
            }
        },
    }
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if matches:
        if len(matches) != 1 or matches[0] != exact:
            raise CfbGamesOnDayStep1Failure("THAW_IDENTITY_COLLISION")
        return registry

    updated = deepcopy(registry)
    updated["active_thaws"] = list(updated.get("active_thaws", [])) + [exact]
    updated["revision"] = int(updated["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise CfbGamesOnDayStep1Failure("MAIN_MOVED_BEFORE_THAW")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: exact thaw CFB Games on This Day Step 1 layout",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    exact_matches = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if len(exact_matches) != 1 or exact_matches[0] != exact:
        raise CfbGamesOnDayStep1Failure("THAW_READBACK_MISMATCH")
    return readback


def execute(app):
    client = app.state.github_client
    _ensure_exact_identities(client)

    registry = GithubRegistryBackend(client).read_registry()
    validated = validate_registry(registry)
    lease_id = _ensure_scope_lease(client, sorted(validated["artifacts"]))
    thawed = _ensure_exact_thaw(client)

    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise CfbGamesOnDayStep1Failure("MAIN_MOVED_BEFORE_PROOF")

    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=lease_id,
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=EXPECTED_MAIN_SHA,
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
        "task_id": TASK_ID,
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": EXPECTED_MAIN_SHA,
        "lease_id": lease_id,
        "thaw_id": THAW_ID,
        "registry_revision": int(thawed["revision"]),
        "registry_state_hash": str(thawed["state_hash"]),
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_PREMERGE="
            + json.dumps(app.state.cfb_games_on_day_step1_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
