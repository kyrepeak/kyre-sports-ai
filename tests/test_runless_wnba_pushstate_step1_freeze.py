from __future__ import annotations

import base64
import hashlib
import json

from devsystem.frozen_artifact_registry_v1 import (
    REGISTRY_PATH,
    REGISTRY_REF,
    VERSION,
    validate_registry,
)
from runless_proof_plane.wnba_pushstate_step1_closeout import (
    STEP1_ARTIFACTS,
    WNBA_PUSHSTATE_STEP1_FREEZE_TOKEN,
    freeze_step1,
)

MERGED = "896bd5f78ef6b6f7d7084413cc1e35ac6489fdc2"
MERGED_RECEIPT = "5d75cc0455219fa9677704bddd0378760701716a0b5454cac8643697f2243881"


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(payload):
    value = dict(payload)
    value.pop("state_hash", None)
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _registry():
    payload = {
        "schema_version": 1,
        "version": VERSION,
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": REGISTRY_REF,
        "registry_path": REGISTRY_PATH,
        "revision": 119,
        "source_main_sha": "1" * 40,
        "entries": {
            "UNRELATED_FROZEN": {
                "status": "FROZEN",
                "checkpoint_id": "UNRELATED_FROZEN",
                "source_main_sha": "1" * 40,
                "artifacts": {"legacy.py": "a" * 40},
            }
        },
        "active_thaws": [
            {
                "thaw_id": "THAW-UNRELATED",
                "status": "ACTIVE",
                "target_head_sha": "2" * 40,
                "files": {
                    "legacy.py": {
                        "from_blob": "a" * 40,
                        "to_blob": "b" * 40,
                    }
                },
            }
        ],
    }
    payload["state_hash"] = _state_hash(payload)
    return payload


class FakeFreezeClient:
    def __init__(self):
        self.registry = _registry()
        self.registry_blob = "f" * 40
        self.updates = []

    def branch_sha(self, branch):
        assert branch == "main"
        return MERGED

    def tree_blobs(self, sha):
        assert sha == MERGED
        return {
            path: f"{index + 1:040x}"
            for index, path in enumerate(STEP1_ARTIFACTS)
        }

    def request(self, method, path, **kwargs):
        assert method == "GET"
        assert path == f"/commits/{MERGED}/check-runs"
        return {
            "check_runs": [
                {
                    "id": 112489495538,
                    "name": "runless-final-gate",
                    "head_sha": MERGED,
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"id": 5204253},
                    "output": {"summary": f"receipt={MERGED_RECEIPT}"},
                }
            ]
        }

    def content(self, path, ref=None):
        assert path == REGISTRY_PATH
        assert ref == "monster-frozen-artifact-registry"
        raw = json.dumps(self.registry, sort_keys=True).encode()
        return {
            "encoding": "base64",
            "content": base64.b64encode(raw).decode(),
            "sha": self.registry_blob,
        }

    def update_content(self, path, text, branch, message, sha):
        assert path == REGISTRY_PATH
        assert branch == "monster-frozen-artifact-registry"
        assert sha == self.registry_blob
        self.registry = json.loads(text)
        self.registry_blob = "e" * 40
        self.updates.append((message, sha))


def test_step1_freeze_is_cas_protected_and_preserves_unrelated_thaws():
    client = FakeFreezeClient()
    before_thaws = json.loads(json.dumps(client.registry["active_thaws"]))

    result = freeze_step1(client, MERGED)

    assert result["status"] == "GREEN"
    assert result["frozen_token"] == WNBA_PUSHSTATE_STEP1_FREEZE_TOKEN
    assert result["merged_sha"] == MERGED
    assert result["revision"] == 120
    assert result["artifact_count"] == 4
    assert result["runless_check_id"] == 112489495538
    assert result["runless_receipt"] == MERGED_RECEIPT
    assert client.registry["active_thaws"] == before_thaws
    entry = client.registry["entries"][WNBA_PUSHSTATE_STEP1_FREEZE_TOKEN]
    assert entry["status"] == "FROZEN"
    assert entry["source_main_sha"] == MERGED
    assert set(entry["artifacts"]) == set(STEP1_ARTIFACTS)
    assert validate_registry(client.registry)["status"] == "GREEN"
    assert len(client.updates) == 1
