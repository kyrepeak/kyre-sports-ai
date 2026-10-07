from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
WINNER_PR = 1424
WINNER_SHA = "6bfe5a42f08cb2c20b4ce3efa5dd6b3e8bc75e56"
WINNER_FILES = {
    "wnba_pra_game_center_v2_step3.py",
    "wnba_pra_game_center_stats_hydration_v1.py",
    "tests/test_wnba_data_step2_live_hydration.py",
}
LOSER_THAW = "THAW-API2-WNBA-DATA-STEP2-LIVE-HYDRATION-R1"
EXPECTED_REVISION = 150
EXPECTED_HASH = "d96db7f9718aa2507a40f3a46bba3db5f705b690c6c9406de53fe668fa54752e"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("AUTHORITY_RECONCILE_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{WINNER_PR}") or {}
    if str(pr.get("state") or "") != "open":
        raise RuntimeError("AUTHORITY_RECONCILE_WINNER_PR_NOT_OPEN")
    if str((pr.get("head") or {}).get("sha") or "") != WINNER_SHA:
        raise RuntimeError("AUTHORITY_RECONCILE_WINNER_HEAD_DRIFT")
    if str((pr.get("base") or {}).get("sha") or "") != MAIN_SHA:
        raise RuntimeError("AUTHORITY_RECONCILE_WINNER_BASE_DRIFT")
    files = client.request("GET", f"/pulls/{WINNER_PR}/files?per_page=100") or []
    changed = {str(item.get("filename") or "") for item in files}
    if changed != WINNER_FILES:
        raise RuntimeError("AUTHORITY_RECONCILE_WINNER_SCOPE_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("AUTHORITY_RECONCILE_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("AUTHORITY_RECONCILE_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("AUTHORITY_RECONCILE_HASH_DRIFT")

    frozen_paths = {}
    for token, entry in (registry.get("entries") or {}).items():
        for path, blob in (entry.get("artifacts") or {}).items():
            frozen_paths.setdefault(str(path), []).append((str(token), str(blob)))
    overlap = WINNER_FILES & set(frozen_paths)
    if overlap:
        raise RuntimeError("AUTHORITY_RECONCILE_WINNER_FROZEN_OVERLAP:" + ",".join(sorted(overlap)))

    thaws = list(registry.get("active_thaws") or [])
    matches = [item for item in thaws if item.get("thaw_id") == LOSER_THAW]
    if len(matches) != 1:
        raise RuntimeError("AUTHORITY_RECONCILE_LOSER_THAW_MISSING")
    loser = matches[0]
    if set((loser.get("files") or {}).keys()) != {"wnba_players_v25.py"}:
        raise RuntimeError("AUTHORITY_RECONCILE_LOSER_SCOPE_DRIFT")

    retained = [deepcopy(item) for item in thaws if item.get("thaw_id") != LOSER_THAW]
    updated = deepcopy(registry)
    updated["active_thaws"] = retained
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: retire competing {LOSER_THAW}",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    if any(item.get("thaw_id") == LOSER_THAW for item in rb.get("active_thaws", [])):
        raise RuntimeError("AUTHORITY_RECONCILE_THAW_RETIRE_FAILED")
    if list(rb.get("active_thaws") or []) != retained:
        raise RuntimeError("AUTHORITY_RECONCILE_UNRELATED_THAW_DRIFT")
    if int(rb.get("revision") or -1) != EXPECTED_REVISION + 1:
        raise RuntimeError("AUTHORITY_RECONCILE_REVISION_READBACK_FAILED")
    return {
        "status": "GREEN",
        "winner_pr": WINNER_PR,
        "winner_sha": WINNER_SHA,
        "retired_thaw": LOSER_THAW,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "unrelated_thaws_preserved": len(retained),
        "winner_frozen_overlap": 0,
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_live_hydration_authority_reconcile = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_live_hydration_authority_reconcile = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_live_hydration_authority_reconcile = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_LIVE_HYDRATION_AUTHORITY_RECONCILE=" + json.dumps(app.state.wnba_live_hydration_authority_reconcile, sort_keys=True), flush=True)
    return app
