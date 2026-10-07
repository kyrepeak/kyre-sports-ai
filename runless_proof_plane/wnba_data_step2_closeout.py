from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "4036459c8c8cde0ac8f3034b560d7948ad9a5015"
RUNLESS_APP_ID = 5204253
FREEZE_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN"
EXPECTED_REGISTRY_REVISION = 155
EXPECTED_REGISTRY_HASH = "a6d78addded88918cb13c08055acd37a5afcd2808c08f402f2866a46170bf372"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
PUBLIC_PROOF_DEPLOY = "dep-db2s8a0m7kps73c4j1cg"
PUBLIC_PROOF_FACTS = {
    "players": 29,
    "game_center_green": True,
    "rc": 0,
    "breanna_stewart_reb": 6.4,
    "breanna_stewart_pra": 26.7,
    "sabrina_ionescu_reb": 2.3,
    "jonquel_jones_reb": 7.3,
    "angel_reese_reb": 9.2,
}

REQUIRED_GATES = (
    ("54e3fe375cb22fc53c844ba50bb6dd04f45e7482", "d368aea00b2cf498835d00df3d827ae4128f083e2037c18bc9c14df7b001bce9"),
    ("786d3042e5c3392edc3a40218520aff5d9e1a934", "5827754a4d1f114b3f6677b2b68d6e22c20c8e6a88743d0472c70797ea22b71f"),
    ("1735d5871030c5aab2143edeed07a0b39877e4c8", "df1884e4e985182b2a5b4156c9bf4271cbe64e2dd6de8517c414ce10a04c23eb"),
    ("9bedbdd848985c42c691018a0952142714f3bf43", "0e15afb94177f9f5130683da03ee8199b4949285ff44aa6cb1d6510a2865a88f"),
)

STEP2_THAWS = {
    "THAW-API2-WNBA-DATA-STEP2-LIVE-HYDRATION-R2": {
        "target_head_sha": "54e3fe375cb22fc53c844ba50bb6dd04f45e7482",
        "files": {
            "wnba_players_v25.py": {
                "from_blob": "9960efb20d9e6f3791ed5c3228ca42abd884f828",
                "to_blob": "13055f7bc06a8af369daba47453e92fe7e6c8ea7",
            }
        },
    },
    "THAW-API2-WNBA-DATA-STEP2-SELECTED-DAY-HANDOFF-R1": {
        "target_head_sha": "786d3042e5c3392edc3a40218520aff5d9e1a934",
        "files": {
            "wnba_availability_v27.py": {
                "from_blob": "82468c9b603947c052e726cd8beb9ba1b05b2484",
                "to_blob": "4cdb65b9fd7942865ad17e7b27e29fb815192de1",
            }
        },
    },
    "THAW-API2-WNBA-DATA-STEP2-STREAMLIT-REFRESH-R1": {
        "target_head_sha": "9bedbdd848985c42c691018a0952142714f3bf43",
        "files": {
            "requirements.txt": {
                "from_blob": "98b621afd372d472784850fed4b603c9989dcf7a",
                "to_blob": "7f5cf407662a79cb4c56781195e7bbcaca38d315",
            }
        },
    },
}

ARTIFACT_PATHS = tuple(sorted((
    "wnba_players_v25.py",
    "wnba_availability_v27.py",
    "wnba_data_completeness_repair_v1_step2_stats_gate.py",
    "wnba_data_completeness_repair_v1_step2_live_history.py",
    "sports_api/wnba_pra_speed_v3_step3_espn_history.py",
    "requirements.txt",
    "tests/test_wnba_data_completeness_repair_v1_step2.py",
    "tests/test_wnba_data_completeness_repair_v1_step2_live_history.py",
    "tests/test_wnba_data_completeness_repair_v1_step2_selected_day_handoff.py",
    "tests/test_wnba_data_completeness_repair_v1_step2_rebound_alias.py",
    "devsystem/wnba_data_completeness_repair_v1_step2_player_game_stats_cert.py",
    "devsystem/wnba_data_completeness_repair_v1_step2_selected_day_handoff_cert.py",
    "devsystem/wnba_data_completeness_repair_v1_step2_rebound_alias_cert.py",
    "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-player-game-stats.json",
    "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-selected-day-handoff.json",
    "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-rebound-alias.json",
    "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-player-game-stats.json",
    "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-selected-day-handoff.json",
    "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-rebound-alias.json",
)))


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP2_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_gate(client, sha: str, receipt: str) -> int:
    checks = client.request("GET", f"/commits/{sha}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == sha
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={receipt}"
        ):
            return int(check["id"])
    raise RuntimeError("WNBA_DATA_STEP2_REQUIRED_RUNLESS_GATE_MISSING:" + sha)


def _verify_identity(client):
    if str(client.branch_sha("main")).lower() != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_MAIN_SHA_DRIFT")
    gate_ids = {sha: _require_gate(client, sha, receipt) for sha, receipt in REQUIRED_GATES}
    tree = client.tree_blobs(MAIN_SHA)
    artifacts = {path: str(tree.get(path) or "") for path in ARTIFACT_PATHS}
    missing = [path for path, blob in artifacts.items() if len(blob) != 40]
    if missing:
        raise RuntimeError("WNBA_DATA_STEP2_FINAL_ARTIFACT_MISSING:" + ",".join(missing))
    for spec in STEP2_THAWS.values():
        for path, pair in spec["files"].items():
            if artifacts.get(path) != pair["to_blob"]:
                raise RuntimeError("WNBA_DATA_STEP2_FINAL_BLOB_DRIFT:" + path)
    owner_text = base64.b64decode((client.content("wnba_availability_v27.py", ref=MAIN_SHA) or {}).get("content", "")).decode()
    if "raw, _ = players._build_selected_player_pool(day_str)" not in owner_text:
        raise RuntimeError("WNBA_DATA_STEP2_SELECTED_DAY_HANDOFF_MISSING")
    rebound_text = base64.b64decode((client.content("sports_api/wnba_pra_speed_v3_step3_espn_history.py", ref=MAIN_SHA) or {}).get("content", "")).decode()
    if '"totalRebounds"' not in rebound_text:
        raise RuntimeError("WNBA_DATA_STEP2_TOTAL_REBOUNDS_ALIAS_MISSING")
    return artifacts, gate_ids


def _publish_main_gate(client, artifacts, gate_ids):
    evidence = {
        "main_sha": MAIN_SHA,
        "artifacts": artifacts,
        "required_gate_ids": gate_ids,
        "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
        "public_proof_facts": PUBLIC_PROOF_FACTS,
        "selected_day_handoff": True,
        "total_rebounds_alias": True,
        "public_nonzero_rebounds": True,
        "public_corrected_pra": True,
        "navigation_changed": False,
        "projection_math_changed": False,
        "probability_changed": False,
        "market_changed": False,
        "other_sports_changed": 0,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step2-final-{MAIN_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-final-closeout",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2",
        step="2/3-final-freeze-closeout",
        candidate_sha=MAIN_SHA,
        artifact_map=artifacts,
        dependency_map={
            "github_actions_fallback": False,
            "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
            "required_runless_heads": [sha for sha, _ in REQUIRED_GATES],
        },
        registry_before={"revision": EXPECTED_REGISTRY_REVISION, "state_hash": EXPECTED_REGISTRY_HASH},
        registry_after={"freeze_token": FREEZE_TOKEN, "mode": "atomic_forward_port_and_retire_step2_thaws"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, MAIN_SHA, "success", receipt)
    return int(check["id"]), str(receipt["digest"])


def _freeze_registry(client, artifacts, check_id: int, receipt_digest: str):
    current, content_sha = _read_registry(client)
    if int(current.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
    if str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")

    current_thaws = deepcopy(list(current.get("active_thaws") or []))
    step2 = {str(g.get("thaw_id") or ""): g for g in current_thaws if str(g.get("thaw_id") or "").startswith("THAW-API2-WNBA-DATA-STEP2-")}
    if set(step2) != set(STEP2_THAWS):
        raise RuntimeError("WNBA_DATA_STEP2_THAW_SET_DRIFT:" + ",".join(sorted(step2)))
    for thaw_id, spec in STEP2_THAWS.items():
        grant = step2[thaw_id]
        expected = {"thaw_id": thaw_id, "status": "ACTIVE", "target_head_sha": spec["target_head_sha"], "files": spec["files"]}
        if grant != expected:
            raise RuntimeError("WNBA_DATA_STEP2_EXACT_THAW_DRIFT:" + thaw_id)

    unrelated_before = [deepcopy(g) for g in current_thaws if str(g.get("thaw_id") or "") not in STEP2_THAWS]
    updated = deepcopy(current)

    # Forward-port every frozen owner of each thawed path to its final blob.
    for spec in STEP2_THAWS.values():
        for path, pair in spec["files"].items():
            owners = 0
            for entry in (updated.get("entries") or {}).values():
                amap = entry.get("artifacts") or {}
                if path in amap:
                    if str(amap[path]) != pair["from_blob"]:
                        raise RuntimeError("WNBA_DATA_STEP2_FROZEN_BASELINE_DRIFT:" + path)
                    amap[path] = pair["to_blob"]
                    owners += 1
            if owners == 0:
                raise RuntimeError("WNBA_DATA_STEP2_FROZEN_OWNER_MISSING:" + path)

    updated["active_thaws"] = unrelated_before
    desired_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(artifacts),
    }
    updated.setdefault("entries", {})[FREEZE_TOKEN] = desired_entry
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(REGISTRY_PATH, text, REGISTRY_BRANCH, f"registry: freeze {FREEZE_TOKEN}", content_sha)
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc

    readback, _ = _read_registry(client)
    entry = (readback.get("entries") or {}).get(FREEZE_TOKEN) or {}
    if entry != desired_entry:
        raise RuntimeError("WNBA_DATA_STEP2_FREEZE_READBACK_MISMATCH")
    remaining_step2 = [g for g in readback.get("active_thaws", []) if str(g.get("thaw_id") or "").startswith("THAW-API2-WNBA-DATA-STEP2-")]
    if remaining_step2:
        raise RuntimeError("WNBA_DATA_STEP2_THAW_RETIRE_READBACK_FAILED")
    if list(readback.get("active_thaws") or []) != unrelated_before:
        raise RuntimeError("WNBA_DATA_STEP2_UNRELATED_THAW_DRIFT")
    for spec in STEP2_THAWS.values():
        for path, pair in spec["files"].items():
            for token, frozen in (readback.get("entries") or {}).items():
                amap = frozen.get("artifacts") or {}
                if path in amap and str(amap[path]) != pair["to_blob"]:
                    raise RuntimeError("WNBA_DATA_STEP2_FORWARD_PORT_READBACK_FAILED:" + str(token) + ":" + path)
    if int(readback.get("revision") or -1) != EXPECTED_REGISTRY_REVISION + 1:
        raise RuntimeError("WNBA_DATA_STEP2_REGISTRY_REVISION_READBACK_FAILED")
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_SOURCE_MAIN_READBACK_FAILED")

    return {
        "status": "GREEN",
        "freeze_token": FREEZE_TOKEN,
        "main_sha": MAIN_SHA,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_step2_thaws": 0,
        "unrelated_thaws_preserved": len(unrelated_before),
        "runless_check_id": check_id,
        "runless_receipt": receipt_digest,
        "public_proof_deploy": PUBLIC_PROOF_DEPLOY,
    }


def closeout_step2(client):
    artifacts, gate_ids = _verify_identity(client)
    check_id, receipt_digest = _publish_main_gate(client, artifacts, gate_ids)
    return _freeze_registry(client, artifacts, check_id, receipt_digest)


def install_startup_closeout(app):
    app.state.wnba_data_step2_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _closeout():
        try:
            app.state.wnba_data_step2_closeout = closeout_step2(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step2_closeout = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]}
        print("WNBA_DATA_STEP2_FINAL_CLOSEOUT=" + json.dumps(app.state.wnba_data_step2_closeout, sort_keys=True), flush=True)

    return app
