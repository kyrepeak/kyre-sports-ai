from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

_RECORD_VERSION = "UNIVERSAL_SPORTS_FINALIZATION_BOOTSTRAP_V1"
_MANIFEST_VERSION = "UNIVERSAL_SPORTS_FINALIZATION_LEDGER_V2_MANIFEST"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PROOF = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _hash_without(value: dict[str, Any], field: str) -> str:
    raw = deepcopy(value)
    raw.pop(field, None)
    return _hash(raw)


def _validate_flags(value: dict[str, Any]) -> None:
    if value.get("render_dependency") is not False:
        raise ValueError("RUNLESS_V2_FINALIZATION_RENDER_DEPENDENCY_FORBIDDEN")
    if value.get("github_actions_fallback") != 0:
        raise ValueError("RUNLESS_V2_FINALIZATION_GITHUB_ACTIONS_FALLBACK_FORBIDDEN")
    if value.get("legacy_registry_mutation") is not False:
        raise ValueError("RUNLESS_V2_FINALIZATION_LEGACY_REGISTRY_MUTATION_FORBIDDEN")


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    raw = deepcopy(record)
    if raw.get("version") != _RECORD_VERSION:
        raise ValueError("RUNLESS_V2_FINALIZATION_RECORD_VERSION_DRIFT")
    if raw.get("record_hash") != _hash_without(raw, "record_hash"):
        raise ValueError("RUNLESS_V2_FINALIZATION_RECORD_HASH_MISMATCH")
    if not _SHA40.fullmatch(str(raw.get("candidate_sha") or "")):
        raise ValueError("RUNLESS_V2_FINALIZATION_CANDIDATE_INVALID")
    if not _SHA40.fullmatch(str(raw.get("merged_main_sha") or "")):
        raise ValueError("RUNLESS_V2_FINALIZATION_MERGED_MAIN_INVALID")
    if not _PROOF.fullmatch(str(raw.get("proof_digest") or "")):
        raise ValueError("RUNLESS_V2_FINALIZATION_PROOF_DIGEST_INVALID")
    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("RUNLESS_V2_FINALIZATION_ARTIFACTS_REQUIRED")
    if artifacts != dict(sorted(artifacts.items())):
        raise ValueError("RUNLESS_V2_FINALIZATION_ARTIFACT_MAP_NOT_CANONICAL")
    if any(not _SHA40.fullmatch(str(blob or "")) for blob in artifacts.values()):
        raise ValueError("RUNLESS_V2_FINALIZATION_ARTIFACT_BLOB_INVALID")
    _validate_flags(raw)
    return raw


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    raw = deepcopy(manifest)
    if raw.get("version") != _MANIFEST_VERSION:
        raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_VERSION_DRIFT")
    if raw.get("state_hash") != _hash_without(raw, "state_hash"):
        raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_HASH_MISMATCH")
    try:
        revision = int(raw.get("revision"))
    except (TypeError, ValueError) as exc:
        raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_REVISION_INVALID") from exc
    if revision <= 0:
        raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_REVISION_INVALID")
    if not _SHA40.fullmatch(str(raw.get("latest_record_blob_sha") or "")):
        raise ValueError("RUNLESS_V2_FINALIZATION_RECORD_BLOB_INVALID")
    if not _SHA40.fullmatch(str(raw.get("latest_merged_main_sha") or "")):
        raise ValueError("RUNLESS_V2_FINALIZATION_MERGED_MAIN_INVALID")
    _validate_flags(raw)
    return raw


def validate_finalization_closeout(
    record: dict[str, Any],
    manifest: dict[str, Any],
    *,
    expected_workstream: str,
    expected_freeze_token: str,
    expected_candidate_sha: str,
    expected_proof_digest: str,
    expected_merged_main_sha: str,
    previous_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    rec = validate_record(record)
    man = validate_manifest(manifest)

    if rec.get("workstream") != expected_workstream:
        raise ValueError("RUNLESS_V2_FINALIZATION_WORKSTREAM_MISMATCH")
    if rec.get("freeze_token") != expected_freeze_token:
        raise ValueError("RUNLESS_V2_FINALIZATION_FREEZE_TOKEN_MISMATCH")
    if rec.get("candidate_sha") != expected_candidate_sha:
        raise ValueError("RUNLESS_V2_FINALIZATION_CANDIDATE_MISMATCH")
    if rec.get("proof_digest") != expected_proof_digest:
        raise ValueError("RUNLESS_V2_FINALIZATION_PROOF_DIGEST_MISMATCH")
    if rec.get("merged_main_sha") != expected_merged_main_sha:
        raise ValueError("RUNLESS_V2_FINALIZATION_MERGED_MAIN_MISMATCH")

    if man.get("latest_freeze_token") != expected_freeze_token:
        raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_FREEZE_TOKEN_MISMATCH")
    if man.get("latest_merged_main_sha") != expected_merged_main_sha:
        raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_MERGED_MAIN_MISMATCH")

    if previous_manifest is None:
        if man["revision"] != 1 or man.get("previous_state_hash") is not None:
            raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_GENESIS_MISMATCH")
    else:
        prior = validate_manifest(previous_manifest)
        if man["revision"] != prior["revision"] + 1:
            raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_REVISION_NOT_MONOTONIC")
        if man.get("previous_state_hash") != prior["state_hash"]:
            raise ValueError("RUNLESS_V2_FINALIZATION_MANIFEST_STALE_PRECONDITION")

    return {
        "status": "GREEN",
        "workstream": expected_workstream,
        "freeze_token": expected_freeze_token,
        "candidate_sha": expected_candidate_sha,
        "proof_digest": expected_proof_digest,
        "merged_main_sha": expected_merged_main_sha,
        "record_hash": rec["record_hash"],
        "manifest_state_hash": man["state_hash"],
        "manifest_revision": man["revision"],
    }
