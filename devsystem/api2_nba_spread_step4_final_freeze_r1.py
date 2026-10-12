from __future__ import annotations

import base64
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.canonical_completion_resolver_v1 import resolve_completion
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt

TASK_ID = "nba-spread-step4-most-bet-feature-v1"
FREEZE_TOKEN = "NBA_SPREAD_STEP4_MOST_BET_FEATURE_FROZEN"
STEP4_THAW_ID = "THAW-NBA-SPREAD-STEP4-MOST-BET-FEATURE-R1"
CERTIFIED_CANDIDATE = "89a3ba98da2cc611093e32f8af20eab05f6faebc"
MERGED_MAIN_SHA = "38954c48c35534428cdd09442ba28a58cd8536bd"
CURRENT_REVISION = 299
CURRENT_HASH = "855f9e2950252812f235033dc53af5b0c80a94cf378a2f30753e6ac7d1354d54"
OLD_PAGE_BLOB = "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0"
NEW_PAGE_BLOB = "0ad62af70010051c3ac8f4477d63263a228eb76b"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EVIDENCE_PATH = Path("devsystem/finalization_evidence/nba-spread-step4-most-bet-feature-v1.json")
LEDGER_PATH = Path("devsystem/task_ledgers/nba-spread-step4-most-bet-feature-v1.json")

STEP4_ARTIFACTS = {
    "devsystem/execution_plans/nba-spread-step4-most-bet-feature-v1.json": "583c411a1205a69fc93d48a53709f9a21ae7d172",
    "devsystem/runless_proof_plans/nba-spread-step4-most-bet-feature-v1.json": "786cd3794964754467e71bc81da1af1bcc6b19d0",
    "devsystem/task_ledgers/nba-spread-step4-most-bet-feature-v1.json": "a733ad2bd6bb0e4a1810845085b2c9dabe29c6ec",
    "nba_spread_most_bet_v1.py": "7366bdcce48c0ba251c2b297cdbe0eb4d02b71e1",
    "nba_spread_page_v1.py": NEW_PAGE_BLOB,
    "tests/test_nba_spread_step4_most_bet_v1.py": "2c82d25fae5664281f82820a518b1f7804e984f1",
}


class Step4FinalFreezeFailure(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise Step4FinalFreezeFailure(code)


def validate_public_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if str(evidence.get("merged_main_sha") or "") != MERGED_MAIN_SHA:
        _fail("PUBLIC_MAIN_IDENTITY")
    if int(evidence.get("backend_health_status") or 0) != 200:
        _fail("PUBLIC_BACKEND_HEALTH")
    if str(evidence.get("backend_health_content") or "").strip().lower() != "ok":
        _fail("PUBLIC_BACKEND_HEALTH")
    if evidence.get("websocket_opened") is not True or int(evidence.get("websocket_frame_count") or 0) <= 0:
        _fail("PUBLIC_WEBSOCKET_NOT_LIVE")
    found = evidence.get("found")
    if not isinstance(found, Mapping):
        _fail("PUBLIC_EVIDENCE_MALFORMED")
    for required in (
        "nba-spread-step4-most-bet-active",
        "NBA Spread",
        "Phoenix, Arizona",
        "nba-spread-step3-schedule-active",
    ):
        if found.get(required) is not True:
            _fail("PUBLIC_REQUIRED_MARKER_MISSING")
    forbidden = evidence.get("forbidden")
    if not isinstance(forbidden, Mapping):
        _fail("PUBLIC_EVIDENCE_MALFORMED")
    if any(bool(forbidden.get(label)) for label in ("Sharp Money Game", "Kyre Fair Spread", "Cover Probability")):
        _fail("PUBLIC_STEP5_LEAKAGE")
    return {"status": "GREEN", "decision": "PUBLIC_PRODUCTION_GREEN", "frame_count": int(evidence["websocket_frame_count"])}


def _assert_step4_thaw(registry: Mapping[str, Any]) -> None:
    matches = [item for item in registry.get("active_thaws", []) if item.get("thaw_id") == STEP4_THAW_ID]
    if len(matches) != 1:
        _fail("STEP4_THAW_COUNT")
    grant = matches[0]
    expected_files = {"nba_spread_page_v1.py": {"from_blob": OLD_PAGE_BLOB, "to_blob": NEW_PAGE_BLOB}}
    if grant.get("status") != "ACTIVE" or grant.get("target_head_sha") != CERTIFIED_CANDIDATE or grant.get("files") != expected_files:
        _fail("STEP4_THAW_IDENTITY")


def build_final_registry(payload: Mapping[str, Any], *, require_authoritative_identity: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = deepcopy(dict(payload))
    validate_registry(registry)
    if require_authoritative_identity:
        if int(registry.get("revision", -1)) != CURRENT_REVISION:
            _fail("CURRENT_REVISION")
        if str(registry.get("state_hash") or "") != CURRENT_HASH:
            _fail("CURRENT_HASH")
    _assert_step4_thaw(registry)
    if FREEZE_TOKEN in registry["entries"]:
        _fail("FREEZE_TOKEN_ALREADY_PRESENT")

    plan = plan_baseline_forward_port(
        registry,
        updates={"nba_spread_page_v1.py": {"from_blob": OLD_PAGE_BLOB, "to_blob": NEW_PAGE_BLOB}},
        source_main_sha=MERGED_MAIN_SHA,
    )
    target = deepcopy(plan["registry"])
    updated = {(item["checkpoint"], item["path"]) for item in plan["updated_entries"]}
    expected_updates = {
        ("NBA_SPREAD_STEP2_SITE_ACTIVATION_FROZEN", "nba_spread_page_v1.py"),
        ("NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN", "nba_spread_page_v1.py"),
    }
    if updated != expected_updates:
        _fail("SHARED_BASELINE_FORWARD_PORT_SCOPE")
    if plan["retired_empty_thaw_grants"] != [STEP4_THAW_ID]:
        _fail("STEP4_THAW_NOT_RETIRED")

    target["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_MAIN_SHA,
        "artifacts": deepcopy(STEP4_ARTIFACTS),
    }
    target["state_hash"] = _hash(_payload_without_hash(target))
    validate_registry(target)
    return target, plan


def _decode(raw: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not raw or raw.get("encoding") != "base64" or not raw.get("sha"):
        _fail("REGISTRY_READ_FAILED")
    try:
        text = base64.b64decode(str(raw["content"])).decode("utf-8")
        return json.loads(text), text
    except Exception as exc:
        raise Step4FinalFreezeFailure("REGISTRY_DECODE_FAILED") from exc


def execute() -> dict[str, Any]:
    from runless_proof_plane.config import Settings
    from runless_proof_plane.github_app import GithubAppAuth
    from runless_proof_plane.github_client import GithubClient

    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    if str(evidence.get("task_id") or "") != TASK_ID or str(evidence.get("freeze_token") or "") != FREEZE_TOKEN:
        _fail("FINALIZATION_EVIDENCE_IDENTITY")
    if int(evidence.get("github_actions_fallback", -1)) != 0:
        _fail("GITHUB_ACTIONS_FALLBACK_USED")
    public = validate_public_evidence(evidence.get("public_production") or {})
    receipt = evidence.get("runless_receipt") or {}
    validate_runless_receipt(receipt)
    gate = evidence.get("runless_gate") or {}
    if gate.get("app_id") != 5204253 or gate.get("conclusion") != "success" or gate.get("head_sha") != CERTIFIED_CANDIDATE:
        _fail("RUNLESS_GATE_IDENTITY")

    settings = Settings.from_env()
    client = GithubClient(GithubAppAuth(settings), settings.repository)
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        _fail("MAIN_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current, _ = _decode(raw)
    target, plan = build_final_registry(current, require_authoritative_identity=True)
    target_text = json.dumps(target, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    update = client.update_content(
        REGISTRY_PATH,
        target_text,
        REGISTRY_BRANCH,
        "registry: freeze NBA Spread Step4 Most Bet Game",
        str(raw["sha"]),
    )

    readback_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    readback, readback_text = _decode(readback_raw)
    validate_registry(readback)
    if readback != target or readback_text != target_text:
        _fail("REGISTRY_READBACK_MISMATCH")
    if STEP4_THAW_ID in {item["thaw_id"] for item in readback["active_thaws"]}:
        _fail("STEP4_THAW_STILL_ACTIVE")
    if FREEZE_TOKEN not in readback["entries"]:
        _fail("FREEZE_TOKEN_MISSING")

    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    completion = resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=ledger,
        registry=readback,
        receipt=receipt,
        gate={
            "name": str(gate.get("name") or ""),
            "conclusion": str(gate.get("conclusion") or ""),
            "head_sha": str(gate.get("head_sha") or ""),
            "receipt_digest": str(gate.get("receipt_digest") or ""),
        },
        merge_evidence=evidence.get("merge_evidence") or {},
    )
    if completion.get("complete") is not True or completion.get("decision") != "CANONICAL_GREEN_FROZEN":
        _fail("FINALIZATION_AUTHORITY_BLOCKED")

    return {
        "status": "GREEN_FROZEN",
        "decision": "CANONICAL_GREEN_FROZEN",
        "authority": completion["authority"],
        "freeze_token": FREEZE_TOKEN,
        "candidate_sha": CERTIFIED_CANDIDATE,
        "merged_main_sha": MERGED_MAIN_SHA,
        "runless_receipt_digest": str(receipt["digest"]),
        "public_production": public,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "registry_commit_sha": str((update.get("commit") or {}).get("sha") or ""),
        "registry_blob_sha": str((readback_raw or {}).get("sha") or ""),
        "retired_step4_thaw": STEP4_THAW_ID,
        "forward_ported_entry_count": len(plan["updated_entries"]),
        "unrelated_thaws_preserved": len(readback["active_thaws"]),
        "ledger_stale": bool(completion.get("ledger_stale")),
        "github_actions_fallback": 0,
        "next_legal_action": "NONE_TERMINAL",
    }


def main() -> int:
    print("API2_NBA_SPREAD_STEP4_FINAL=" + json.dumps(execute(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
