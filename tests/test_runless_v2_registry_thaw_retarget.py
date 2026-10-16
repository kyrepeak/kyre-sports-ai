from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_TEST = ROOT / "tests/test_runless_v2_registry_thaw_route.py"
NEW_CANDIDATE = "7" * 40


def _load_base():
    spec = importlib.util.spec_from_file_location("runless_registry_thaw_base_test", BASE_TEST)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_thaw_same_frozen_delta_can_retarget_exact_new_candidate_without_duplicate_grant() -> None:
    base = _load_base()
    client, github = base._client(enabled=True)

    first = client.post("/registry-thaw", headers=base.AUTH, json=base._payload())
    assert first.status_code == 200, first.text
    assert github.put_count == 1
    assert len(github.registry["active_thaws"]) == 2

    original_tree_blobs = github.tree_blobs

    def tree_blobs(sha):
        if sha == NEW_CANDIDATE:
            return {base.PATH: base.TO_BLOB}
        return original_tree_blobs(sha)

    github.tree_blobs = tree_blobs
    before_unrelated = github.registry["active_thaws"][0].copy()
    payload = base._payload()
    payload["candidate_sha"] = NEW_CANDIDATE

    response = client.post("/registry-thaw", headers=base.AUTH, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert github.put_count == 2
    assert github.registry["revision"] == 43
    assert len(github.registry["active_thaws"]) == 2
    assert github.registry["active_thaws"][0] == before_unrelated

    exact = github.registry["active_thaws"][1]
    assert exact == {
        "thaw_id": base.THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": NEW_CANDIDATE,
        "files": {
            base.PATH: {
                "from_blob": base.FROM_BLOB,
                "to_blob": base.TO_BLOB,
            }
        },
    }
    assert github.registry["state_hash"] == base._state_hash(github.registry)
    assert body["thaw_id"] == base.THAW_ID
    assert body["target_head_sha"] == NEW_CANDIDATE
    assert body["from_blob"] == base.FROM_BLOB
    assert body["to_blob"] == base.TO_BLOB
    assert body["previous_registry_revision"] == 42
    assert body["current_registry_revision"] == 43
    assert body["state"] == "ACTIVE"
    assert body["reused"] is False
    assert body["failure_class"] == "NONE"


def test_same_thaw_retarget_rejects_changed_frozen_blob_pair() -> None:
    base = _load_base()
    client, github = base._client(enabled=True)
    first = client.post("/registry-thaw", headers=base.AUTH, json=base._payload())
    assert first.status_code == 200

    payload = base._payload()
    payload["candidate_sha"] = NEW_CANDIDATE
    payload["to_blob"] = "6" * 40
    github.tree_blobs = lambda sha: (
        {base.PATH: "6" * 40} if sha == NEW_CANDIDATE else {base.PATH: base.FROM_BLOB}
    )

    response = client.post("/registry-thaw", headers=base.AUTH, json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "REGISTRY_THAW_ID_COLLISION"
    assert github.put_count == 1
    assert len(github.registry["active_thaws"]) == 2
