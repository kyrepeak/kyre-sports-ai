from __future__ import annotations

import base64
import json
import os
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state

from .registry import GithubRegistryBackend, REGISTRY_PATH

ENV = "RPP_NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT_ON_START"
TASK_ID = "nba-spread-step2-site-activation-v1"
WORKSTREAM = "nba-spread-two-page-v1"
SOURCE_MAIN_SHA = "9a7afa1fe19d62eed444088a8e77ca6c45e0bfb1"
CANDIDATE_SHA = "bfae122c36ea29d18a64a9e7ff4c40b06e24640f"
MAIN_SHA = "30e803ea24274edab756dfc1973312ea8df567a4"
THAW_ID = "THAW-NBA-SPREAD-STEP2-SITE-ACTIVATION-R1"
FREEZE_TOKEN = "NBA_SPREAD_STEP2_SITE_ACTIVATION_FROZEN"
RECEIPT_DIGEST = "bf1f123a63a604078c3b587cb811241670e85371de560464461f58cff47714f2"
CHECK_RUN_ID = 55334333227
EXPECTED_REGISTRY_REVISION = 293
EXPECTED_REGISTRY_HASH = "fb1b3518bee5e99902e97d16a53e21669745a3b67ae5c248be5c4a79c3b1a50"
LEASE_OWNER = "chatgpt:api2:nba-spread-step2-site-activation-v1-finalizer"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
THAW_FILES = {
    "app.py": {
        "from_blob": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
        "to_blob": "a8802aa8e32b430e5c33378ab1105ca877b934c1",
    },
    "tests/test_devsystem_change_classifier_v1.py": {
        "from_blob": "265129d2ce89da49426b36059294fcba381cfb7b",
        "to_blob": "6b064453b2d79ab933ce58f9d2a504e34f6fbd21",
    },
}
WRITE_PATHS = (
    "app.py",
    "devsystem/devsystem_manifest_v1.json",
    "devsystem/execution_plans/nba-spread-step2-site-activation-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step2-site-activation-v1.json",
    "devsystem/task_ledgers/nba-spread-step2-site-activation-v1.json",
    "nba_spread_page_v1.py",
    "nba_spread_step2_activation_v1.py",
    "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py",
    "tests/test_devsystem_change_classifier_v1.py",
    "tests/test_nba_spread_step2_site_activation_v1.py",
)


class NBAGroupStep2CloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise NBAGroupStep2CloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise NBAGroupStep2CloseoutFailure(label + "_DECODE_FAILED") from exc


def _assert_merge_and_gate(client) -> None:
    if client.branch_sha("main") != MAIN_SHA:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if SOURCE_MAIN_SHA not in parents or CANDIDATE_SHA not in parents:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_MERGE_LINEAGE_DRIFT")

    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + RECEIPT_DIGEST
    matches = []
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if (
            str(run.get("head_sha") or "") == CANDIDATE_SHA
            and int(run.get("id") or 0) == CHECK_RUN_ID
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and str(output.get("summary") or "") == expected_summary
        ):
            matches.append(run)
    if len(matches) != 1:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_EXACT_GATE_MISSING")


def _read_registry(client) -> tuple[GithubRegistryBackend, dict]:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    return backend, registry


def _assert_registry_prestate(client, registry: dict) -> tuple[dict, dict]:
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_REGISTRY_MAIN_DRIFT")

    thaws = [item for item in registry.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(thaws) != 1:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_THAW_IDENTITY_DRIFT")
    thaw = thaws[0]
    if (
        thaw.get("status") != "ACTIVE"
        or str(thaw.get("target_head_sha") or "") != CANDIDATE_SHA
        or thaw.get("files") != THAW_FILES
    ):
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_THAW_DRIFT")

    validated = validate_registry(registry)
    source_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    merged_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    for path, pair in THAW_FILES.items():
        if str(validated["artifacts"].get(path) or "") != pair["from_blob"]:
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_BASELINE_DRIFT:" + path)
        if str(source_tree.get(path) or "") != pair["from_blob"]:
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_SOURCE_BLOB_DRIFT:" + path)
        if str(candidate_tree.get(path) or "") != pair["to_blob"]:
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_CANDIDATE_BLOB_DRIFT:" + path)
        if str(merged_tree.get(path) or "") != pair["to_blob"]:
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_MERGED_BLOB_DRIFT:" + path)
    return validated, merged_tree


def _claim_lease(client, registry: dict, validated: dict) -> str:
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_state(_decode_json(raw, "NBA_STEP2_CLOSEOUT_LEASE"))
    duplicate = [item for item in state.get("holders", []) if item.get("owner_id") == LEASE_OWNER]
    if duplicate:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_DUPLICATE_FINALIZER_LEASE")

    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("workstream:nba-spread-two-page-v1", "phase:postmerge-closeout"),
        shared_resources=("registry:monster-frozen-artifact-registry",),
        resource_identity={
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
            "source_main_sha": SOURCE_MAIN_SHA,
            "registry_state_hash": str(registry["state_hash"]),
            "freeze_token": FREEZE_TOKEN,
        },
    )
    claimed = claim_scope(
        state,
        owner_id=LEASE_OWNER,
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        scope=scope,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
        ttl_seconds=900,
        frozen_paths=tuple(validated["artifacts"].keys()),
        thawed_paths=tuple(THAW_FILES.keys()),
    )
    if claimed["result"].get("allowed") is not True:
        raise NBAGroupStep2CloseoutFailure(
            "NBA_STEP2_CLOSEOUT_LEASE_BLOCKED:" + str(claimed["result"].get("decision"))
        )
    lease_id = str(claimed["result"]["lease_id"])
    client.update_content(
        LEASE_PATH,
        json.dumps(claimed["state"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: claim NBA Spread Step2 postmerge finalizer",
        str(raw.get("sha") or ""),
    )
    readback = validate_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_REF), "NBA_STEP2_CLOSEOUT_LEASE_READBACK"))
    if len([item for item in readback.get("holders", []) if item.get("lease_id") == lease_id]) != 1:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_LEASE_READBACK_MISMATCH")
    return lease_id


def _release_lease(client, lease_id: str) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_state(_decode_json(raw, "NBA_STEP2_CLOSEOUT_LEASE_RELEASE"))
    holders = [item for item in state.get("holders", []) if item.get("lease_id") == lease_id]
    if not holders:
        return {"released": True, "already_absent": True}
    released = release_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=lease_id,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_LEASE_RELEASE_BLOCKED")
    client.update_content(
        LEASE_PATH,
        json.dumps(released["state"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: release NBA Spread Step2 postmerge finalizer",
        str(raw.get("sha") or ""),
    )
    readback = validate_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_REF), "NBA_STEP2_CLOSEOUT_LEASE_RELEASE_READBACK"))
    if any(item.get("lease_id") == lease_id for item in readback.get("holders", [])):
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_LEASE_RELEASE_READBACK_MISMATCH")
    return {"released": True, "already_absent": False}


def _build_registry_after(registry: dict, merged_tree: dict) -> tuple[dict, dict]:
    updated = deepcopy(registry)
    freeze_artifacts = {path: str(merged_tree.get(path) or "") for path in WRITE_PATHS}
    if any(not blob for blob in freeze_artifacts.values()):
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_FREEZE_ARTIFACT_MISSING")

    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    existing = (updated.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if existing != exact_entry:
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_FREEZE_TOKEN_COLLISION")
        return updated, {"exact_entry": exact_entry, "rebased_unrelated_thaw_pairs": 0}

    for checkpoint, entry in updated["entries"].items():
        artifacts = entry.get("artifacts") or {}
        for path, pair in THAW_FILES.items():
            if path not in artifacts:
                continue
            current = str(artifacts[path])
            if current != pair["from_blob"]:
                raise NBAGroupStep2CloseoutFailure(
                    "NBA_STEP2_CLOSEOUT_FROZEN_ENTRY_BASELINE_DRIFT:" + str(checkpoint) + ":" + path
                )
            artifacts[path] = pair["to_blob"]

    rebased_unrelated = 0
    retained_thaws = []
    for grant in updated.get("active_thaws", []):
        if grant.get("thaw_id") == THAW_ID:
            continue
        kept = deepcopy(grant)
        for path, pair in THAW_FILES.items():
            other = (kept.get("files") or {}).get(path)
            if not isinstance(other, dict):
                continue
            before = str(other.get("from_blob") or "")
            after = str(other.get("to_blob") or "")
            if before == pair["from_blob"]:
                if after == pair["to_blob"]:
                    del kept["files"][path]
                else:
                    other["from_blob"] = pair["to_blob"]
                rebased_unrelated += 1
            elif before != pair["to_blob"]:
                raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_UNRELATED_THAW_BASELINE_DRIFT:" + path)
        if kept.get("files"):
            retained_thaws.append(kept)

    updated["active_thaws"] = retained_thaws
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["source_main_sha"] = MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)
    return updated, {
        "exact_entry": exact_entry,
        "rebased_unrelated_thaw_pairs": rebased_unrelated,
    }


def _freeze(client, backend: GithubRegistryBackend, registry: dict, merged_tree: dict) -> dict:
    updated, detail = _build_registry_after(registry, merged_tree)
    if updated == registry:
        return {
            "registry": registry,
            "already_frozen": True,
            **detail,
        }

    if client.branch_sha("main") != MAIN_SHA:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_MAIN_MOVED_BEFORE_FREEZE")
    current = backend.read_registry()
    validate_registry(current)
    if (
        int(current.get("revision") or -1) != EXPECTED_REGISTRY_REVISION
        or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH
    ):
        raise NBAGroupStep2CloseoutFailure("WAIT_NBA_STEP2_REGISTRY_CAS_CONFLICT")

    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        backend.branch,
        "registry: freeze NBA Spread Step2 site activation",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if readback != updated:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_REGISTRY_READBACK_MISMATCH")
    if client.branch_sha("main") != MAIN_SHA:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_MAIN_MOVED_AFTER_FREEZE")
    return {
        "registry": readback,
        "already_frozen": False,
        **detail,
    }


def execute(client):
    _assert_merge_and_gate(client)
    backend, registry = _read_registry(client)

    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        tree = client.tree_blobs(MAIN_SHA)
        expected = {
            "status": "FROZEN",
            "checkpoint_id": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "artifacts": dict(sorted({path: str(tree.get(path) or "") for path in WRITE_PATHS}.items())),
        }
        if existing != expected:
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_EXISTING_FREEZE_DRIFT")
        if any(item.get("thaw_id") == THAW_ID for item in registry.get("active_thaws", [])):
            raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_THAW_REMAINS_AFTER_FREEZE")
        return {
            "status": "GREEN",
            "decision": "NBA_SPREAD_STEP2_ALREADY_GREEN_FROZEN",
            "main_sha": MAIN_SHA,
            "candidate_sha": CANDIDATE_SHA,
            "freeze_token": FREEZE_TOKEN,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "lease_released": True,
            "duplicate_proofs": 0,
            "github_actions_fallback": 0,
        }

    validated, merged_tree = _assert_registry_prestate(client, registry)
    lease_id = _claim_lease(client, registry, validated)
    release = None
    try:
        frozen = _freeze(client, backend, registry, merged_tree)
    finally:
        release = _release_lease(client, lease_id)

    readback = frozen["registry"]
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != frozen["exact_entry"]:
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_FINAL_FREEZE_READBACK_MISMATCH")
    if any(item.get("thaw_id") == THAW_ID for item in readback.get("active_thaws", [])):
        raise NBAGroupStep2CloseoutFailure("NBA_STEP2_CLOSEOUT_FINAL_THAW_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "decision": "NBA_SPREAD_STEP2_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "artifact_count": len(WRITE_PATHS),
        "exact_gate_check_run_id": CHECK_RUN_ID,
        "exact_receipt_digest": RECEIPT_DIGEST,
        "rebased_unrelated_thaw_pairs": int(frozen["rebased_unrelated_thaw_pairs"]),
        "lease_id": lease_id,
        "lease_released": bool((release or {}).get("released")),
        "duplicate_proofs": 0,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.nba_spread_step2_postmerge_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV, "").strip() != "1":
            return
        try:
            result = execute(app.state.github_client)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        app.state.nba_spread_step2_postmerge_closeout = result
        print("NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT=" + json.dumps(result, sort_keys=True), flush=True)

    return app
