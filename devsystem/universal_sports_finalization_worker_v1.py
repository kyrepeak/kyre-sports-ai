"""Universal Sports Finalization Worker V1 — Step 7 hardened finalization + legacy bridge.

Consumes one already-certified finalization packet, validates exact ledger and
legacy-registry identities, constructs deterministic ledger targets, performs
one injected CAS write, and independently reads the result back.  The legacy
registry is deliberately read-only; this worker produces a bridge record that
binds its exact state without becoming a second legacy mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping

from devsystem import frozen_artifact_registry_v1 as legacy_registry
from devsystem import universal_sports_finalization_bootstrap_v1 as bootstrap

VERSION = "UNIVERSAL_SPORTS_FINALIZATION_WORKER_V1"
PACKET_VERSION = "UNIVERSAL_SPORTS_CERTIFIED_FINALIZATION_PACKET_V1"
BRIDGE_VERSION = "UNIVERSAL_SPORTS_LEGACY_BRIDGE_V1"
LEDGER_REF = "refs/heads/monster-finalization-ledger-v2"
MANIFEST_PATH = "devsystem/finalization_ledger_v2/manifest.json"
RECORD_DIR = "devsystem/finalization_ledger_v2/records"
BRIDGE_DIR = "devsystem/finalization_ledger_v2/bridges"
NETWORK_CALLS = False
RENDER_DEPENDENCY = False
GITHUB_ACTIONS_FALLBACK = 0
PRODUCT_RUNTIME_MUTATION = False
MODEL_PROJECTION_MUTATION = False
LEGACY_REGISTRY_MUTATION = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")


class FinalizationWorkerFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonical_text(value: Mapping[str, Any]) -> str:
    return _canonical(dict(value)) + "\n"


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(dict(value)).encode("utf-8")).hexdigest()


def _hash_without(value: Mapping[str, Any], field: str) -> str:
    raw = deepcopy(dict(value))
    raw.pop(field, None)
    return _hash(raw)


def _git_blob_sha(text: str) -> str:
    data = text.encode("utf-8")
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_{label.upper()}_INVALID")
    return text


def _hash64(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _HASH64.fullmatch(text):
        raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_{label.upper()}_INVALID")
    return text


def _identity(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_{label.upper()}_REQUIRED")
    return text


def _require_equal(actual: Any, expected: Any, error: str) -> None:
    if actual != expected:
        raise FinalizationWorkerFailure(error)


def _validate_packet_identity(packet: Mapping[str, Any], backend: Any) -> None:
    if not isinstance(packet, Mapping):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_PACKET_NOT_OBJECT")
    if packet.get("version") != PACKET_VERSION:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_PACKET_VERSION_DRIFT")
    if packet.get("certified") is not True:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_PACKET_NOT_CERTIFIED")

    repository = _identity(packet.get("repository"), "repository")
    workstream = _identity(packet.get("workstream"), "workstream")
    expected_repository = _identity(getattr(backend, "repository", None), "backend_repository")
    expected_workstream = _identity(getattr(backend, "workstream", None), "backend_workstream")
    if repository != expected_repository:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_REPOSITORY_MISMATCH")
    if workstream != expected_workstream:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_WORKSTREAM_MISMATCH")

    try:
        trusted = dict(backend.trusted_certification())
    except Exception as exc:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_TRUSTED_CERTIFICATION_UNAVAILABLE") from exc
    trusted_freeze_token = _identity(trusted.get("freeze_token"), "trusted_freeze_token")
    trusted_candidate_sha = _sha(trusted.get("candidate_sha"), "trusted_candidate_sha")
    trusted_merged_main_sha = _sha(trusted.get("merged_main_sha"), "trusted_merged_main_sha")
    trusted_proof_digest = str(trusted.get("proof_digest") or "").strip().lower()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", trusted_proof_digest):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_TRUSTED_PROOF_DIGEST_INVALID")

    packet_proof_digest = str(packet.get("proof_digest") or "").strip().lower()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", packet_proof_digest):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_PROOF_DIGEST_INVALID")
    for actual, expected, label in (
        (_identity(packet.get("freeze_token"), "freeze_token"), trusted_freeze_token, "FREEZE_TOKEN"),
        (_sha(packet.get("candidate_sha"), "candidate_sha"), trusted_candidate_sha, "CANDIDATE"),
        (_sha(packet.get("merged_main_sha"), "merged_main_sha"), trusted_merged_main_sha, "MERGED_MAIN"),
        (packet_proof_digest, trusted_proof_digest, "PROOF_DIGEST"),
    ):
        if actual != expected:
            raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_TRUSTED_CERTIFICATION_{label}_MISMATCH")


def _validate_preconditions(packet: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_ledger = dict(packet.get("expected_ledger") or {})
    if expected_ledger.get("ref") != LEDGER_REF:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEDGER_REF_MISMATCH")
    _require_equal(
        str(snapshot.get("ledger_head_sha") or "").lower(),
        _sha(expected_ledger.get("head_sha"), "ledger_head_sha"),
        "FINALIZATION_WORKER_LEDGER_HEAD_DRIFT",
    )
    _require_equal(
        str(snapshot.get("manifest_blob_sha") or "").lower(),
        _sha(expected_ledger.get("manifest_blob_sha"), "manifest_blob_sha"),
        "FINALIZATION_WORKER_LEDGER_BLOB_DRIFT",
    )
    manifest = deepcopy(dict(snapshot.get("manifest") or {}))
    try:
        revision = int(manifest.get("revision"))
        expected_revision = int(expected_ledger.get("revision"))
    except (TypeError, ValueError) as exc:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEDGER_REVISION_INVALID") from exc
    if revision != expected_revision:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEDGER_REVISION_DRIFT")
    if str(manifest.get("state_hash") or "").lower() != _hash64(expected_ledger.get("state_hash"), "ledger_state_hash"):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEDGER_STATE_HASH_DRIFT")

    bridge = dict(packet.get("legacy_bridge") or {})
    if bridge.get("registry_ref") != legacy_registry.REGISTRY_REF:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_REF_MISMATCH")
    if bridge.get("retire_thaw_ids"):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_THAW_RETIREMENT_FORBIDDEN")
    _require_equal(
        str(snapshot.get("legacy_head_sha") or "").lower(),
        _sha(bridge.get("head_sha"), "legacy_head_sha"),
        "FINALIZATION_WORKER_LEGACY_HEAD_DRIFT",
    )
    _require_equal(
        str(snapshot.get("legacy_registry_blob_sha") or "").lower(),
        _sha(bridge.get("registry_blob_sha"), "legacy_registry_blob_sha"),
        "FINALIZATION_WORKER_LEGACY_BLOB_DRIFT",
    )
    registry = deepcopy(dict(snapshot.get("legacy_registry") or {}))
    try:
        validated = legacy_registry.validate_registry(registry)
    except Exception as exc:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_REGISTRY_INVALID") from exc
    if int(registry.get("revision")) != int(bridge.get("revision")):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_REVISION_DRIFT")
    if validated["state_hash"] != _hash64(bridge.get("state_hash"), "legacy_state_hash"):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_STATE_HASH_DRIFT")
    observed_thaws = sorted(str(item.get("thaw_id") or "") for item in registry.get("active_thaws") or [])
    expected_thaws = sorted(str(item or "") for item in bridge.get("active_thaw_ids") or [])
    if observed_thaws != expected_thaws:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_ACTIVE_THAW_DRIFT")
    return manifest, registry


def _build_targets(packet: Mapping[str, Any], previous_manifest: Mapping[str, Any], registry: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    repository = _identity(packet.get("repository"), "repository")
    workstream = _identity(packet.get("workstream"), "workstream")
    freeze_token = _identity(packet.get("freeze_token"), "freeze_token")
    candidate_sha = _sha(packet.get("candidate_sha"), "candidate_sha")
    merged_main_sha = _sha(packet.get("merged_main_sha"), "merged_main_sha")
    proof_digest = str(packet.get("proof_digest") or "").strip().lower()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", proof_digest):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_PROOF_DIGEST_INVALID")

    try:
        record = bootstrap.build_freeze_record(
            workstream=workstream,
            freeze_token=freeze_token,
            merged_main_sha=merged_main_sha,
            candidate_sha=candidate_sha,
            proof_digest=proof_digest,
            artifacts=dict(packet.get("artifacts") or {}),
        )
    except Exception as exc:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_FREEZE_RECORD_INVALID") from exc
    record_path = f"{RECORD_DIR}/{freeze_token}.json"
    record_text = _canonical_text(record)
    record_blob_sha = _git_blob_sha(record_text)

    try:
        manifest = bootstrap.build_manifest(
            previous=previous_manifest,
            freeze_token=freeze_token,
            record_path=record_path,
            record_blob_sha=record_blob_sha,
            merged_main_sha=merged_main_sha,
        )
        bootstrap.validate_manifest_transition(previous_manifest, manifest)
    except Exception as exc:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_TARGET_MANIFEST_INVALID") from exc

    active_thaws = sorted(str(item.get("thaw_id") or "") for item in registry.get("active_thaws") or [])
    bridge_cfg = dict(packet.get("legacy_bridge") or {})
    bridge_record: dict[str, Any] = {
        "version": BRIDGE_VERSION,
        "repository": repository,
        "workstream": workstream,
        "freeze_token": freeze_token,
        "ledger_ref": LEDGER_REF,
        "ledger_revision": manifest["revision"],
        "ledger_state_hash": manifest["state_hash"],
        "legacy_registry_ref": legacy_registry.REGISTRY_REF,
        "legacy_registry_head_sha": _sha(bridge_cfg.get("head_sha"), "legacy_head_sha"),
        "legacy_registry_blob_sha": _sha(bridge_cfg.get("registry_blob_sha"), "legacy_registry_blob_sha"),
        "legacy_registry_revision": int(registry["revision"]),
        "legacy_registry_state_hash": str(registry["state_hash"]),
        "active_thaw_ids_preserved": active_thaws,
        "retired_thaw_ids": [],
        "safe_migration_path": "LEDGER_AUTHORITATIVE_LEGACY_READ_ONLY_BRIDGE",
        "legacy_registry_mutation": False,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "product_runtime_mutation": False,
        "model_projection_mutation": False,
    }
    bridge_record["bridge_hash"] = _hash_without(bridge_record, "bridge_hash")
    bridge_path = f"{BRIDGE_DIR}/{freeze_token}.json"
    files = {
        record_path: record_text,
        bridge_path: _canonical_text(bridge_record),
        MANIFEST_PATH: _canonical_text(manifest),
    }
    return files, {
        "record": record,
        "record_path": record_path,
        "bridge": bridge_record,
        "bridge_path": bridge_path,
        "manifest": manifest,
    }


def finalize_certified_packet(packet: Mapping[str, Any], *, backend: Any) -> dict[str, Any]:
    """Finalize one certified packet with one CAS write and exact readback.

    The backend owns transport only. It must expose: repository, workstream,
    snapshot(), cas_commit(...), read_ref(ref), and read_json(ref, path).
    This function never retries a deterministic failure.
    """
    _validate_packet_identity(packet, backend)
    before = deepcopy(dict(backend.snapshot()))
    manifest, registry = _validate_preconditions(packet, before)
    files, target = _build_targets(packet, manifest, registry)

    expected = dict(packet["expected_ledger"])
    for immutable_path in (target["record_path"], target["bridge_path"]):
        try:
            existing_blob = backend.read_blob_sha(LEDGER_REF, immutable_path)
        except Exception as exc:
            raise FinalizationWorkerFailure("FINALIZATION_WORKER_TARGET_PATH_CHECK_FAILED") from exc
        if existing_blob is not None:
            raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_TARGET_PATH_EXISTS:{immutable_path}")

    try:
        write_result = backend.cas_commit(
            ref=LEDGER_REF,
            expected_head_sha=_sha(expected["head_sha"], "ledger_head_sha"),
            expected_manifest_blob_sha=_sha(expected["manifest_blob_sha"], "manifest_blob_sha"),
            files=files,
        )
    except Exception as exc:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_CAS_WRITE_FAILED") from exc
    commit_sha = _sha((write_result or {}).get("commit_sha"), "commit_sha")

    if str(backend.read_ref(LEDGER_REF) or "").lower() != commit_sha:
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_READBACK_MISMATCH:REF")
    for path, expected_value in (
        (target["record_path"], target["record"]),
        (target["bridge_path"], target["bridge"]),
        (MANIFEST_PATH, target["manifest"]),
    ):
        actual = backend.read_json(LEDGER_REF, path)
        if actual != expected_value:
            raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_READBACK_MISMATCH:{path}")
        try:
            observed_blob = str(backend.read_blob_sha(LEDGER_REF, path) or "").strip().lower()
        except Exception as exc:
            raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_READBACK_BLOB_UNAVAILABLE:{path}") from exc
        expected_blob = _git_blob_sha(files[path])
        if observed_blob != expected_blob:
            raise FinalizationWorkerFailure(f"FINALIZATION_WORKER_READBACK_BLOB_MISMATCH:{path}")

    after = deepcopy(dict(backend.snapshot()))
    if (
        after.get("legacy_head_sha") != before.get("legacy_head_sha")
        or after.get("legacy_registry_blob_sha") != before.get("legacy_registry_blob_sha")
        or after.get("legacy_registry") != before.get("legacy_registry")
    ):
        raise FinalizationWorkerFailure("FINALIZATION_WORKER_LEGACY_REGISTRY_MUTATED")

    return {
        "status": "GREEN_FROZEN",
        "decision": "FINALIZATION_WORKER_GREEN_FROZEN",
        "version": VERSION,
        "workstream": packet["workstream"],
        "freeze_token": packet["freeze_token"],
        "candidate_sha": str(packet["candidate_sha"]).lower(),
        "merged_main_sha": str(packet["merged_main_sha"]).lower(),
        "commit_sha": commit_sha,
        "manifest_revision": target["manifest"]["revision"],
        "manifest_state_hash": target["manifest"]["state_hash"],
        "legacy_registry_state_hash": registry["state_hash"],
        "legacy_thaws_preserved": target["bridge"]["active_thaw_ids_preserved"],
        "write_attempts": 1,
        "readback_verified": True,
        "legacy_registry_mutation": LEGACY_REGISTRY_MUTATION,
        "render_dependency": RENDER_DEPENDENCY,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        "product_runtime_mutation": PRODUCT_RUNTIME_MUTATION,
        "model_projection_mutation": MODEL_PROJECTION_MUTATION,
    }
