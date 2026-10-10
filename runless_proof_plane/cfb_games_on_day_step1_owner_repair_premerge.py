from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_lease_state,
)

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-games-on-day-step1-card-layout-v1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
CANDIDATE_SHA = "3cec8dd71aeb7337e9eb0c508e564ffafb48bad3"
EXPECTED_MAIN_SHA = "60da7cbd5cf05413f2c9d8ce3e8921adb2f58648"
PRIOR_REGISTRY_MAIN_SHA = "3876d4cbe7fe541c94cf3d8e71cc0103b1a6ec66"
AUTHORIZATION_ID = "AUTH-CFB-GT-GAMES-ON-DAY-STEP1-OWNER-REPAIR-R1"
OWNER_ID = "api2-cfb-games-on-day-step1"
OLD_LEASE_ID = "SCOPE-LEASE-C314CE5BCC31A3DD4CF3B305"
SUPERSEDED_OWNER_ID = "api2-cfb-games-on-day-step1-runtime-refresh"
SUPERSEDED_BRANCH = "cfb-game-total-games-on-day-step1-runtime-refresh-r1"
SUPERSEDED_LEDGER = "devsystem/task_ledgers/cfb-game-total-games-on-day-step1-runtime-refresh-r1.json"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-STEP1-LAYOUT-R1"
FROZEN_PATH = "kyre_remaining_pages_theme_v1.py"
FROM_BLOB = "1695d5046107b22e22e2304e33adec622d083785"
TO_BLOB = "97d735edd788c554051ea7864e2cad50cdec82bc"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
WRITE_PATHS = (
    "cfb_game_total_games_on_day_step1_layout_v1.py",
    "tests/test_cfb_game_total_games_on_day_step1_layout_v1.py",
)


class OwnerRepairProofFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise OwnerRepairProofFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise OwnerRepairProofFailure(label + "_DECODE_FAILED") from exc


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _existing_green_gate(client) -> bool:
    payload = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    return any(
        run.get("head_sha") == CANDIDATE_SHA
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        for run in payload.get("check_runs", [])
    )


def _verify_heads(client) -> None:
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise OwnerRepairProofFailure("OWNER_REPAIR_MAIN_DRIFT")
    commit = client.commit(CANDIDATE_SHA)
    if str(commit.get("sha") or "") != CANDIDATE_SHA:
        raise OwnerRepairProofFailure("OWNER_REPAIR_CANDIDATE_DRIFT")


def _reconcile_registry_to_merged_main(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    current_source = str(registry.get("source_main_sha") or "")
    if current_source == EXPECTED_MAIN_SHA:
        return registry
    if current_source != PRIOR_REGISTRY_MAIN_SHA:
        raise OwnerRepairProofFailure("OWNER_REPAIR_REGISTRY_MAIN_DRIFT")
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise OwnerRepairProofFailure("OWNER_REPAIR_MAIN_MOVED_BEFORE_REGISTRY_RECONCILE")
    main_tree = client.tree_blobs(EXPECTED_MAIN_SHA)
    if str(main_tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise OwnerRepairProofFailure("OWNER_REPAIR_THEME_BLOB_DRIFT")

    unrelated_before = [
        str(item.get("thaw_id") or "")
        for item in registry.get("active_thaws", [])
        if str(item.get("thaw_id") or "") != THAW_ID
    ]
    plan = plan_baseline_forward_port(
        registry,
        updates={FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
        source_main_sha=EXPECTED_MAIN_SHA,
    )
    updated = plan["registry"]
    if THAW_ID not in plan.get("retired_empty_thaw_grants", []):
        raise OwnerRepairProofFailure("OWNER_REPAIR_EXPECTED_THAW_NOT_RETIRED")
    unrelated_after = [str(item.get("thaw_id") or "") for item in updated.get("active_thaws", [])]
    if unrelated_after != unrelated_before:
        raise OwnerRepairProofFailure("OWNER_REPAIR_UNRELATED_THAW_DRIFT")
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: reconcile CFB Step 1 merged baseline before owner repair proof",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != EXPECTED_MAIN_SHA:
        raise OwnerRepairProofFailure("OWNER_REPAIR_REGISTRY_READBACK_DRIFT")
    if any(str(item.get("thaw_id") or "") == THAW_ID for item in readback.get("active_thaws", [])):
        raise OwnerRepairProofFailure("OWNER_REPAIR_THAW_RETIRE_READBACK_DRIFT")
    return readback


def _release_superseded_runtime_refresh(client, state: dict) -> dict:
    holders = [
        h for h in state.get("holders", [])
        if h.get("owner_id") == SUPERSEDED_OWNER_ID
    ]
    if not holders:
        return state
    if len(holders) != 1:
        raise OwnerRepairProofFailure("OWNER_REPAIR_DUPLICATE_SUPERSEDED_LEASE")

    ref = client.get_ref(SUPERSEDED_BRANCH)
    if not ref:
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_BRANCH_MISSING")
    head = str((ref.get("object") or {}).get("sha") or "")
    if not head:
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_HEAD_MISSING")

    runs = client.request("GET", f"/commits/{head}/check-runs?per_page=100") or {}
    if runs.get("check_runs"):
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_HAS_PROOF_ACTIVITY")
    prs = client.request(
        "GET",
        f"/pulls?state=open&head=kyrepeak:{SUPERSEDED_BRANCH}&per_page=10",
    ) or []
    if prs:
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_HAS_OPEN_PR")

    ledger = _decode_json(client.content(SUPERSEDED_LEDGER, ref=SUPERSEDED_BRANCH), "SUPERSEDED_LEDGER")
    runless = ledger.get("runless") if isinstance(ledger.get("runless"), dict) else {}
    if ledger.get("status") != "CANDIDATE_ASSEMBLY" or runless.get("proof_request_status") != "NOT_SUBMITTED":
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_NOT_IDLE")

    candidate_tree = client.tree_blobs(head)
    main_tree = client.tree_blobs(EXPECTED_MAIN_SHA)
    if candidate_tree.get("requirements.txt") != main_tree.get("requirements.txt"):
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_RUNTIME_MUTATION_PRESENT")

    holder = holders[0]
    released = release_scope(
        state,
        owner_id=SUPERSEDED_OWNER_ID,
        lease_id=str(holder["lease_id"]),
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_RELEASE_BLOCKED")
    return released["state"]


def _rotate_scope_lease(client, registry: dict) -> str:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    now_utc = _now()

    current = state
    old = [
        h for h in current.get("holders", [])
        if h.get("owner_id") == OWNER_ID and h.get("lease_id") == OLD_LEASE_ID
    ]
    if len(old) > 1:
        raise OwnerRepairProofFailure("OWNER_REPAIR_DUPLICATE_OLD_LEASE")
    if old:
        released = release_scope(
            current,
            owner_id=OWNER_ID,
            lease_id=OLD_LEASE_ID,
            expected_revision=int(current["revision"]),
            expected_state_hash=str(current["state_hash"]),
        )
        if released["result"].get("allowed") is not True:
            raise OwnerRepairProofFailure("OWNER_REPAIR_OLD_LEASE_RELEASE_BLOCKED")
        current = released["state"]

    current = _release_superseded_runtime_refresh(client, current)

    matching = []
    for holder in current.get("holders", []):
        identity = (holder.get("scope") or {}).get("resource_identity") or {}
        if (
            holder.get("owner_id") == OWNER_ID
            and identity.get("candidate_sha") == CANDIDATE_SHA
            and identity.get("main_sha") == EXPECTED_MAIN_SHA
        ):
            matching.append(holder)
    if len(matching) > 1:
        raise OwnerRepairProofFailure("OWNER_REPAIR_DUPLICATE_NEW_LEASE")
    if matching:
        return str(matching[0]["lease_id"])

    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("cfb_game_total_step4_games_owner",),
        shared_resources=("route:cfb:game-total",),
        resource_identity={"candidate_sha": CANDIDATE_SHA, "main_sha": EXPECTED_MAIN_SHA},
        exclusive=False,
    )
    frozen_paths = sorted(validate_registry(registry)["artifacts"])
    claimed = claim_scope(
        current,
        owner_id=OWNER_ID,
        now_utc=now_utc,
        scope=scope,
        expected_revision=int(current["revision"]),
        expected_state_hash=str(current["state_hash"]),
        ttl_seconds=3600,
        frozen_paths=frozen_paths,
        thawed_paths=(),
    )
    if claimed["result"].get("allowed") is not True:
        raise OwnerRepairProofFailure(
            "OWNER_REPAIR_LEASE_BLOCKED:" + str(claimed["result"].get("decision") or "UNKNOWN")
        )
    final_state = claimed["state"]
    client.update_content(
        LEASE_PATH,
        _json_text(final_state),
        LEASE_BRANCH,
        "lease: retire superseded refresh and claim CFB Step 1 owner repair scope",
        raw["sha"],
    )
    lease_id = str(claimed["result"]["lease_id"])
    readback = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
    matches = [h for h in readback.get("holders", []) if h.get("lease_id") == lease_id]
    if len(matches) != 1:
        raise OwnerRepairProofFailure("OWNER_REPAIR_LEASE_READBACK_MISMATCH")
    if any(h.get("owner_id") == SUPERSEDED_OWNER_ID for h in readback.get("holders", [])):
        raise OwnerRepairProofFailure("OWNER_REPAIR_SUPERSEDED_RELEASE_READBACK_MISMATCH")
    return lease_id


def execute(app):
    client = app.state.github_client
    _verify_heads(client)
    if _existing_green_gate(client):
        return {
            "status": "GREEN",
            "decision": "OWNER_REPAIR_ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": EXPECTED_MAIN_SHA,
            "github_actions_fallback": 0,
        }

    registry = _reconcile_registry_to_merged_main(client)
    lease_id = _rotate_scope_lease(client, registry)
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise OwnerRepairProofFailure("OWNER_REPAIR_MAIN_MOVED_BEFORE_PROOF")

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
        "decision": "OWNER_REPAIR_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": EXPECTED_MAIN_SHA,
        "lease_id": lease_id,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_owner_repair_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_owner_repair_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_owner_repair_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_OWNER_REPAIR_PREMERGE="
            + json.dumps(app.state.cfb_games_on_day_step1_owner_repair_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
