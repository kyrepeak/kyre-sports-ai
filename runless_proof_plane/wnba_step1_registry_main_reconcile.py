from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry
from .registry import GithubRegistryBackend, _state_hash

EXPECTED_SOURCE_MAIN = "219ed8367207538a909986841e66807e408feede"
TARGET_MAIN = "42b9bcf3465af8aca41141a1d2713d5731ea6c00"
CANDIDATE = "a6570bfc5f8cdc4fb78f6d0ec385afd906b82791"
EXPECTED_REVISION = 185
EXPECTED_HASH = "c724272b73372ececa74be33c8310b2fae7586ce9fae4e6bafe735918587bea3"


def execute(client):
    if str(client.branch_sha("main")) != TARGET_MAIN:
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_MAIN_DRIFT")

    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    validated = validate_registry(current)
    source = str(current.get("source_main_sha") or "")

    main_tree = client.tree_blobs(TARGET_MAIN)
    candidate_tree = client.tree_blobs(CANDIDATE)
    candidate_frozen_delta = sorted(
        path
        for path in validated["artifacts"]
        if str(candidate_tree.get(path) or "") != str(main_tree.get(path) or "")
    )
    if candidate_frozen_delta:
        raise RuntimeError(
            "WNBA_STEP1_REGISTRY_RECONCILE_CANDIDATE_FROZEN_DELTA:"
            + ",".join(candidate_frozen_delta[:20])
        )

    inherited = sorted(
        path
        for path, expected in validated["artifacts"].items()
        if str(main_tree.get(path) or "") != str(expected)
    )

    if source == TARGET_MAIN:
        return {
            "status": "GREEN",
            "decision": "WNBA_STEP1_REGISTRY_MAIN_ALREADY_RECONCILED",
            "revision": int(current["revision"]),
            "state_hash": str(current["state_hash"]),
            "source_main_sha": source,
            "inherited_frozen_path_count": len(inherited),
            "candidate_frozen_delta_count": 0,
        }

    if source != EXPECTED_SOURCE_MAIN:
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_SOURCE_DRIFT")
    if int(current.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_REVISION_DRIFT")
    if str(current.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_HASH_DRIFT")

    updated = deepcopy(current)
    updated["source_main_sha"] = TARGET_MAIN
    updated["revision"] = EXPECTED_REVISION + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    if updated.get("entries") != current.get("entries"):
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_ENTRY_MUTATION")
    if updated.get("active_thaws") != current.get("active_thaws"):
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_THAW_MUTATION")

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    client.update_content(
        backend.path,
        text,
        backend.branch,
        "registry: advance source main; preserve inherited frozen state for WNBA Step 1",
        backend._blob_sha,
    )

    readback = backend.read_registry()
    if (
        str(readback.get("source_main_sha") or "") != TARGET_MAIN
        or int(readback.get("revision") or -1) != EXPECTED_REVISION + 1
        or str(readback.get("state_hash") or "") != str(updated["state_hash"])
        or readback.get("entries") != current.get("entries")
        or readback.get("active_thaws") != current.get("active_thaws")
    ):
        raise RuntimeError("WNBA_STEP1_REGISTRY_RECONCILE_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "decision": "WNBA_STEP1_REGISTRY_MAIN_RECONCILED_WITH_INHERITED_STATE",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "source_main_sha": str(readback["source_main_sha"]),
        "inherited_frozen_path_count": len(inherited),
        "candidate_frozen_delta_count": 0,
        "entries_mutated": 0,
        "thaws_mutated": 0,
    }


def install_startup(app):
    app.state.wnba_step1_registry_reconcile = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_step1_registry_reconcile = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_step1_registry_reconcile = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "WNBA_STEP1_REGISTRY_MAIN_RECONCILE="
            + json.dumps(app.state.wnba_step1_registry_reconcile, sort_keys=True),
            flush=True,
        )

    return app
