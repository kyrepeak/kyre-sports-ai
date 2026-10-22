from __future__ import annotations

import hashlib
import json
from typing import Any

_REQUIRED = (
    "proof_id", "task_id", "project", "workstream", "step", "candidate_sha",
    "artifact_map", "dependency_map", "registry_before", "registry_after",
    "evidence_digests", "failure_class",
)


def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical({k: v for k, v in payload.items() if k != "digest"})).hexdigest()


def validate_receipt(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        raise ValueError("RUNLESS_V2_RECEIPT_NOT_OBJECT")
    missing = [key for key in _REQUIRED if key not in payload]
    if missing:
        raise ValueError("RUNLESS_V2_RECEIPT_MISSING:" + ",".join(missing))
    if payload.get("digest") != digest_payload(payload):
        raise ValueError("RUNLESS_V2_RECEIPT_TAMPERED")
    candidate = str(payload.get("candidate_sha") or "")
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise ValueError("RUNLESS_V2_RECEIPT_BAD_SHA")
    return True


def finalization_proof_digest(receipt: dict[str, Any]) -> str:
    validate_receipt(receipt)
    return "sha256:" + receipt["digest"]
