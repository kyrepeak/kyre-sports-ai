"""MONSTER Step 2G frozen checkpoint V1.

Pure deterministic checkpoint construction/validation. This module has no
network or mutation authority; the authoritative MONSTER execution lane writes
the resulting checkpoint to a dedicated MONSTER-only registry ref and reads it
back independently before any GREEN + FROZEN claim.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

VERSION = "MONSTER_STEP2G_FROZEN_CHECKPOINT_V1"
AUTHORITY = "MONSTER_ONLY"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_FOREIGN = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.IGNORECASE)


class FrozenCheckpointFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _walk(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, str):
        yield value


def _reject_foreign(value: Any) -> None:
    if any(_FOREIGN.search(text) for text in _walk(value)):
        raise FrozenCheckpointFailure("foreign-system evidence is forbidden in MONSTER Step 2G freeze")


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise FrozenCheckpointFailure(f"{label} must be an exact git SHA")
    return text


def _hash64(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    if not _DIGEST_RE.fullmatch(text):
        raise FrozenCheckpointFailure(f"{label} must be sha256")
    return text


def _identity(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FrozenCheckpointFailure(f"{label} is required")
    return text


def build_checkpoint(
    *,
    checkpoint_id: str,
    certified_monster_sha: str,
    certified_monster_tree_sha: str,
    production_runtime_sha: str,
    production_runtime_tree_sha: str,
    stable_alias: str,
    deployment_id: str,
    step2g_evidence_digest: str,
    proof_artifact_digest: str,
    rollback_anchor_sha: str,
    runtime_identity: Mapping[str, Any],
) -> dict[str, Any]:
    checkpoint = _identity(checkpoint_id, "checkpoint_id")
    if not checkpoint.startswith("MONSTER_") or not checkpoint.endswith("_FROZEN"):
        raise FrozenCheckpointFailure("checkpoint_id must be a MONSTER FROZEN checkpoint")
    if not isinstance(runtime_identity, Mapping):
        raise FrozenCheckpointFailure("runtime_identity must be an object")

    certified_sha = _sha(certified_monster_sha, "certified_monster_sha")
    certified_tree = _sha(certified_monster_tree_sha, "certified_monster_tree_sha")
    runtime_sha = _sha(production_runtime_sha, "production_runtime_sha")
    runtime_tree = _sha(production_runtime_tree_sha, "production_runtime_tree_sha")
    alias = _identity(stable_alias, "stable_alias")
    if not alias.startswith("https://"):
        raise FrozenCheckpointFailure("stable_alias must be HTTPS")
    deployment = _identity(deployment_id, "deployment_id")
    step2g_digest = _hash64(step2g_evidence_digest, "step2g_evidence_digest")
    proof_digest = _hash64(proof_artifact_digest, "proof_artifact_digest")
    rollback_sha = _sha(rollback_anchor_sha, "rollback_anchor_sha")
    runtime_packet = deepcopy(dict(runtime_identity))

    core = {
        "schema_version": 1,
        "version": VERSION,
        "authority": AUTHORITY,
        "status": "FROZEN",
        "checkpoint_id": checkpoint,
        "certified_monster_sha": certified_sha,
        "certified_monster_tree_sha": certified_tree,
        "production_runtime_sha": runtime_sha,
        "production_runtime_tree_sha": runtime_tree,
        "stable_alias": alias.rstrip("/"),
        "deployment_id": deployment,
        "step2g_evidence_digest": step2g_digest,
        "proof_artifact_digest": proof_digest,
        "rollback_anchor_sha": rollback_sha,
        "runtime_identity": runtime_packet,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    _reject_foreign(core)

    if runtime_packet.get("owner") != "MONSTER":
        raise FrozenCheckpointFailure("runtime_identity owner must be MONSTER")
    if runtime_packet.get("certified_monster_sha") not in {None, certified_sha}:
        raise FrozenCheckpointFailure("runtime certified MONSTER SHA mismatch")
    if runtime_packet.get("runtime_sha") not in {None, runtime_sha}:
        raise FrozenCheckpointFailure("runtime production SHA mismatch")

    checkpoint_out = dict(core)
    checkpoint_out["checkpoint_digest"] = _digest(core)
    return checkpoint_out


def validate_checkpoint(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FrozenCheckpointFailure("checkpoint must be an object")
    supplied = deepcopy(dict(value))
    _reject_foreign(supplied)
    digest = _hash64(supplied.get("checkpoint_digest"), "checkpoint_digest")
    core = dict(supplied)
    core.pop("checkpoint_digest", None)
    if digest != _digest(core):
        raise FrozenCheckpointFailure("checkpoint digest mismatch")
    if core.get("version") != VERSION or core.get("authority") != AUTHORITY:
        raise FrozenCheckpointFailure("checkpoint authority/version mismatch")
    if core.get("status") != "FROZEN":
        raise FrozenCheckpointFailure("checkpoint status must be FROZEN")

    rebuilt = build_checkpoint(
        checkpoint_id=core.get("checkpoint_id"),
        certified_monster_sha=core.get("certified_monster_sha"),
        certified_monster_tree_sha=core.get("certified_monster_tree_sha"),
        production_runtime_sha=core.get("production_runtime_sha"),
        production_runtime_tree_sha=core.get("production_runtime_tree_sha"),
        stable_alias=core.get("stable_alias"),
        deployment_id=core.get("deployment_id"),
        step2g_evidence_digest=core.get("step2g_evidence_digest"),
        proof_artifact_digest=core.get("proof_artifact_digest"),
        rollback_anchor_sha=core.get("rollback_anchor_sha"),
        runtime_identity=core.get("runtime_identity") or {},
    )
    if supplied != rebuilt:
        raise FrozenCheckpointFailure("checkpoint is non-canonical or has drifted")
    return {
        "status": "GREEN",
        "version": VERSION,
        "authority": AUTHORITY,
        "checkpoint_id": rebuilt["checkpoint_id"],
        "checkpoint_digest": rebuilt["checkpoint_digest"],
        "certified_monster_sha": rebuilt["certified_monster_sha"],
        "production_runtime_sha": rebuilt["production_runtime_sha"],
        "step2g_evidence_digest": rebuilt["step2g_evidence_digest"],
        "readback_verified": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
    }


if __name__ == "__main__":
    print(VERSION)
