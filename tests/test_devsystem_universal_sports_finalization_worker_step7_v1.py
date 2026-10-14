import hashlib
import json
from copy import deepcopy

import pytest

from devsystem import frozen_artifact_registry_v1 as legacy
from devsystem import universal_sports_finalization_bootstrap_v1 as bootstrap
from devsystem import universal_sports_finalization_worker_v1 as worker

A = "a" * 40
B = "b" * 40
C = "c" * 40
D = "d" * 40
E = "e" * 40
F = "f" * 40
H = "1" * 64
TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP7_FINALIZATION_WORKER_LEGACY_BRIDGE_FROZEN"


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def legacy_registry():
    value = {
        "schema_version": 1,
        "version": legacy.VERSION,
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": legacy.REGISTRY_REF,
        "registry_path": legacy.REGISTRY_PATH,
        "revision": 302,
        "source_main_sha": B,
        "entries": {
            "FROZEN_ONE": {
                "status": "FROZEN",
                "checkpoint_id": "FROZEN_ONE",
                "source_main_sha": B,
                "artifacts": {"frozen.py": C},
            }
        },
        "active_thaws": [
            {
                "thaw_id": "THAW-KEEP",
                "status": "ACTIVE",
                "target_head_sha": D,
                "files": {"frozen.py": {"from_blob": C, "to_blob": E}},
            }
        ],
    }
    value["state_hash"] = canonical_hash(value)
    return value


def previous_manifest():
    return bootstrap.build_manifest(
        previous=None,
        freeze_token="PRIOR_FROZEN",
        record_path="devsystem/finalization_ledger_v2/records/PRIOR_FROZEN.json",
        record_blob_sha=F,
        merged_main_sha=B,
    )


def packet(manifest, registry):
    return {
        "version": worker.PACKET_VERSION,
        "certified": True,
        "repository": "kyrepeak/kyre-sports-ai",
        "workstream": "universal-sports-source-finalization-v1",
        "freeze_token": TOKEN,
        "candidate_sha": A,
        "merged_main_sha": B,
        "proof_digest": "sha256:" + H,
        "artifacts": {"devsystem/step7.py": C},
        "expected_ledger": {
            "ref": worker.LEDGER_REF,
            "head_sha": D,
            "manifest_blob_sha": E,
            "revision": manifest["revision"],
            "state_hash": manifest["state_hash"],
        },
        "legacy_bridge": {
            "registry_ref": legacy.REGISTRY_REF,
            "head_sha": F,
            "registry_blob_sha": A,
            "revision": registry["revision"],
            "state_hash": registry["state_hash"],
            "active_thaw_ids": ["THAW-KEEP"],
            "retire_thaw_ids": [],
        },
    }


class FakeBackend:
    repository = "kyrepeak/kyre-sports-ai"
    workstream = "universal-sports-source-finalization-v1"

    def __init__(self, manifest, registry, *, tamper=False):
        self.ledger_head = D
        self.manifest_blob = E
        self.legacy_head = F
        self.legacy_blob = A
        self.manifest = deepcopy(manifest)
        self.registry = deepcopy(registry)
        self.files = {}
        self.file_texts = {}
        self.write_attempts = 0
        self.tamper = tamper

    def trusted_certification(self):
        return {
            "freeze_token": TOKEN,
            "candidate_sha": A,
            "merged_main_sha": B,
            "proof_digest": "sha256:" + H,
        }

    def snapshot(self):
        return {
            "ledger_head_sha": self.ledger_head,
            "manifest_blob_sha": self.manifest_blob,
            "manifest": deepcopy(self.manifest),
            "legacy_head_sha": self.legacy_head,
            "legacy_registry_blob_sha": self.legacy_blob,
            "legacy_registry": deepcopy(self.registry),
        }

    def cas_commit(self, *, ref, expected_head_sha, expected_manifest_blob_sha, files):
        self.write_attempts += 1
        assert ref == worker.LEDGER_REF
        assert expected_head_sha == self.ledger_head
        assert expected_manifest_blob_sha == self.manifest_blob
        self.file_texts = dict(files)
        self.files = {path: json.loads(text) for path, text in files.items()}
        self.ledger_head = "9" * 40
        self.manifest = deepcopy(self.files[worker.MANIFEST_PATH])
        self.manifest_blob = "8" * 40
        return {"commit_sha": self.ledger_head}

    def read_ref(self, ref):
        assert ref == worker.LEDGER_REF
        return self.ledger_head

    def read_json(self, ref, path):
        assert ref == worker.LEDGER_REF
        value = deepcopy(self.files[path])
        if self.tamper and path == worker.MANIFEST_PATH:
            value["revision"] += 1
        return value

    def read_blob_sha(self, ref, path):
        assert ref == worker.LEDGER_REF
        text = self.file_texts.get(path)
        if text is None:
            return None
        data = text.encode("utf-8")
        return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def test_worker_writes_once_reads_back_and_preserves_legacy_state():
    manifest = previous_manifest()
    registry = legacy_registry()
    backend = FakeBackend(manifest, registry)
    result = worker.finalize_certified_packet(packet(manifest, registry), backend=backend)
    assert result["status"] == "GREEN_FROZEN"
    assert result["decision"] == "FINALIZATION_WORKER_GREEN_FROZEN"
    assert result["write_attempts"] == 1 == backend.write_attempts
    assert result["readback_verified"] is True
    assert result["legacy_registry_mutation"] is False
    assert result["legacy_thaws_preserved"] == ["THAW-KEEP"]
    assert result["render_dependency"] is False
    assert result["github_actions_fallback"] == 0
    assert result["product_runtime_mutation"] is False
    assert result["model_projection_mutation"] is False
    assert backend.registry == registry


def test_repository_or_workstream_mismatch_fails_before_write():
    manifest, registry = previous_manifest(), legacy_registry()
    backend = FakeBackend(manifest, registry)
    bad = packet(manifest, registry)
    bad["repository"] = "other/repo"
    with pytest.raises(worker.FinalizationWorkerFailure, match="REPOSITORY_MISMATCH"):
        worker.finalize_certified_packet(bad, backend=backend)
    assert backend.write_attempts == 0


def test_stale_ledger_precondition_fails_before_write():
    manifest, registry = previous_manifest(), legacy_registry()
    backend = FakeBackend(manifest, registry)
    bad = packet(manifest, registry)
    bad["expected_ledger"]["state_hash"] = "0" * 64
    with pytest.raises(worker.FinalizationWorkerFailure, match="LEDGER_STATE_HASH_DRIFT"):
        worker.finalize_certified_packet(bad, backend=backend)
    assert backend.write_attempts == 0


def test_legacy_registry_or_thaw_drift_fails_before_write():
    manifest, registry = previous_manifest(), legacy_registry()
    backend = FakeBackend(manifest, registry)
    bad = packet(manifest, registry)
    bad["legacy_bridge"]["active_thaw_ids"] = []
    with pytest.raises(worker.FinalizationWorkerFailure, match="LEGACY_ACTIVE_THAW_DRIFT"):
        worker.finalize_certified_packet(bad, backend=backend)
    assert backend.write_attempts == 0


def test_legacy_thaw_retirement_is_not_owned_by_step7():
    manifest, registry = previous_manifest(), legacy_registry()
    backend = FakeBackend(manifest, registry)
    bad = packet(manifest, registry)
    bad["legacy_bridge"]["retire_thaw_ids"] = ["THAW-KEEP"]
    with pytest.raises(worker.FinalizationWorkerFailure, match="LEGACY_THAW_RETIREMENT_FORBIDDEN"):
        worker.finalize_certified_packet(bad, backend=backend)
    assert backend.write_attempts == 0


def test_readback_tamper_fails_after_exactly_one_write_without_retry():
    manifest, registry = previous_manifest(), legacy_registry()
    backend = FakeBackend(manifest, registry, tamper=True)
    with pytest.raises(worker.FinalizationWorkerFailure, match="READBACK_MISMATCH"):
        worker.finalize_certified_packet(packet(manifest, registry), backend=backend)
    assert backend.write_attempts == 1