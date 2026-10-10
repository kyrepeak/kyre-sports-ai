from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state as validate_scope_state

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-native-page1-shell-step3-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
BRANCH = "cfb-game-total-native-page1-shell-step3-v1"
CANDIDATE_SHA = "091ec7abc840119705e7f98d895c1346871ed2f8"
MAIN_SHA = "a3166e7d980d85b6adb6a064b8ac225befd9b9e3"
AUTHORIZATION_ID = "AUTH-CFB-GT-NATIVE-PAGE1-SHELL-STEP3-R1"
THAW_ID = "THAW-CFB-GT-NATIVE-PAGE1-SHELL-STEP3-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
FROM_BLOB = "7f27ead880acdbe6a272e6d34dfcd55d84a926d0"
TO_BLOB = "7e38d5b3cac89e0ea30fa01d972d8fce85abe66e"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-native-page1-shell-step3"
WRITE_PATHS = (
    "cfb_game_total_clean_page_v40.py",
    ROUTER_PATH,
    "tests/test_cfb_game_total_native_page1_shell_step3_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-native-page1-shell-step3-v1.json",
    "devsystem/task_ledgers/cfb-game-total-native-page1-shell-step3-v1.json",
    "docs/superpowers/plans/2026-10-10-cfb-game-total-native-page1-shell-step3-v1.md",
)
ADDITIVE_PATHS = tuple(path for path in WRITE_PATHS if path != ROUTER_PATH)
PROTECTED_BLOBS = {
    "cfb_game_total_clean_page_v39.py": "0135dc520dfaa0c2c878cbb17618f17188dfff1a",
    "cfb_freeze_manifest_v12.json": "3ff2a727967e80dddbe03f747d9f32090cc39539",
    "cfb_game_total_model_v1.py": "88e98c2b78c689e48f81f049cb1a64c0e958e964",
    "cfb_game_total_final_v1.py": "78fbeaeb77e3101cc83c579b15f9cd6d485df952",
    "cfb_game_total_slate_v1.py": "777beb82b1dc3dd7df76f8f4d8d37f87eeb9b872",
    "cfb_game_total_model_input_v1.py": "0d270126b6265ec22c29ea0a73faaf57235f4b8e",
    "cfb_game_total_slate_v2.py": "1acc2859bc1666b968e8ea54fb7fadc905781d81",
    "cfb_game_total_step3_form_v1.py": "ea7bad697064625588ec31971fe642446d2f8b34",
    "cfb_game_total_page2_step8_final_runtime_v1.py": "bf3141e958826cf93cb39435e7ea809865f92a29",
}


class NativePage1ShellStep3PremergeFailure(RuntimeError):
    pass


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise NativePage1ShellStep3PremergeFailure(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _verify_heads(client) -> dict[str, str]:
    if client.branch_sha("main") != MAIN_SHA:
        raise NativePage1ShellStep3PremergeFailure("MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise NativePage1ShellStep3PremergeFailure("CANDIDATE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(ROUTER_PATH) or "") != FROM_BLOB:
        raise NativePage1ShellStep3PremergeFailure("ROUTER_FROM_BLOB_DRIFT")
    if str(candidate_tree.get(ROUTER_PATH) or "") != TO_BLOB:
        raise NativePage1ShellStep3PremergeFailure("ROUTER_TO_BLOB_DRIFT")
    for path in ADDITIVE_PATHS:
        if main_tree.get(path):
            raise NativePage1ShellStep3PremergeFailure("STEP3_ADDITIVE_PATH_COLLISION:" + path)
        if not candidate_tree.get(path):
            raise NativePage1ShellStep3PremergeFailure("CANDIDATE_ARTIFACT_MISSING:" + path)
    for path, expected_blob in PROTECTED_BLOBS.items():
        if str(main_tree.get(path) or "") != expected_blob:
            raise NativePage1ShellStep3PremergeFailure("MAIN_PROTECTED_BLOB_DRIFT:" + path)
        if str(candidate_tree.get(path) or "") != expected_blob:
            raise NativePage1ShellStep3PremergeFailure("CANDIDATE_PROTECTED_BLOB_DRIFT:" + path)
    return candidate_tree


def _ensure_thaw(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise NativePage1ShellStep3PremergeFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {ROUTER_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if len(matches) > 1:
        raise NativePage1ShellStep3PremergeFailure("THAW_DUPLICATE")
    if matches == [exact]:
        return {"created": False, "revision": int(registry["revision"]), "state_hash": str(registry["state_hash"])}
    unrelated = [deepcopy(g) for g in registry.get("active_thaws", []) if g.get("thaw_id") != THAW_ID]
    if matches:
        raise NativePage1ShellStep3PremergeFailure("THAW_ID_COLLISION")
    updated = deepcopy(registry)
    updated["active_thaws"] = sorted(unrelated + [exact], key=lambda row: str(row.get("thaw_id") or ""))
    updated["revision"] = int(updated["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: authorize CFB Game Total native Page1 shell Step 3 exact-head thaw",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    found = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if found != [exact]:
        raise NativePage1ShellStep3PremergeFailure("THAW_READBACK_MISMATCH")
    if [g for g in readback.get("active_thaws", []) if g.get("thaw_id") != THAW_ID] != unrelated:
        raise NativePage1ShellStep3PremergeFailure("UNRELATED_THAW_DRIFT")
    return {
        "created": True,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws", [])),
    }


def _ensure_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode_json(raw, "LEASE"))
    owned = [h for h in state.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
    exact = [
        h for h in owned
        if (h.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") == CANDIDATE_SHA
    ]
    if exact:
        if len(owned) != 1 or len(exact) != 1:
            raise NativePage1ShellStep3PremergeFailure("LEASE_DUPLICATE")
        return {"created": False, "lease_id": str(exact[0]["lease_id"]), "revision": int(state["revision"]), "state_hash": str(state["state_hash"])}
    if len(owned) > 1:
        raise NativePage1ShellStep3PremergeFailure("LEASE_DUPLICATE")
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
            raise NativePage1ShellStep3PremergeFailure("STALE_LEASE_RELEASE_BLOCKED")
        working = released["state"]
    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("cfb:game-total:native-page1-shell:step3",),
        shared_resources=("route:cfb:game-total", "presentation:cfb:game-total:page1"),
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
        frozen_paths=(ROUTER_PATH,),
        thawed_paths=(ROUTER_PATH,),
    )
    if claimed["result"].get("allowed") is not True:
        raise NativePage1ShellStep3PremergeFailure("LEASE_BLOCKED:" + str(claimed["result"].get("decision") or "UNKNOWN"))
    updated = claimed["state"]
    holders = [h for h in updated.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
    if len(holders) != 1:
        raise NativePage1ShellStep3PremergeFailure("LEASE_ID_UNRESOLVED")
    lease_id = str(holders[0]["lease_id"])
    client.update_content(
        LEASE_PATH,
        _json_text(updated),
        LEASE_BRANCH,
        "lease: claim CFB Game Total native Page1 shell Step 3 scope",
        raw["sha"],
    )
    readback = validate_scope_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
    found = [h for h in readback.get("holders", []) if h.get("lease_id") == lease_id and h.get("owner_id") == LEASE_OWNER]
    if len(found) != 1:
        raise NativePage1ShellStep3PremergeFailure("LEASE_READBACK_MISMATCH")
    return {
        "created": True,
        "replaced": bool(released_id),
        "released_lease_id": released_id,
        "lease_id": lease_id,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def _existing_gate(client) -> dict | None:
    payload = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100") or {}
    for run in payload.get("check_runs", []):
        if run.get("head_sha") == CANDIDATE_SHA and run.get("status") == "completed" and run.get("conclusion") == "success":
            return run
    return None


def execute(app):
    client = app.state.github_client
    _verify_heads(client)
    thaw = _ensure_thaw(client)
    lease = _ensure_lease(client)
    existing = _existing_gate(client)
    if existing:
        return {
            "status": "GREEN",
            "decision": "NATIVE_PAGE1_SHELL_STEP3_ALREADY_MERGE_AUTHORIZED",
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
        "decision": "NATIVE_PAGE1_SHELL_STEP3_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "thaw": thaw,
        "lease": lease,
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_native_page1_shell_step3_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_native_page1_shell_step3_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_native_page1_shell_step3_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:4200],
            }
        print(
            "CFB_GAME_TOTAL_NATIVE_PAGE1_SHELL_STEP3_PREMERGE="
            + json.dumps(app.state.cfb_game_total_native_page1_shell_step3_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
