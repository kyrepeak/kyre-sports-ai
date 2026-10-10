from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash, _payload_without_hash, validate_registry

from . import cfb_game_total_native_page1_shell_step3_premerge as prior
from .registry import GithubRegistryBackend, REGISTRY_PATH

CANDIDATE_SHA = "9afe37ec19d2b02aa204dd6158d55f2eae6dd726"


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _ensure_thaw_recovery(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != prior.MAIN_SHA:
        raise prior.NativePage1ShellStep3PremergeFailure("REGISTRY_SOURCE_MAIN_DRIFT")

    exact = {
        "thaw_id": prior.THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {
            prior.ROUTER_PATH: {
                "from_blob": prior.FROM_BLOB,
                "to_blob": prior.TO_BLOB,
            }
        },
    }
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == prior.THAW_ID]
    if len(matches) > 1:
        raise prior.NativePage1ShellStep3PremergeFailure("THAW_DUPLICATE")
    if matches == [exact]:
        return {
            "created": False,
            "retargeted": False,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
        }

    unrelated = [deepcopy(g) for g in registry.get("active_thaws", []) if g.get("thaw_id") != prior.THAW_ID]
    if matches:
        current = matches[0]
        if current.get("status") != "ACTIVE" or current.get("files") != exact["files"]:
            raise prior.NativePage1ShellStep3PremergeFailure("THAW_ID_COLLISION")

    updated = deepcopy(registry)
    updated["active_thaws"] = sorted(unrelated + [exact], key=lambda row: str(row.get("thaw_id") or ""))
    updated["revision"] = int(updated["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: retarget CFB Game Total Page1 shell Step 3 exact-head thaw after static-slice diagnosis",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    found = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == prior.THAW_ID]
    if found != [exact]:
        raise prior.NativePage1ShellStep3PremergeFailure("THAW_READBACK_MISMATCH")
    if [g for g in readback.get("active_thaws", []) if g.get("thaw_id") != prior.THAW_ID] != unrelated:
        raise prior.NativePage1ShellStep3PremergeFailure("UNRELATED_THAW_DRIFT")
    return {
        "created": not bool(matches),
        "retargeted": bool(matches),
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws", [])),
    }


def execute(app):
    prior.CANDIDATE_SHA = CANDIDATE_SHA
    prior._ensure_thaw = _ensure_thaw_recovery
    return prior.execute(app)


def install_startup(app):
    app.state.cfb_game_total_native_page1_shell_step3_recovery = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_native_page1_shell_step3_recovery = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_native_page1_shell_step3_recovery = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:4200],
            }
        print(
            "CFB_GAME_TOTAL_NATIVE_PAGE1_SHELL_STEP3_RECOVERY="
            + json.dumps(app.state.cfb_game_total_native_page1_shell_step3_recovery, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
