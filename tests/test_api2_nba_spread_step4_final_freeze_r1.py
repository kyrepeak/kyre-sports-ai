import hashlib
import json

import pytest

from devsystem.api2_nba_spread_step4_final_freeze_r1 import (
    FREEZE_TOKEN,
    MERGED_MAIN_SHA,
    NEW_PAGE_BLOB,
    OLD_PAGE_BLOB,
    STEP4_ARTIFACTS,
    STEP4_THAW_ID,
    build_final_registry,
    validate_public_evidence,
)
from devsystem.frozen_artifact_registry_v1 import validate_registry


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value):
    payload = dict(value)
    payload.pop("state_hash", None)
    return hashlib.sha256(_canon(payload).encode("utf-8")).hexdigest()


def _sample_registry():
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 299,
        "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
        "entries": {
            "NBA_SPREAD_STEP2_SITE_ACTIVATION_FROZEN": {
                "status": "FROZEN",
                "checkpoint_id": "NBA_SPREAD_STEP2_SITE_ACTIVATION_FROZEN",
                "source_main_sha": "30e803ea943091d07e760d9d4e003e110cbc29ed",
                "artifacts": {"nba_spread_page_v1.py": OLD_PAGE_BLOB},
            },
            "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN": {
                "status": "FROZEN",
                "checkpoint_id": "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN",
                "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
                "artifacts": {"nba_spread_page_v1.py": OLD_PAGE_BLOB},
            },
            "OTHER": {
                "status": "FROZEN",
                "checkpoint_id": "OTHER",
                "source_main_sha": "1" * 40,
                "artifacts": {"keep.py": "c" * 40},
            },
        },
        "active_thaws": [
            {
                "thaw_id": STEP4_THAW_ID,
                "status": "ACTIVE",
                "target_head_sha": "89a3ba98da2cc611093e32f8af20eab05f6faebc",
                "files": {"nba_spread_page_v1.py": {"from_blob": OLD_PAGE_BLOB, "to_blob": NEW_PAGE_BLOB}},
            },
            {
                "thaw_id": "THAW-OTHER",
                "status": "ACTIVE",
                "target_head_sha": "2" * 40,
                "files": {"keep.py": {"from_blob": "c" * 40, "to_blob": "d" * 40}},
            },
        ],
    }
    payload["state_hash"] = _hash(payload)
    return payload


def test_final_freeze_advances_shared_baseline_and_adds_token():
    before = _sample_registry()
    after, plan = build_final_registry(before, require_authoritative_identity=False)
    validate_registry(after)
    assert after["revision"] == 300
    assert after["source_main_sha"] == MERGED_MAIN_SHA
    assert after["entries"]["NBA_SPREAD_STEP2_SITE_ACTIVATION_FROZEN"]["artifacts"]["nba_spread_page_v1.py"] == NEW_PAGE_BLOB
    assert after["entries"]["NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN"]["artifacts"]["nba_spread_page_v1.py"] == NEW_PAGE_BLOB
    assert after["entries"][FREEZE_TOKEN]["artifacts"] == STEP4_ARTIFACTS
    assert STEP4_THAW_ID not in {item["thaw_id"] for item in after["active_thaws"]}
    assert "THAW-OTHER" in {item["thaw_id"] for item in after["active_thaws"]}
    assert len(plan["updated_entries"]) == 2
    assert plan["retired_empty_thaw_grants"] == [STEP4_THAW_ID]
    assert after["state_hash"] == _hash(after)


def test_wrong_step4_thaw_target_fails_closed():
    before = _sample_registry()
    before["active_thaws"][0]["target_head_sha"] = "e" * 40
    before["state_hash"] = _hash(before)
    with pytest.raises(Exception, match="STEP4_THAW_IDENTITY"):
        build_final_registry(before, require_authoritative_identity=False)


def test_public_evidence_requires_live_step3_step4_and_no_step5():
    evidence = {
        "merged_main_sha": MERGED_MAIN_SHA,
        "backend_health_status": 200,
        "backend_health_content": "ok",
        "websocket_opened": True,
        "websocket_frame_count": 22,
        "found": {
            "nba-spread-step4-most-bet-active": True,
            "NBA Spread": True,
            "Phoenix, Arizona": True,
            "nba-spread-step3-schedule-active": True,
        },
        "forbidden": {
            "Sharp Money Game": False,
            "Kyre Fair Spread": False,
            "Cover Probability": False,
        },
    }
    assert validate_public_evidence(evidence)["status"] == "GREEN"
    evidence["forbidden"]["Cover Probability"] = True
    with pytest.raises(Exception, match="PUBLIC_STEP5_LEAKAGE"):
        validate_public_evidence(evidence)
