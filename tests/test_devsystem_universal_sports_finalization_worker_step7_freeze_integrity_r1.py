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
TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP7_FINALIZATION_WORKER_LEGACY_BRIDGE_R1_FROZEN"


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def git_blob_sha(text):
    data = text.encode("utf-8")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


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
        "active_thaws": [],
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
        "artifacts": {"devsystem/step7-r1.py": C},
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
            "active_thaw_ids": [],
            "retire_thaw_ids": [],
        },
    }


class IntegrityBackend:
    repository = "kyrepeak/kyre-sports-ai"
    workstream = "universal-sports-source-finalization-v1"

    def __init__(
        self,
        manifest,
        registry,
        *,
        trusted=None,
        existing_paths=None,
        blob_mismatch_path=None,
    ):
        self.ledger_head = D
        self.manifest_blob = E
        self.legacy_head = F
        self.legacy_blob = A
        self.manifest = deepcopy(manifest)
        self.registry = deepcopy(registry)
        self.files = {}
        self.file_blob_shas = {}
        self.write_attempts = 0
        self.existing_paths = set(existing_paths or [])
        self.blob_mismatch_path = blob_mismatch_path
        self.trusted = deepcopy(trusted) if trusted is not None else {
            "freeze_token": TOKEN,
            "candidate_sha": A,
            "merged_main_sha": B,
            "proof_digest": "sha256:" + H,
        }

    def trusted_certification(self):
        return deepcopy(self.trusted)

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
        self.files = {path: json.loads(text) for path, text in files.items()}
        self.file_blob_shas = {path: git_blob_sha(text) for path, text in files.items()}
        self.ledger_head = "9" * 40
        self.manifest = deepcopy(self.files[worker.MANIFEST_PATH])
        self.manifest_blob = self.file_blob_shas[worker.MANIFEST_PATH]
        return {"commit_sha": self.ledger_head}

    def read_ref(self, ref):
        assert ref == worker.LEDGER_REF
        return self.ledger_head

    def read_json(self, ref, path):
        assert ref == worker.LEDGER_REF
        return deepcopy(self.files[path])

    def read_blob_sha(self, ref, path):
        assert ref == worker.LEDGER_REF
        if not self.files:
            return F if path in self.existing_paths else None
        observed = self.file_blob_shas.get(path)
        if path == self.blob_mismatch_path and observed is not None:
            return "0" * 40
        return observed


def test_untrusted_candidate_identity_fails_before_write():
    manifest, registry = previous_manifest(), legacy_registry()
    backend = IntegrityBackend(manifest, registry)
    bad = packet(manifest, registry)
    bad["candidate_sha"] = C

    with pytest.raises(worker.FinalizationWorkerFailure, match="TRUSTED_CERTIFICATION"):
        worker.finalize_certified_packet(bad, backend=backend)

    assert backend.write_attempts == 0


def test_existing_immutable_record_path_fails_before_write():
    manifest, registry = previous_manifest(), legacy_registry()
    record_path = f"{worker.RECORD_DIR}/{TOKEN}.json"
    backend = IntegrityBackend(manifest, registry, existing_paths={record_path})

    with pytest.raises(worker.FinalizationWorkerFailure, match="TARGET_PATH_EXISTS"):
        worker.finalize_certified_packet(packet(manifest, registry), backend=backend)

    assert backend.write_attempts == 0


def test_exact_blob_mismatch_fails_even_when_json_readback_matches():
    manifest, registry = previous_manifest(), legacy_registry()
    record_path = f"{worker.RECORD_DIR}/{TOKEN}.json"
    backend = IntegrityBackend(manifest, registry, blob_mismatch_path=record_path)

    with pytest.raises(worker.FinalizationWorkerFailure, match="READBACK_BLOB_MISMATCH"):
        worker.finalize_certified_packet(packet(manifest, registry), backend=backend)

    assert backend.write_attempts == 1
