from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry

from .registry import GithubRegistryBackend, REGISTRY_PATH

FREEZE_TOKEN = "NBA_SPREAD_STEP1_PAGE_ISOLATION_FROZEN"
PRODUCT_MAIN_SHA = "9a7afa1fe19d62eed444088a8e77ca6c45e0bfb1"
TERMINAL_BRANCH = "nba-spread-step1-terminal-ledger-r1"
TERMINAL_CANDIDATE_SHA = "7b5f39eb22802b836788955bc1229e68474914bb"
LEDGER_PATH = "devsystem/task_ledgers/nba-spread-step1-page-isolation-v1.json"
OLD_LEDGER_BLOB = "32a435d8a7aa5268a92eb5b282df07ed5787b30a"
NEW_LEDGER_BLOB = "b17c731ba35631428e94e9241a51eeffd4d73987"
THAW_ID = "THAW-NBA-SPREAD-STEP1-TERMINAL-LEDGER-R1"
EXPECTED_PRODUCT_ARTIFACTS = {
    "devsystem/execution_plans/nba-spread-step1-page-isolation-v1.json": "a32706bf7084af9b59f5ac178e34bac89902a8f7",
    "devsystem/runless_proof_plans/nba-spread-step1-page-isolation-v1.json": "b3fc1be0502a756f2290e9e39ba20ce90c86883f",
    LEDGER_PATH: OLD_LEDGER_BLOB,
    "nba_spread_page_isolation_v1.py": "2204e40efb2cf3202d346a3e1ff1cd33f99ce79b",
    "tests/test_nba_spread_page_isolation_v1.py": "77780af37775f7b867ea4facc7ea5cc4163bb6bc",
}


class NBASpreadTerminalFinalizationFailure(RuntimeError):
    pass


def _exact_entry(source_sha: str, artifacts: dict[str, str]) -> dict:
    return {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": source_sha,
        "artifacts": dict(sorted(artifacts.items())),
    }


def _write_registry(client, *, before: dict, after: dict, message: str) -> dict:
    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    if (
        int(current.get("revision") or -1) != int(before["revision"])
        or str(current.get("state_hash") or "") != str(before["state_hash"])
    ):
        raise NBASpreadTerminalFinalizationFailure("WAIT_NBA_SPREAD_REGISTRY_CAS_CONFLICT")
    client.update_content(
        REGISTRY_PATH,
        json.dumps(after, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        backend.branch,
        message,
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if (
        int(readback["revision"]) != int(after["revision"])
        or str(readback["state_hash"]) != str(after["state_hash"])
        or readback.get("entries") != after.get("entries")
        or readback.get("active_thaws") != after.get("active_thaws")
        or str(readback.get("source_main_sha") or "") != str(after.get("source_main_sha") or "")
    ):
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_REGISTRY_READBACK_MISMATCH")
    return readback


def prepare(client) -> dict:
    if client.branch_sha("main") != PRODUCT_MAIN_SHA:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_PREPARE_MAIN_DRIFT")
    if client.branch_sha(TERMINAL_BRANCH) != TERMINAL_CANDIDATE_SHA:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_BRANCH_DRIFT")
    compare = client.request("GET", f"/compare/{PRODUCT_MAIN_SHA}...{TERMINAL_CANDIDATE_SHA}") or {}
    files = sorted(str(item.get("filename") or "") for item in (compare.get("files") or []))
    if files != [LEDGER_PATH]:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_SCOPE_DRIFT:" + ",".join(files))

    tree = client.tree_blobs(TERMINAL_CANDIDATE_SHA)
    if str(tree.get(LEDGER_PATH) or "") != NEW_LEDGER_BLOB:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_LEDGER_BLOB_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != PRODUCT_MAIN_SHA:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_PREPARE_REGISTRY_MAIN_DRIFT")
    entry = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if entry != _exact_entry(PRODUCT_MAIN_SHA, EXPECTED_PRODUCT_ARTIFACTS):
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_PREPARE_FREEZE_ENTRY_DRIFT")

    exact_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": TERMINAL_CANDIDATE_SHA,
        "files": {
            LEDGER_PATH: {
                "from_blob": OLD_LEDGER_BLOB,
                "to_blob": NEW_LEDGER_BLOB,
            }
        },
    }
    existing = [item for item in (registry.get("active_thaws") or []) if str(item.get("thaw_id") or "") == THAW_ID]
    if existing:
        if existing != [exact_grant]:
            raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_THAW_COLLISION")
        return {
            "status": "GREEN",
            "decision": "NBA_SPREAD_TERMINAL_THAW_ALREADY_ACTIVE",
            "thaw_id": THAW_ID,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "candidate_sha": TERMINAL_CANDIDATE_SHA,
        }

    for grant in registry.get("active_thaws") or []:
        if LEDGER_PATH in (grant.get("files") or {}):
            raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_LEDGER_ALREADY_THAWED")

    updated = deepcopy(registry)
    updated["active_thaws"] = list(updated.get("active_thaws") or []) + [exact_grant]
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)
    readback = _write_registry(
        client,
        before=registry,
        after=updated,
        message="registry: authorize NBA Spread Step1 terminal ledger thaw",
    )
    return {
        "status": "GREEN",
        "decision": "NBA_SPREAD_TERMINAL_THAW_ACTIVE",
        "thaw_id": THAW_ID,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "candidate_sha": TERMINAL_CANDIDATE_SHA,
        "active_thaw_count": len(readback.get("active_thaws") or []),
    }


def finalize(client, final_main_sha: str) -> dict:
    final_sha = str(final_main_sha or "").strip().lower()
    if len(final_sha) != 40:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_FINAL_MAIN_SHA_REQUIRED")
    if client.branch_sha("main") != final_sha:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_FINAL_MAIN_DRIFT")
    compare = client.request("GET", f"/compare/{TERMINAL_CANDIDATE_SHA}...{final_sha}") or {}
    if str(compare.get("status") or "") not in {"ahead", "identical"}:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_FINAL_MAIN_MISSING_TERMINAL_CANDIDATE")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    grants = [item for item in (registry.get("active_thaws") or []) if str(item.get("thaw_id") or "") == THAW_ID]
    if len(grants) != 1:
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_THAW_NOT_ACTIVE")
    grant = grants[0]
    pair = (grant.get("files") or {}).get(LEDGER_PATH) or {}
    if (
        str(grant.get("target_head_sha") or "") != TERMINAL_CANDIDATE_SHA
        or str(pair.get("from_blob") or "") != OLD_LEDGER_BLOB
        or str(pair.get("to_blob") or "") != NEW_LEDGER_BLOB
    ):
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_THAW_DRIFT")

    tree = client.tree_blobs(final_sha)
    final_artifacts = {path: str(tree.get(path) or "") for path in EXPECTED_PRODUCT_ARTIFACTS}
    if any(not value for value in final_artifacts.values()):
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_FINAL_ARTIFACT_MISSING")
    for path, old_blob in EXPECTED_PRODUCT_ARTIFACTS.items():
        if path == LEDGER_PATH:
            if final_artifacts[path] != NEW_LEDGER_BLOB:
                raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_FINAL_LEDGER_BLOB_DRIFT")
        elif final_artifacts[path] != old_blob:
            raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_FINAL_PRODUCT_SCOPE_DRIFT:" + path)

    updated = deepcopy(registry)
    updated["entries"][FREEZE_TOKEN] = _exact_entry(final_sha, final_artifacts)
    updated["active_thaws"] = [item for item in updated.get("active_thaws") or [] if str(item.get("thaw_id") or "") != THAW_ID]
    updated["source_main_sha"] = final_sha
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)
    readback = _write_registry(
        client,
        before=registry,
        after=updated,
        message="registry: finalize NBA Spread Step1 terminal ledger freeze",
    )
    if any(str(item.get("thaw_id") or "") == THAW_ID for item in readback.get("active_thaws") or []):
        raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_THAW_RELEASE_FAILED")
    return {
        "status": "GREEN_FROZEN",
        "decision": "NBA_SPREAD_TERMINAL_REGISTRY_REBOUND",
        "freeze_token": FREEZE_TOKEN,
        "final_main_sha": final_sha,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "artifact_count": len(final_artifacts),
        "active_thaw_count": len(readback.get("active_thaws") or []),
        "thaw_removed": True,
    }


def run_and_print(client, mode: str, final_main_sha: str = ""):
    try:
        if mode == "prepare":
            result = prepare(client)
        elif mode == "finalize":
            result = finalize(client, final_main_sha)
        else:
            raise NBASpreadTerminalFinalizationFailure("NBA_SPREAD_TERMINAL_MODE_INVALID")
    except Exception as exc:
        result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:1800], "mode": mode}
    print("NBA_SPREAD_TERMINAL_FINALIZATION=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    return result
