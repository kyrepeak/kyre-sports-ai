from __future__ import annotations

import base64
import hashlib
import json

from fastapi.testclient import TestClient

from runless_v2.app import create_app
from runless_v2.config import Settings

REPOSITORY = "kyrepeak/kyre-sports-ai"
CANDIDATE = "a" * 40
MAIN = "b" * 40
MERGED_MAIN = "7" * 40
FROM_BLOB = "c" * 40
TO_BLOB = "d" * 40
REGISTRY_BLOB = "e" * 40
REGISTRY_COMMIT = "f" * 40
PATH = "frozen.py"
THAW_ID = "THAW-RUNLESS-V2-ROUTE-TEST"
AUTH = {"Authorization": "Bearer proof-secret"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(value):
    payload = dict(value)
    payload.pop("state_hash", None)
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _registry():
    value = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": REPOSITORY,
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 41,
        "source_main_sha": MAIN,
        "entries": {
            "FROZEN_TEST": {
                "status": "FROZEN",
                "checkpoint_id": "FROZEN_TEST",
                "source_main_sha": MAIN,
                "artifacts": {PATH: FROM_BLOB},
            }
        },
        "active_thaws": [
            {
                "thaw_id": "UNRELATED-THAW",
                "status": "ACTIVE",
                "target_head_sha": "9" * 40,
                "files": {"other.py": {"from_blob": "1" * 40, "to_blob": "2" * 40}},
            }
        ],
    }
    value["state_hash"] = _state_hash(value)
    return value


class FakeStore:
    def health(self):
        return True


class FakeSandbox:
    pass


class FakeGithub:
    def __init__(self):
        self.registry = _registry()
        self.registry_blob = REGISTRY_BLOB
        self.put_count = 0

    def main_sha(self):
        return MAIN

    def tree_blobs(self, sha):
        if sha == MAIN:
            return {PATH: FROM_BLOB}
        if sha == CANDIDATE:
            return {PATH: TO_BLOB}
        raise AssertionError(f"unexpected tree sha: {sha}")

    @staticmethod
    def _flatten_registry_artifacts(registry):
        result = {}
        for entry in registry["entries"].values():
            result.update(entry["artifacts"])
        return result

    def _raw_registry(self):
        text = _canonical(self.registry) + "\n"
        return {
            "encoding": "base64",
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "sha": self.registry_blob,
        }

    def _request(self, method, path, **kwargs):
        if method == "GET" and path.startswith("/contents/devsystem/frozen_artifact_registry_state_v1.json"):
            return self._raw_registry()
        if method == "PUT" and path == "/contents/devsystem/frozen_artifact_registry_state_v1.json":
            body = kwargs["json"]
            assert body["branch"] == "monster-frozen-artifact-registry"
            assert body["sha"] == self.registry_blob
            self.registry = json.loads(base64.b64decode(body["content"]).decode("utf-8"))
            self.registry_blob = "8" * 40
            self.put_count += 1
            return {"commit": {"sha": REGISTRY_COMMIT}, "content": {"sha": self.registry_blob}}
        raise AssertionError(f"unexpected GitHub request: {method} {path}")


def _settings(enabled=True):
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-secret",
        github_app_id="5204253",
        github_app_installation_id="99",
        github_app_private_key="private-key",
        proof_auth_token="proof-secret",
        repository=REPOSITORY,
        authority_enabled=enabled,
    )


def _client(*, enabled=True):
    github = FakeGithub()
    app = create_app(
        settings=_settings(enabled=enabled),
        state_store=FakeStore(),
        github=github,
        sandbox_executor=FakeSandbox(),
    )
    return TestClient(app), github


def _payload():
    return {
        "repository": REPOSITORY,
        "workstream": "monster-cfb-game-total-page2-unified-flow-repair-v1",
        "task_id": "monster-cfb-game-total-page2-team-snapshot-step3-v1",
        "candidate_sha": CANDIDATE,
        "thaw_id": THAW_ID,
        "path": PATH,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "expected_main_sha": MAIN,
    }


def test_registry_thaw_route_is_bearer_protected_and_fails_closed_when_disabled():
    client, github = _client(enabled=True)
    assert client.post("/registry-thaw", json=_payload()).status_code == 401
    assert github.put_count == 0

    disabled, disabled_github = _client(enabled=False)
    response = disabled.post("/registry-thaw", headers=AUTH, json=_payload())
    assert response.status_code == 503
    assert response.json()["detail"] == "RUNLESS_V2_AUTHORITY_DISABLED"
    assert disabled_github.put_count == 0


def test_registry_thaw_route_writes_one_exact_cas_thaw_and_preserves_unrelated_state():
    client, github = _client(enabled=True)
    before_entries = json.loads(json.dumps(github.registry["entries"]))
    before_unrelated = json.loads(json.dumps(github.registry["active_thaws"]))
    before_hash = github.registry["state_hash"]

    response = client.post("/registry-thaw", headers=AUTH, json=_payload())
    assert response.status_code == 200, response.text
    body = response.json()

    assert github.put_count == 1
    assert github.registry["entries"] == before_entries
    assert github.registry["active_thaws"][:-1] == before_unrelated
    exact = github.registry["active_thaws"][-1]
    assert exact == {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    assert github.registry["revision"] == 42
    assert github.registry["state_hash"] == _state_hash(github.registry)

    assert body == {
        "thaw_id": THAW_ID,
        "target_head_sha": CANDIDATE,
        "path": PATH,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "previous_registry_revision": 41,
        "current_registry_revision": 42,
        "previous_state_hash": before_hash,
        "current_state_hash": github.registry["state_hash"],
        "registry_commit_sha": REGISTRY_COMMIT,
        "state": "ACTIVE",
        "reused": False,
        "failure_class": "NONE",
        "detail": "",
    }


class FakeForwardPortGithub(FakeGithub):
    def __init__(self):
        super().__init__()
        self.registry["entries"]["FROZEN_TEST_2"] = {
            "status": "FROZEN",
            "checkpoint_id": "FROZEN_TEST_2",
            "source_main_sha": MAIN,
            "artifacts": {
                PATH: FROM_BLOB,
                "keep.py": "3" * 40,
            },
        }
        self.registry["active_thaws"].append(
            {
                "thaw_id": THAW_ID,
                "status": "ACTIVE",
                "target_head_sha": CANDIDATE,
                "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
            }
        )
        self.registry["state_hash"] = _state_hash(self.registry)

    def main_sha(self):
        return MERGED_MAIN

    def tree_blobs(self, sha):
        if sha in {CANDIDATE, MERGED_MAIN}:
            return {PATH: TO_BLOB}
        raise AssertionError(f"unexpected tree sha: {sha}")


def _forward_client(*, enabled=True):
    github = FakeForwardPortGithub()
    app = create_app(
        settings=_settings(enabled=enabled),
        state_store=FakeStore(),
        github=github,
        sandbox_executor=FakeSandbox(),
    )
    return TestClient(app), github


def _forward_payload():
    return {
        "repository": REPOSITORY,
        "workstream": "monster-cfb-game-total-page2-unified-flow-repair-v1",
        "candidate_sha": CANDIDATE,
        "merged_main_sha": MERGED_MAIN,
        "thaw_id": THAW_ID,
        "path": PATH,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
    }


def test_registry_forward_port_route_is_bearer_protected_and_fails_closed_when_disabled():
    client, github = _forward_client(enabled=True)
    assert client.post("/registry-forward-port", json=_forward_payload()).status_code == 401
    assert github.put_count == 0

    disabled, disabled_github = _forward_client(enabled=False)
    response = disabled.post("/registry-forward-port", headers=AUTH, json=_forward_payload())
    assert response.status_code == 503
    assert response.json()["detail"] == "RUNLESS_V2_AUTHORITY_DISABLED"
    assert disabled_github.put_count == 0


def test_registry_forward_port_updates_baseline_retires_exact_thaw_and_preserves_unrelated_state():
    client, github = _forward_client(enabled=True)
    before = json.loads(json.dumps(github.registry))
    before_hash = github.registry["state_hash"]
    unrelated = before["active_thaws"][0]

    response = client.post("/registry-forward-port", headers=AUTH, json=_forward_payload())
    assert response.status_code == 200, response.text
    body = response.json()

    assert github.put_count == 1
    assert github.registry["revision"] == 42
    assert github.registry["source_main_sha"] == MERGED_MAIN
    assert github.registry["state_hash"] == _state_hash(github.registry)

    assert github.registry["entries"]["FROZEN_TEST"]["artifacts"][PATH] == TO_BLOB
    assert github.registry["entries"]["FROZEN_TEST_2"]["artifacts"][PATH] == TO_BLOB
    assert github.registry["entries"]["FROZEN_TEST_2"]["artifacts"]["keep.py"] == "3" * 40
    assert github.registry["active_thaws"] == [unrelated]

    assert body == {
        "thaw_id": THAW_ID,
        "candidate_sha": CANDIDATE,
        "merged_main_sha": MERGED_MAIN,
        "path": PATH,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "previous_registry_revision": 41,
        "current_registry_revision": 42,
        "previous_state_hash": before_hash,
        "current_state_hash": github.registry["state_hash"],
        "registry_commit_sha": REGISTRY_COMMIT,
        "state": "FROZEN",
        "retired": True,
        "failure_class": "NONE",
        "detail": "",
    }


def test_registry_forward_port_rejects_thaw_identity_mismatch_without_mutation():
    client, github = _forward_client(enabled=True)
    github.registry["active_thaws"][-1]["target_head_sha"] = "6" * 40
    github.registry["state_hash"] = _state_hash(github.registry)

    response = client.post("/registry-forward-port", headers=AUTH, json=_forward_payload())
    assert response.status_code == 409
    assert response.json()["detail"] == "REGISTRY_FORWARD_PORT_THAW_IDENTITY_MISMATCH"
    assert github.put_count == 0
