from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.canonical_completion_resolver_v1 import resolve_completion
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "nba-spread-step1-page-isolation-v1"
WORKSTREAM = "nba-spread-two-page-v1"
CANDIDATE_SHA = "649027cd36412d93857a483f4aee47ddac3c02b4"
PRODUCT_MERGE_SHA = "9a7afa1fe19d62eed444088a8e77ca6c45e0bfb1"
PROOF_ID = "nba-spread-step1-page-isolation-v1-649027cd36412d93-4cc8f1a645bec65e"
RECEIPT_DIGEST = "f5d407bbed53faf144dff4efc76c302a36f9afaf30354b23fdbf784ec5ebbc8e"
FREEZE_TOKEN = "NBA_SPREAD_STEP1_PAGE_ISOLATION_FROZEN"
LEDGER_PATH = "devsystem/task_ledgers/nba-spread-step1-page-isolation-v1.json"
FREEZE_PATHS = (
    "devsystem/execution_plans/nba-spread-step1-page-isolation-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step1-page-isolation-v1.json",
    LEDGER_PATH,
    "nba_spread_page_isolation_v1.py",
    "tests/test_nba_spread_page_isolation_v1.py",
)
EXPECTED_PREMERGE_ARTIFACTS = {
    "devsystem/execution_plans/nba-spread-step1-page-isolation-v1.json": "a32706bf7084af9b59f5ac178e34bac89902a8f7",
    "devsystem/runless_proof_plans/nba-spread-step1-page-isolation-v1.json": "b3fc1be0502a756f2290e9e39ba20ce90c86883f",
    LEDGER_PATH: "32a435d8a7aa5268a92eb5b282df07ed5787b30a",
    "nba_spread_page_isolation_v1.py": "2204e40efb2cf3202d346a3e1ff1cd33f99ce79b",
    "tests/test_nba_spread_page_isolation_v1.py": "77780af37775f7b867ea4facc7ea5cc4163bb6bc",
}
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-845FB9703F8FADD9302CA5A3"
LEASE_OWNER = "chatgpt:api2:nba-spread-step1-page-isolation-v1"


class NBASpreadStep1CloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise NBASpreadStep1CloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise NBASpreadStep1CloseoutFailure(label + "_DECODE_FAILED") from exc


def _read_json(client, path: str, ref: str, label: str) -> tuple[dict, str]:
    raw = client.content(path, ref=ref)
    return _decode_json(raw, label), str(raw.get("sha") or "")


def _read_receipt(client) -> dict:
    receipt, _ = _read_json(
        client,
        f"{RECEIPT_BASE}/{PROOF_ID}.json",
        RECEIPT_REF,
        "NBA_SPREAD_PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if str(receipt.get("proof_id") or "") != PROOF_ID:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_PROOF_ID_DRIFT")
    if str(receipt.get("task_id") or "") != TASK_ID:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_TASK_ID_DRIFT")
    if str(receipt.get("workstream") or "") != WORKSTREAM:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_WORKSTREAM_DRIFT")
    if str(receipt.get("candidate_sha") or "") != CANDIDATE_SHA:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != RECEIPT_DIGEST:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_RECEIPT_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_RECEIPT_NOT_GREEN")
    if dict(receipt.get("artifact_map") or {}) != EXPECTED_PREMERGE_ARTIFACTS:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_RECEIPT_ARTIFACT_DRIFT")
    return receipt


def _read_gate(client) -> dict:
    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + RECEIPT_DIGEST
    matches = []
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        app = run.get("app") or {}
        if (
            str(run.get("name") or "") == "runless-final-gate"
            and str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "").lower() == "success"
            and str(output.get("summary") or "") == expected_summary
            and int(app.get("id") or 0) == 5204253
        ):
            matches.append(run)
    if len(matches) != 1:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_RUNLESS_GATE_DRIFT")
    return {
        "name": "runless-final-gate",
        "conclusion": "success",
        "head_sha": CANDIDATE_SHA,
        "receipt_digest": RECEIPT_DIGEST,
        "check_id": matches[0].get("id"),
        "app_id": 5204253,
    }


def _assert_product_merge(client) -> None:
    if client.branch_sha("main") != PRODUCT_MERGE_SHA:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_MAIN_DRIFT_BEFORE_CLOSEOUT")
    commit = client.commit(PRODUCT_MERGE_SHA)
    parents = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if CANDIDATE_SHA not in parents:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_MERGE_LINEAGE_DRIFT")


def _artifacts(tree: dict[str, str]) -> dict[str, str]:
    out = {path: str(tree.get(path) or "") for path in FREEZE_PATHS}
    if any(not value for value in out.values()):
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_FREEZE_ARTIFACT_MISSING")
    return dict(sorted(out.items()))


def _assert_existing_frozen_intact(client, registry: dict, target_sha: str) -> None:
    validated = validate_registry(registry)
    old_tree = client.tree_blobs(str(registry["source_main_sha"]))
    target_tree = client.tree_blobs(target_sha)
    thaw_paths = {
        path
        for grant in (registry.get("active_thaws") or [])
        for path in (grant.get("files") or {})
    }
    for path in sorted(validated["artifacts"]):
        if path in thaw_paths:
            continue
        if str(old_tree.get(path) or "") != str(target_tree.get(path) or ""):
            raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_EXISTING_FROZEN_DELTA:" + path)


def _write_registry_entry(client, *, expected_registry: dict, source_sha: str, artifacts: dict[str, str], allow_rebind: bool) -> dict:
    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    if (
        int(current.get("revision") or -1) != int(expected_registry["revision"])
        or str(current.get("state_hash") or "") != str(expected_registry["state_hash"])
        or current.get("active_thaws", []) != expected_registry.get("active_thaws", [])
    ):
        raise NBASpreadStep1CloseoutFailure("WAIT_NBA_SPREAD_REGISTRY_CAS_CONFLICT")

    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": source_sha,
        "artifacts": artifacts,
    }
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None and not allow_rebind:
        if existing == exact_entry:
            return current
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_FREEZE_TOKEN_COLLISION")
    if existing is not None and allow_rebind:
        if str(existing.get("checkpoint_id") or "") != FREEZE_TOKEN:
            raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_REBIND_TOKEN_DRIFT")

    flattened = {}
    for token, entry in (current.get("entries") or {}).items():
        if token == FREEZE_TOKEN:
            continue
        flattened.update(entry.get("artifacts") or {})
    conflicts = sorted(path for path, blob in artifacts.items() if path in flattened and flattened[path] != blob)
    if conflicts:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))

    active_thaws = deepcopy(current.get("active_thaws", []))
    thaw_paths = {path for grant in active_thaws for path in (grant.get("files") or {})}
    overlap = sorted(set(artifacts) & thaw_paths)
    if overlap:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_ACTIVE_THAW_OVERLAP:" + ",".join(overlap))

    updated = deepcopy(current)
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["source_main_sha"] = source_sha
    updated["revision"] = int(current["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)

    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        backend.branch,
        ("registry: rebind " if allow_rebind else "registry: freeze ") + FREEZE_TOKEN,
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if (
        int(readback["revision"]) != int(updated["revision"])
        or str(readback["state_hash"]) != str(updated["state_hash"])
        or readback.get("active_thaws", []) != active_thaws
        or (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry
    ):
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_REGISTRY_READBACK_MISMATCH")
    return readback


def _heal_ledger(client, *, canonical: dict) -> tuple[dict, str]:
    raw = client.content(LEDGER_PATH, ref="main")
    ledger = _decode_json(raw, "NBA_SPREAD_LEDGER")
    if str(ledger.get("task_id") or "") != TASK_ID:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEDGER_IDENTITY_DRIFT")
    healed = deepcopy(ledger)
    healed["state"] = "DONE"
    healed["status"] = "DONE"
    healed["green_plus_frozen_claimed"] = True
    healed["next_legal_action"] = "NONE_TERMINAL"
    healed["freeze_exit"] = {"claimed": True, "frozen_token": FREEZE_TOKEN}
    healed["tdd"]["exact_head_runless_result"] = "MERGE_AUTHORIZED"
    healed["runless"]["proof_id"] = PROOF_ID
    healed["runless"]["receipt_digest"] = RECEIPT_DIGEST
    healed["runless"]["successful_exact_head_runs"] = 1
    healed["acceptance"]["exact_head_runless_green"] = True
    healed["acceptance"]["merged_main_verified"] = True
    healed["acceptance"]["frozen_verified"] = True
    healed["finalization"] = {
        "authority": "FROZEN_REGISTRY_RUNLESS",
        "candidate_sha": CANDIDATE_SHA,
        "product_merge_sha": PRODUCT_MERGE_SHA,
        "initial_registry_revision": canonical.get("registry_revision"),
        "initial_registry_state_hash": canonical.get("registry_state_hash"),
        "receipt_digest": RECEIPT_DIGEST,
        "runless_gate": "SUCCESS",
        "github_actions_fallback": 0,
    }
    response = client.update_content(
        LEDGER_PATH,
        json.dumps(healed, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        "main",
        "NBA Spread Step 1 — terminal ledger closeout",
        str(raw.get("sha") or ""),
    )
    final_sha = str(((response or {}).get("commit") or {}).get("sha") or "")
    if len(final_sha) != 40:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEDGER_COMMIT_SHA_MISSING")
    if client.branch_sha("main") != final_sha:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEDGER_MAIN_READBACK_DRIFT")
    commit = client.commit(final_sha)
    parents = [str(item.get("sha") or "") for item in (commit.get("parents") or [])]
    if parents != [PRODUCT_MERGE_SHA]:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEDGER_CLOSEOUT_PARENT_DRIFT")
    compare = client.request("GET", f"/compare/{PRODUCT_MERGE_SHA}...{final_sha}") or {}
    changed = sorted(str(item.get("filename") or "") for item in (compare.get("files") or []))
    if changed != [LEDGER_PATH]:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEDGER_CLOSEOUT_SCOPE_DRIFT:" + ",".join(changed))
    readback, _ = _read_json(client, LEDGER_PATH, final_sha, "NBA_SPREAD_LEDGER_READBACK")
    if readback != healed:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEDGER_READBACK_MISMATCH")
    return healed, final_sha


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_scope_lease_state(_decode_json(raw, "NBA_SPREAD_LEASE"))
    before = list(state.get("holders") or [])
    remaining = [
        holder for holder in before
        if not (
            str(holder.get("lease_id") or "") == LEASE_ID
            and str(holder.get("owner_id") or "") == LEASE_OWNER
        )
    ]
    if len(remaining) == len(before):
        return {"released": False, "already_absent": True, "revision": int(state["revision"]), "state_hash": str(state["state_hash"])}
    updated = deepcopy(state)
    updated["holders"] = remaining
    updated["revision"] = int(state["revision"]) + 1
    updated.pop("state_hash", None)
    canonical = json.dumps(updated, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    updated["state_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    validate_scope_lease_state(updated)
    client.update_content(
        LEASE_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: release NBA Spread Step1 finalization authority",
        str(raw.get("sha") or ""),
    )
    readback, _ = _read_json(client, LEASE_PATH, LEASE_REF, "NBA_SPREAD_LEASE_READBACK")
    validated = validate_scope_lease_state(readback)
    if any(str(item.get("lease_id") or "") == LEASE_ID for item in validated.get("holders") or []):
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_LEASE_RELEASE_READBACK_MISMATCH")
    return {"released": True, "already_absent": False, "revision": int(validated["revision"]), "state_hash": str(validated["state_hash"])}


def execute(client) -> dict:
    _assert_product_merge(client)
    receipt = _read_receipt(client)
    gate = _read_gate(client)

    backend = GithubRegistryBackend(client)
    registry_before = backend.read_registry()
    _assert_existing_frozen_intact(client, registry_before, PRODUCT_MERGE_SHA)
    product_tree = client.tree_blobs(PRODUCT_MERGE_SHA)
    product_artifacts = _artifacts(product_tree)
    if product_artifacts != EXPECTED_PREMERGE_ARTIFACTS:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_PRODUCT_ARTIFACT_DRIFT")

    initial_registry = _write_registry_entry(
        client,
        expected_registry=registry_before,
        source_sha=PRODUCT_MERGE_SHA,
        artifacts=product_artifacts,
        allow_rebind=False,
    )
    initial_canonical = resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=_decode_json(client.content(LEDGER_PATH, ref=PRODUCT_MERGE_SHA), "NBA_SPREAD_LEDGER_PREHEAL"),
        registry=initial_registry,
        receipt=receipt,
        gate=gate,
        merge_evidence={
            "contains_candidate": True,
            "candidate_sha": CANDIDATE_SHA,
            "merged_main_sha": PRODUCT_MERGE_SHA,
        },
    )
    if initial_canonical.get("complete") is not True or initial_canonical.get("ledger_stale") is not True:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_INITIAL_CANONICAL_NOT_READY")

    healed_ledger, final_main_sha = _heal_ledger(client, canonical=initial_canonical)
    final_tree = client.tree_blobs(final_main_sha)
    final_artifacts = _artifacts(final_tree)
    for path, blob in product_artifacts.items():
        if path == LEDGER_PATH:
            continue
        if final_artifacts.get(path) != blob:
            raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_FINALIZATION_SCOPE_DRIFT:" + path)
    if final_artifacts[LEDGER_PATH] == product_artifacts[LEDGER_PATH]:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_TERMINAL_LEDGER_BLOB_DID_NOT_ADVANCE")

    registry_for_rebind = backend.read_registry()
    final_registry = _write_registry_entry(
        client,
        expected_registry=registry_for_rebind,
        source_sha=final_main_sha,
        artifacts=final_artifacts,
        allow_rebind=True,
    )

    compare = client.request("GET", f"/compare/{CANDIDATE_SHA}...{final_main_sha}") or {}
    if str(compare.get("status") or "") not in {"ahead", "identical"}:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_FINAL_MAIN_DOES_NOT_CONTAIN_CANDIDATE")
    final_canonical = resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=healed_ledger,
        registry=final_registry,
        receipt=receipt,
        gate=gate,
        merge_evidence={
            "contains_candidate": True,
            "candidate_sha": CANDIDATE_SHA,
            "merged_main_sha": final_main_sha,
        },
    )
    if (
        final_canonical.get("complete") is not True
        or final_canonical.get("status") != "GREEN_FROZEN"
        or final_canonical.get("ledger_stale") is not False
    ):
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_FINAL_CANONICAL_NOT_TERMINAL")

    lease = _release_lease(client)
    if client.branch_sha("main") != final_main_sha:
        raise NBASpreadStep1CloseoutFailure("NBA_SPREAD_MAIN_MOVED_AFTER_FINALIZATION")

    return {
        "status": "GREEN_FROZEN",
        "decision": "NBA_SPREAD_STEP1_GREEN_FROZEN",
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": CANDIDATE_SHA,
        "product_merge_sha": PRODUCT_MERGE_SHA,
        "final_main_sha": final_main_sha,
        "proof_id": PROOF_ID,
        "receipt_digest": RECEIPT_DIGEST,
        "freeze_token": FREEZE_TOKEN,
        "artifact_count": len(final_artifacts),
        "registry_revision": int(final_registry["revision"]),
        "registry_state_hash": str(final_registry["state_hash"]),
        "ledger_stale": bool(final_canonical.get("ledger_stale")),
        "canonical_authority": str(final_canonical.get("authority") or ""),
        "lease": lease,
        "github_actions_fallback": 0,
        "duplicate_successful_proofs": 0,
    }


def run_and_print(client):
    try:
        result = execute(client)
    except Exception as exc:
        result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:1800]}
    print("NBA_SPREAD_STEP1_CLOSEOUT=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    return result
