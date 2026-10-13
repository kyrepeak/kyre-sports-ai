from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping

VERSION = "UNIVERSAL_SPORTS_FINALIZATION_BOOTSTRAP_V1"
MANIFEST_VERSION = "UNIVERSAL_SPORTS_FINALIZATION_LEDGER_V2_MANIFEST"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PROOF = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(dict(value)).encode("utf-8")).hexdigest()


def _hash_without(value: Mapping[str, Any], field: str) -> str:
    raw = deepcopy(dict(value))
    raw.pop(field, None)
    return canonical_hash(raw)


def _require_sha(name: str, value: Any) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise ValueError(f"FINALIZATION_INVALID_{name.upper()}")
    return text


def _require_proof(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not _PROOF.fullmatch(text):
        raise ValueError("FINALIZATION_INVALID_PROOF_DIGEST")
    return text


def _artifact_map(artifacts: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise ValueError("FINALIZATION_ARTIFACTS_REQUIRED")
    out: dict[str, str] = {}
    for path, blob in artifacts.items():
        key = str(path or "").strip()
        if not key or key in out:
            raise ValueError("FINALIZATION_INVALID_ARTIFACT_PATH")
        out[key] = _require_sha("artifact_blob", blob)
    return dict(sorted(out.items()))


def build_freeze_record(
    *,
    workstream: str,
    freeze_token: str,
    merged_main_sha: str,
    candidate_sha: str,
    proof_digest: str,
    artifacts: Mapping[str, str],
) -> dict[str, Any]:
    ws = str(workstream or "").strip()
    token = str(freeze_token or "").strip()
    if not ws or not token:
        raise ValueError("FINALIZATION_IDENTITY_REQUIRED")
    record: dict[str, Any] = {
        "version": VERSION,
        "workstream": ws,
        "freeze_token": token,
        "merged_main_sha": _require_sha("merged_main_sha", merged_main_sha),
        "candidate_sha": _require_sha("candidate_sha", candidate_sha),
        "proof_digest": _require_proof(proof_digest),
        "artifacts": _artifact_map(artifacts),
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    record["record_hash"] = _hash_without(record, "record_hash")
    return record


def validate_freeze_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("FINALIZATION_RECORD_NOT_OBJECT")
    raw = deepcopy(dict(record))
    if raw.get("version") != VERSION:
        raise ValueError("FINALIZATION_RECORD_VERSION_DRIFT")
    if not str(raw.get("workstream") or "").strip() or not str(raw.get("freeze_token") or "").strip():
        raise ValueError("FINALIZATION_IDENTITY_REQUIRED")
    _require_sha("merged_main_sha", raw.get("merged_main_sha"))
    _require_sha("candidate_sha", raw.get("candidate_sha"))
    _require_proof(raw.get("proof_digest"))
    normalized_artifacts = _artifact_map(raw.get("artifacts") or {})
    if raw.get("artifacts") != normalized_artifacts:
        raise ValueError("FINALIZATION_ARTIFACT_MAP_NOT_CANONICAL")
    if raw.get("render_dependency") is not False:
        raise ValueError("FINALIZATION_RENDER_DEPENDENCY_FORBIDDEN")
    if raw.get("github_actions_fallback") != 0:
        raise ValueError("FINALIZATION_GITHUB_ACTIONS_FALLBACK_FORBIDDEN")
    if raw.get("legacy_registry_mutation") is not False:
        raise ValueError("FINALIZATION_LEGACY_REGISTRY_MUTATION_FORBIDDEN")
    if str(raw.get("record_hash") or "") != _hash_without(raw, "record_hash"):
        raise ValueError("FINALIZATION_RECORD_HASH_MISMATCH")
    return raw


def build_manifest(
    *,
    previous: Mapping[str, Any] | None,
    freeze_token: str,
    record_path: str,
    record_blob_sha: str,
    merged_main_sha: str,
) -> dict[str, Any]:
    token = str(freeze_token or "").strip()
    path = str(record_path or "").strip()
    if not token or not path:
        raise ValueError("FINALIZATION_MANIFEST_IDENTITY_REQUIRED")
    if previous is None:
        revision = 1
        previous_hash = None
    else:
        previous_valid = _validate_manifest_self(previous)
        revision = int(previous_valid["revision"]) + 1
        previous_hash = str(previous_valid["state_hash"])
    target: dict[str, Any] = {
        "version": MANIFEST_VERSION,
        "revision": revision,
        "previous_state_hash": previous_hash,
        "latest_freeze_token": token,
        "latest_record_path": path,
        "latest_record_blob_sha": _require_sha("record_blob_sha", record_blob_sha),
        "latest_merged_main_sha": _require_sha("merged_main_sha", merged_main_sha),
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    target["state_hash"] = _hash_without(target, "state_hash")
    return target


def _validate_manifest_self(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise ValueError("FINALIZATION_MANIFEST_NOT_OBJECT")
    raw = deepcopy(dict(manifest))
    if raw.get("version") != MANIFEST_VERSION:
        raise ValueError("FINALIZATION_MANIFEST_VERSION_DRIFT")
    try:
        revision = int(raw.get("revision"))
    except (TypeError, ValueError) as exc:
        raise ValueError("FINALIZATION_MANIFEST_REVISION_INVALID") from exc
    if revision <= 0:
        raise ValueError("FINALIZATION_MANIFEST_REVISION_INVALID")
    if not str(raw.get("latest_freeze_token") or "").strip() or not str(raw.get("latest_record_path") or "").strip():
        raise ValueError("FINALIZATION_MANIFEST_IDENTITY_REQUIRED")
    _require_sha("record_blob_sha", raw.get("latest_record_blob_sha"))
    _require_sha("merged_main_sha", raw.get("latest_merged_main_sha"))
    if raw.get("render_dependency") is not False:
        raise ValueError("FINALIZATION_RENDER_DEPENDENCY_FORBIDDEN")
    if raw.get("github_actions_fallback") != 0:
        raise ValueError("FINALIZATION_GITHUB_ACTIONS_FALLBACK_FORBIDDEN")
    if raw.get("legacy_registry_mutation") is not False:
        raise ValueError("FINALIZATION_LEGACY_REGISTRY_MUTATION_FORBIDDEN")
    if str(raw.get("state_hash") or "") != _hash_without(raw, "state_hash"):
        raise ValueError("FINALIZATION_MANIFEST_HASH_MISMATCH")
    return raw


def validate_manifest_transition(
    previous: Mapping[str, Any] | None,
    target: Mapping[str, Any],
) -> dict[str, Any]:
    current = _validate_manifest_self(target)
    if previous is None:
        if current["revision"] != 1 or current.get("previous_state_hash") is not None:
            raise ValueError("FINALIZATION_GENESIS_PRECONDITION_MISMATCH")
        return current

    prior = _validate_manifest_self(previous)
    if current["revision"] != int(prior["revision"]) + 1:
        raise ValueError("FINALIZATION_MANIFEST_REVISION_NOT_MONOTONIC")
    if current.get("previous_state_hash") != prior["state_hash"]:
        raise ValueError("FINALIZATION_MANIFEST_STALE_PRECONDITION")
    return current
