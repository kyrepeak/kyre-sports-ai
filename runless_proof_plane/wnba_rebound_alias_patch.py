from __future__ import annotations

import base64
import json

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

BRANCH = "api2-wnba-data-step2-rebound-alias-r1"
EXPECTED_HEAD = "dc64446ff23cb29774f2c8ed3c455534f9129910"
PATH = "sports_api/wnba_pra_speed_v3_step3_espn_history.py"
EXPECTED_BLOB = "fa4f7a99a6c73984e90e938efc506711a9f614c6"
OLD = '"rebounds": _to_int(_pick(stats, "REB", "rebounds")),'
NEW = '"rebounds": _to_int(_pick(stats, "REB", "rebounds", "totalRebounds")),'
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def execute(client):
    if client.branch_sha(BRANCH) != EXPECTED_HEAD:
        raise RuntimeError("WNBA_REBOUND_ALIAS_BRANCH_DRIFT")

    registry_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not registry_raw or registry_raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_REBOUND_ALIAS_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(registry_raw["content"]).decode())
    validate_registry(registry)
    for checkpoint, entry in (registry.get("entries") or {}).items():
        if PATH in ((entry or {}).get("artifacts") or {}):
            raise RuntimeError("WNBA_REBOUND_ALIAS_FROZEN_OWNER:" + str(checkpoint))
    for thaw in registry.get("active_thaws") or []:
        if PATH in ((thaw or {}).get("files") or {}):
            raise RuntimeError("WNBA_REBOUND_ALIAS_EXISTING_THAW:" + str(thaw.get("thaw_id") or ""))

    raw = client.content(PATH, ref=BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_REBOUND_ALIAS_SOURCE_READ_FAILED")
    if str(raw.get("sha") or "") != EXPECTED_BLOB:
        raise RuntimeError("WNBA_REBOUND_ALIAS_SOURCE_BLOB_DRIFT")
    text = base64.b64decode(raw["content"]).decode()
    if text.count(OLD) != 1:
        raise RuntimeError("WNBA_REBOUND_ALIAS_OLD_EXPRESSION_COUNT")
    if NEW in text:
        raise RuntimeError("WNBA_REBOUND_ALIAS_ALREADY_PRESENT")

    client.update_content(
        PATH,
        text.replace(OLD, NEW, 1),
        BRANCH,
        "fix: preserve ESPN totalRebounds in WNBA history",
        EXPECTED_BLOB,
    )
    new_head = client.branch_sha(BRANCH)
    verify = client.content(PATH, ref=new_head)
    if not verify or verify.get("encoding") != "base64":
        raise RuntimeError("WNBA_REBOUND_ALIAS_READBACK_FAILED")
    after = base64.b64decode(verify["content"]).decode()
    if NEW not in after or OLD in after:
        raise RuntimeError("WNBA_REBOUND_ALIAS_PATCH_READBACK_FAILED")
    return {
        "status": "GREEN",
        "branch": BRANCH,
        "old_head": EXPECTED_HEAD,
        "candidate_sha": new_head,
        "old_blob": EXPECTED_BLOB,
        "candidate_blob": str(verify.get("sha") or ""),
        "registry_revision": int(registry.get("revision") or 0),
        "registry_state_hash": str(registry.get("state_hash") or ""),
        "frozen_owner": False,
        "active_thaw": False,
        "mutation_files": [PATH],
    }


def install_startup(app):
    app.state.wnba_rebound_alias_patch = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_rebound_alias_patch = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_rebound_alias_patch = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]}
        print("WNBA_REBOUND_ALIAS_PATCH=" + json.dumps(app.state.wnba_rebound_alias_patch, sort_keys=True), flush=True)
    return app
