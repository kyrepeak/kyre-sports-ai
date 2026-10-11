from __future__ import annotations

from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash, _payload_without_hash, validate_registry

from . import cfb_game_total_game_cards_step6_premerge as prior
from .registry import GithubRegistryBackend, REGISTRY_PATH

CANDIDATE_SHA = "2db2e429b2e3361d524d061aa617e0687071cced"
SUPERSEDED_CANDIDATE_SHA = "411c2155062596f321480fc5682b237dea27c924"
FAILURE_CLASS = "CODE_REVIEW_FINDING_AFTER_PREMERGE_PROOF"

_original_ensure_thaw = prior._ensure_thaw


def _json_text(payload: dict) -> str:
    import json
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _ensure_thaw_reconciled(client):
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == prior.THAW_ID]
    if len(matches) > 1:
        raise prior.GameCardsStep6PremergeFailure("THAW_DUPLICATE")
    if matches and str(matches[0].get("target_head_sha") or "") != CANDIDATE_SHA:
        stale = matches[0]
        if str(stale.get("target_head_sha") or "") != SUPERSEDED_CANDIDATE_SHA:
            raise prior.GameCardsStep6PremergeFailure("THAW_ID_COLLISION")
        desired = deepcopy(stale)
        desired["target_head_sha"] = CANDIDATE_SHA
        updated = deepcopy(registry)
        updated["active_thaws"] = [
            desired if g.get("thaw_id") == prior.THAW_ID else deepcopy(g)
            for g in registry.get("active_thaws", [])
        ]
        updated["active_thaws"] = sorted(updated["active_thaws"], key=lambda row: str(row.get("thaw_id") or ""))
        updated["revision"] = int(updated["revision"]) + 1
        updated.pop("state_hash", None)
        updated["state_hash"] = registry_hash(_payload_without_hash(updated))
        validate_registry(updated)
        client.update_content(
            REGISTRY_PATH,
            _json_text(updated),
            backend.branch,
            "registry: retarget CFB Game Total game cards Step 6 thaw after review fix",
            backend._blob_sha,
        )
        readback = backend.read_registry()
        validate_registry(readback)
        found = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == prior.THAW_ID]
        if len(found) != 1 or str(found[0].get("target_head_sha") or "") != CANDIDATE_SHA:
            raise prior.GameCardsStep6PremergeFailure("THAW_RETARGET_READBACK_MISMATCH")
    return _original_ensure_thaw(client)


def install_startup(app):
    prior.CANDIDATE_SHA = CANDIDATE_SHA
    prior._ensure_thaw = _ensure_thaw_reconciled
    return prior.install_startup(app)


__all__ = ["CANDIDATE_SHA", "FAILURE_CLASS", "SUPERSEDED_CANDIDATE_SHA", "install_startup"]
