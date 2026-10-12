import hashlib
import json

import pytest

from devsystem.api2_registry_step4_thaw_rebind_r2 import (
    CURRENT_REVISION,
    NEW_HEAD,
    OLD_HEAD,
    STEP4_THAW_ID,
    rebind_payload,
)


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value):
    payload = dict(value)
    payload.pop("state_hash", None)
    return hashlib.sha256(_canon(payload).encode("utf-8")).hexdigest()


def _sample_registry():
    frozen_blob = "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0"
    to_blob = "0ad62af70010051c3ac8f4477d63263a228eb76b"
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": CURRENT_REVISION,
        "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
        "entries": {
            "X": {
                "status": "FROZEN",
                "checkpoint_id": "X",
                "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
                "artifacts": {"nba_spread_page_v1.py": frozen_blob},
            }
        },
        "active_thaws": [
            {
                "thaw_id": STEP4_THAW_ID,
                "status": "ACTIVE",
                "target_head_sha": OLD_HEAD,
                "files": {
                    "nba_spread_page_v1.py": {
                        "from_blob": frozen_blob,
                        "to_blob": to_blob,
                    }
                },
            }
        ],
    }
    payload["state_hash"] = _hash(payload)
    return payload


def test_rebind_moves_only_exact_step4_target():
    before = _sample_registry()
    after = rebind_payload(before, require_current_hash=False)
    assert after["revision"] == CURRENT_REVISION + 1
    assert after["active_thaws"][0]["target_head_sha"] == NEW_HEAD
    assert after["entries"] == before["entries"]
    assert after["state_hash"] == _hash(after)


def test_wrong_old_target_fails_closed():
    before = _sample_registry()
    before["active_thaws"][0]["target_head_sha"] = "e" * 40
    before["state_hash"] = _hash(before)
    with pytest.raises(Exception, match="STEP4_THAW_IDENTITY"):
        rebind_payload(before, require_current_hash=False)
