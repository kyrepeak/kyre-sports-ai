from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
FREEZE_TOKEN = "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN"
MERGED_SHA = "6b3a37891fc2938736e8f371d29c3337682a4a22"
CANDIDATE_SHA = "196295abd07610b47af30ae8542683f0143b6b25"
TARGET_THAW_ID = "THAW-NBA-SPREAD-STEP3-SCHEDULE-PHOENIX-R1"
SHARED_CHECKPOINT = "NBA_SPREAD_STEP2_SITE_ACTIVATION_FROZEN"
SHARED_PATH = "nba_spread_page_v1.py"
OLD_SHARED_BLOB = "8becdc6be21e8956e8f8101ebb3a930897f61cf6"
NEW_SHARED_BLOB = "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0"
EXPECTED_REVISION = 295
EXPECTED_HASH = "0389b304ab6cd1fe955d331de90671680ebbb3369297db66ccbef1faa678d6bc"
EXPECTED_NEW_HASH = "5e4d1ec3b4c1fc443cae3122fe51c274407a679cf54f5795e34ca4a9c89b926c"
ARTIFACTS = {
    "devsystem/execution_plans/nba-spread-step3-schedule-phoenix-v1.json": "49cf5f8240f72e28eae14e88682dc01fdde3c7fa",
    "devsystem/runless_proof_plans/nba-spread-step3-schedule-phoenix-v1.json": "abf83f4bc5844770f71b98f5ae614804e6935e34",
    "devsystem/task_ledgers/nba-spread-step3-schedule-phoenix-v1.json": "1abbb39d8199487a563a1000bdf30d6ff4770e56",
    "nba_spread_schedule_v1.py": "143c366f935776b2f8ce77c0947b1fcf23013fa7",
    SHARED_PATH: NEW_SHARED_BLOB,
    "tests/test_nba_spread_step3_schedule_phoenix_v1.py": "de424b332587f061678cfcffe58c8f340cdfd3a0",
}


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(payload):
    value = deepcopy(payload)
    value.pop("state_hash", None)
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("NBA_SPREAD_STEP3_REGISTRY_READ_FAILED")
    try:
        payload = json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("NBA_SPREAD_STEP3_REGISTRY_DECODE_FAILED") from exc
    validate_registry(payload)
    if _state_hash(payload) != payload.get("state_hash"):
        raise RuntimeError("NBA_SPREAD_STEP3_REGISTRY_HASH_INVALID")
    return payload, raw["sha"]


def _entry_exact(entry):
    return (
        isinstance(entry, dict)
        and entry.get("status") == "FROZEN"
        and entry.get("checkpoint_id") == FREEZE_TOKEN
        and entry.get("source_main_sha") == MERGED_SHA
        and entry.get("artifacts") == ARTIFACTS
    )


def freeze_step3(client):
    current, content_sha = _read_registry(client)
    current_entries = current.get("entries") or {}
    existing = current_entries.get(FREEZE_TOKEN)
    target_thaws = [
        grant for grant in current.get("active_thaws", [])
        if str(grant.get("thaw_id")) == TARGET_THAW_ID
    ]
    shared_blob = (
        current_entries.get(SHARED_CHECKPOINT, {})
        .get("artifacts", {})
        .get(SHARED_PATH)
    )

    if _entry_exact(existing) and not target_thaws and shared_blob == NEW_SHARED_BLOB:
        if int(current.get("revision", -1)) != 296 or current.get("state_hash") != EXPECTED_NEW_HASH:
            raise RuntimeError("NBA_SPREAD_STEP3_IDEMPOTENT_STATE_DRIFT")
        return {
            "status": "GREEN",
            "idempotent": True,
            "revision": 296,
            "state_hash": EXPECTED_NEW_HASH,
            "frozen_token": FREEZE_TOKEN,
            "active_thaw_count": len(current.get("active_thaws", [])),
            "retired_thaw": TARGET_THAW_ID,
        }

    if current.get("revision") != EXPECTED_REVISION or current.get("state_hash") != EXPECTED_HASH:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
    if len(target_thaws) != 1:
        raise RuntimeError("NBA_SPREAD_STEP3_TARGET_THAW_REQUIRED")

    target = target_thaws[0]
    expected_files = {
        SHARED_PATH: {"from_blob": OLD_SHARED_BLOB, "to_blob": NEW_SHARED_BLOB}
    }
    if (
        target.get("status") != "ACTIVE"
        or target.get("target_head_sha") != CANDIDATE_SHA
        or target.get("files") != expected_files
    ):
        raise RuntimeError("NBA_SPREAD_STEP3_TARGET_THAW_DRIFT")
    if shared_blob != OLD_SHARED_BLOB:
        raise RuntimeError("NBA_SPREAD_STEP3_SHARED_BASELINE_DRIFT")
    if existing is not None:
        raise RuntimeError("NBA_SPREAD_STEP3_FREEZE_TOKEN_CONFLICT")

    unrelated_thaws = [
        deepcopy(grant)
        for grant in current.get("active_thaws", [])
        if str(grant.get("thaw_id")) != TARGET_THAW_ID
    ]
    if len(unrelated_thaws) != 4:
        raise RuntimeError("NBA_SPREAD_STEP3_UNRELATED_THAW_COUNT_DRIFT")

    updated = deepcopy(current)
    updated["active_thaws"] = unrelated_thaws
    updated["entries"][SHARED_CHECKPOINT]["artifacts"][SHARED_PATH] = NEW_SHARED_BLOB
    updated["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_SHA,
        "artifacts": ARTIFACTS,
    }
    updated["revision"] = 296
    updated["source_main_sha"] = MERGED_SHA
    updated["state_hash"] = _state_hash(updated)
    if updated["state_hash"] != EXPECTED_NEW_HASH:
        raise RuntimeError("NBA_SPREAD_STEP3_EXPECTED_HASH_MISMATCH")
    validate_registry(updated)

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(
            REGISTRY_PATH,
            text,
            REGISTRY_BRANCH,
            "registry: freeze NBA Spread Step3 schedule Phoenix",
            content_sha,
        )
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc

    readback, _ = _read_registry(client)
    rb_entry = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    rb_shared = (
        readback.get("entries", {})
        .get(SHARED_CHECKPOINT, {})
        .get("artifacts", {})
        .get(SHARED_PATH)
    )
    if (
        int(readback.get("revision", -1)) != 296
        or readback.get("source_main_sha") != MERGED_SHA
        or readback.get("state_hash") != EXPECTED_NEW_HASH
        or not _entry_exact(rb_entry)
        or rb_shared != NEW_SHARED_BLOB
        or readback.get("active_thaws", []) != unrelated_thaws
        or any(str(g.get("thaw_id")) == TARGET_THAW_ID for g in readback.get("active_thaws", []))
    ):
        raise RuntimeError("NBA_SPREAD_STEP3_REGISTRY_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "idempotent": False,
        "revision": 296,
        "state_hash": EXPECTED_NEW_HASH,
        "frozen_token": FREEZE_TOKEN,
        "active_thaw_count": 4,
        "retired_thaw": TARGET_THAW_ID,
        "artifact_count": len(ARTIFACTS),
        "shared_baseline_blob": NEW_SHARED_BLOB,
    }


def freeze_from_env(client):
    return freeze_step3(client)
