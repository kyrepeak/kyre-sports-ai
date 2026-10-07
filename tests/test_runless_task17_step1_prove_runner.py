import base64
import json
from pathlib import Path

import pytest

from devsystem.frozen_artifact_registry_v1 import (
    FrozenArtifactRegistryFailure,
    _hash,
    _payload_without_hash,
)
from runless_proof_plane.config import Settings
from runless_proof_plane.models import FailureClass, ProofRequest, SliceEvidence
from runless_proof_plane.orchestrator import ProofOrchestrator


def _request(**overrides):
    values = dict(
        task_id="runless-task17-step1-real-prove",
        workstream="runless-task17-step1",
        candidate_sha="a" * 40,
        lease_id="lease-1",
        authorization_id="auth-1",
        expected_main_sha="b" * 40,
    )
    values.update(overrides)
    return ProofRequest(**values)


def _write_plan(root: Path):
    path = root / "devsystem" / "runless_proof_plans"
    path.mkdir(parents=True)
    (path / "runless-task17-step1-real-prove.json").write_text(
        json.dumps(
            {
                "task_id": "runless-task17-step1-real-prove",
                "workstream": "runless-task17-step1",
                "commands": [["python", "-m", "pytest", "-q", "tests/test_example.py"]],
                "artifacts": ["runless_proof_plane/api.py"],
                "dependencies": ["runless_proof_plane/step2a.py"],
                "probes": [],
                "timeout_seconds": 60,
                "live_ttl_seconds": 60,
                "freeze_token": "RUNLESS_TASK17_STEP1_REAL_PROVE_FROZEN",
            }
        )
        + "\n"
    )


def _registry(*, with_thaw=False):
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 154,
        "source_main_sha": "b" * 40,
        "entries": {
            "RUNLESS_PARENT": {
                "status": "FROZEN",
                "checkpoint_id": "RUNLESS_PARENT",
                "source_main_sha": "b" * 40,
                "artifacts": {"runless_proof_plane/api.py": "1" * 40},
            }
        },
        "active_thaws": [],
    }
    if with_thaw:
        payload["active_thaws"] = [
            {
                "thaw_id": "THAW-RUNLESS-TASK17-STEP1-API",
                "status": "ACTIVE",
                "target_head_sha": "a" * 40,
                "files": {
                    "runless_proof_plane/api.py": {
                        "from_blob": "1" * 40,
                        "to_blob": "2" * 40,
                    }
                },
            }
        ]
    payload["state_hash"] = _hash(_payload_without_hash(payload))
    return payload


def test_execute_proof_request_runs_real_premerge_chain(monkeypatch, tmp_path):
    import runless_proof_plane.prove as prove

    _write_plan(tmp_path)
    request = _request()
    receipts = {}
    published = {}

    class FakeWorkspace:
        def __init__(self, *args, **kwargs):
            self.path = tmp_path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        repository = "kyrepeak/kyre-sports-ai"

        class Auth:
            def installation_token(self):
                return "token"

        auth = Auth()

        def commit(self, sha):
            assert sha == "a" * 40
            return {"sha": sha}

        def branch_sha(self, branch):
            assert branch == "main"
            return "b" * 40

        def tree_blobs(self, sha):
            if sha == "a" * 40:
                return {
                    "runless_proof_plane/api.py": "1" * 40,
                    "runless_proof_plane/step2a.py": "2" * 40,
                }
            assert sha == "b" * 40
            return {
                "runless_proof_plane/api.py": "1" * 40,
                "runless_proof_plane/step2a.py": "2" * 40,
            }

    class FakeBackend:
        def exists(self, path, ref):
            return False

    class FakeStore:
        ref = "runless-proof-receipts"
        base_path = "devsystem/runless_proof_receipts"
        backend = FakeBackend()

        def get(self, proof_id):
            raise AssertionError("missing receipt must not be read")

        def put(self, receipt):
            published["stored_receipt"] = receipt
            return receipt["digest"]

    monkeypatch.setattr(prove, "CandidateWorkspace", FakeWorkspace)
    monkeypatch.setattr(
        prove,
        "_verify_frozen_candidate",
        lambda client, candidate_sha, tree, **kwargs: {
            "revision": 154,
            "state_hash": "3" * 64,
            "active_thaws": [],
            "inherited_frozen_paths": [],
            "exact_thawed_paths": [],
        },
    )
    monkeypatch.setattr(prove, "_read_live_scope_lease", lambda client, lease_id: lease_id)
    monkeypatch.setattr(
        prove,
        "execute_static_slice",
        lambda plan, workspace: [
            SliceEvidence(name="static", ok=True, failure_class=FailureClass.NONE)
        ],
    )
    monkeypatch.setattr(prove, "_receipt_store", lambda *args, **kwargs: FakeStore())
    monkeypatch.setattr(
        prove,
        "publish_gate",
        lambda client, sha, conclusion, receipt, gate_name: published.update(
            sha=sha, conclusion=conclusion, gate_name=gate_name, receipt=receipt
        ),
    )

    result = prove.execute_proof_request(
        request,
        settings=Settings(bootstrap=False),
        github_client=FakeClient(),
        orchestrator=ProofOrchestrator(),
        receipts=receipts,
    )

    assert result["status"] == "MERGE_AUTHORIZED"
    assert result["candidate_sha"] == "a" * 40
    assert result["proof_id"] in receipts
    assert result["receipt"]["digest"] == receipts[result["proof_id"]]["digest"]
    assert published["sha"] == "a" * 40
    assert published["conclusion"] == "success"
    assert published["gate_name"] == "runless-final-gate"
    assert result["inherited_frozen_path_count"] == 0
    assert result["exact_thawed_path_count"] == 0


def test_execute_proof_request_fails_closed_on_scope_lease_drift(monkeypatch, tmp_path):
    import runless_proof_plane.prove as prove
    from runless_proof_plane.step2a import Step2AError

    _write_plan(tmp_path)

    class FakeWorkspace:
        def __init__(self, *args, **kwargs):
            self.path = tmp_path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        repository = "kyrepeak/kyre-sports-ai"

        class Auth:
            def installation_token(self):
                return "token"

        auth = Auth()

        def commit(self, sha):
            return {"sha": sha}

        def branch_sha(self, branch):
            return "b" * 40

        def tree_blobs(self, sha):
            if sha == "a" * 40:
                return {
                    "runless_proof_plane/api.py": "1" * 40,
                    "runless_proof_plane/step2a.py": "2" * 40,
                }
            assert sha == "b" * 40
            return {
                "runless_proof_plane/api.py": "1" * 40,
                "runless_proof_plane/step2a.py": "2" * 40,
            }

    monkeypatch.setattr(prove, "CandidateWorkspace", FakeWorkspace)
    monkeypatch.setattr(
        prove,
        "_verify_frozen_candidate",
        lambda client, candidate_sha, tree, **kwargs: {
            "revision": 154,
            "state_hash": "3" * 64,
            "active_thaws": [],
            "inherited_frozen_paths": [],
            "exact_thawed_paths": [],
        },
    )
    monkeypatch.setattr(prove, "_read_live_scope_lease", lambda client, lease_id: "different-lease")

    with pytest.raises(Step2AError, match="RUNLESS_SCOPE_LEASE_MISMATCH"):
        prove.execute_proof_request(
            _request(),
            settings=Settings(bootstrap=False),
            github_client=FakeClient(),
            orchestrator=ProofOrchestrator(),
            receipts={},
        )


def test_frozen_candidate_requires_exact_head_thaw():
    import runless_proof_plane.prove as prove

    class FakeClient:
        def content(self, path, ref=None):
            payload = json.dumps(_registry()).encode()
            return {
                "encoding": "base64",
                "sha": "f" * 40,
                "content": base64.b64encode(payload).decode(),
            }

    with pytest.raises(FrozenArtifactRegistryFailure, match="candidate frozen delta without exact thaw grant"):
        prove._verify_frozen_candidate(
            FakeClient(),
            "a" * 40,
            {"runless_proof_plane/api.py": "2" * 40},
        )


def test_frozen_candidate_accepts_exact_head_thaw():
    import runless_proof_plane.prove as prove

    class FakeClient:
        def content(self, path, ref=None):
            payload = json.dumps(_registry(with_thaw=True)).encode()
            return {
                "encoding": "base64",
                "sha": "f" * 40,
                "content": base64.b64encode(payload).decode(),
            }

    result = prove._verify_frozen_candidate(
        FakeClient(),
        "a" * 40,
        {"runless_proof_plane/api.py": "2" * 40},
    )

    assert result["revision"] == 154
    assert result["active_thaws"] == ["THAW-RUNLESS-TASK17-STEP1-API"]
    assert result["exact_thawed_paths"] == ["runless_proof_plane/api.py"]
