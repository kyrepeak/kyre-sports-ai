from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import authorize_scope, validate_state as validate_scope_state, verify_scope_identity

from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
CANDIDATE_SHA = "b8a693bdce3f0e17a602e67fe89a60f63457b15a"
EXPECTED_REVISION = 271
EXPECTED_HASH = "715f190c2ef77cca82e11c4d4fc50620a2a2fdcfe75b92a94274bb5ed435cd30"
THAW_ID = "THAW-CFB-GT-STEP8-STREAMLIT-REDEPLOY-R1"
PATH = "requirements.txt"
FROM_BLOB = "1022d95a71b3c04aa5310b5057de74978e4cffa4"
TO_BLOB = "7b2e379fc2f519c9bb8700a14b33b70d4eb0f581"
EXPECTED_EXISTING_THAWS = {
    "THAW-CFB-GT-PAGE2-STEP7-REPAIR-R1",
    "THAW-CFB-GT-PAGE2-STEP7-REVIEW-RED-R1",
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
}
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-8A71E2F3D54B690C21F4A83D"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-redeploy-thaw"


class Step8RedeployThawFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise Step8RedeployThawFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _json_text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8RedeployThawFailure("MAIN_DRIFT")
    if client.branch_sha("cfb-game-total-step8-streamlit-redeploy-recovery-v1") != CANDIDATE_SHA:
        raise Step8RedeployThawFailure("CANDIDATE_HEAD_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION or str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise Step8RedeployThawFailure("REGISTRY_IDENTITY_DRIFT")
    if validated["artifacts"].get(PATH) != FROM_BLOB:
        raise Step8RedeployThawFailure("REQUIREMENTS_FROZEN_BASELINE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if main_tree.get(PATH) != FROM_BLOB or candidate_tree.get(PATH) != TO_BLOB:
        raise Step8RedeployThawFailure("REQUIREMENTS_BLOB_IDENTITY_DRIFT")

    existing_ids = {str(row.get("thaw_id") or "") for row in registry.get("active_thaws", [])}
    if existing_ids != EXPECTED_EXISTING_THAWS:
        raise Step8RedeployThawFailure("EXISTING_THAW_SET_DRIFT")

    lease_raw = client.content(LEASE_PATH, ref=LEASE_REF)
    lease_state = validate_scope_state(_decode(lease_raw))
    holders = [h for h in lease_state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER]
    if len(holders) != 1:
        raise Step8RedeployThawFailure("THAW_LEASE_NOT_UNIQUE")
    holder = holders[0]
    now = datetime.now(timezone.utc)
    if now >= datetime.fromisoformat(str(holder["expires_at_utc"]).replace("Z", "+00:00")):
        raise Step8RedeployThawFailure("THAW_LEASE_EXPIRED")
    ident = verify_scope_identity(holder["scope"], observed_resource_identity={"main_sha": MAIN_SHA, "registry_state_hash": EXPECTED_HASH})
    if ident.get("allowed") is not True:
        raise Step8RedeployThawFailure("THAW_RESOURCE_IDENTITY_DRIFT")
    gate = authorize_scope(
        lease_state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        now_utc=now.isoformat().replace("+00:00", "Z"),
        action_scope={
            "write_paths": [REGISTRY_PATH],
            "dependency_tokens": ["cfb:game-total:step8", "registry:requirements-redeploy-thaw"],
            "shared_resources": ["ref:monster-frozen-artifact-registry"],
            "resource_identity": {},
            "exclusive": False,
        },
    )
    if gate.get("allowed") is not True:
        raise Step8RedeployThawFailure("THAW_SCOPE_NOT_AUTHORIZED")

    next_registry = deepcopy(registry)
    next_registry["active_thaws"].append({
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    })
    next_registry["active_thaws"] = sorted(next_registry["active_thaws"], key=lambda row: str(row.get("thaw_id") or ""))
    next_registry["revision"] = EXPECTED_REVISION + 1
    next_registry["state_hash"] = _hash(_payload_without_hash(next_registry))
    validate_registry(next_registry)

    client.update_content(
        REGISTRY_PATH,
        _json_text(next_registry),
        backend.branch,
        "registry: authorize exact CFB Step8 Streamlit redeploy thaw",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if readback != next_registry:
        raise Step8RedeployThawFailure("THAW_REGISTRY_READBACK_MISMATCH")
    return {
        "status": "GREEN",
        "decision": "CFB_STEP8_REDEPLOY_EXACT_THAW_AUTHORIZED",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "thaw_id": THAW_ID,
        "target_head_sha": CANDIDATE_SHA,
        "path": PATH,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "unrelated_thaws_preserved": len(EXPECTED_EXISTING_THAWS),
    }


def install_startup(app):
    app.state.cfb_step8_redeploy_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_step8_redeploy_thaw = execute(app)
        except Exception as exc:
            app.state.cfb_step8_redeploy_thaw = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        print("CFB_STEP8_REDEPLOY_THAW=" + json.dumps(app.state.cfb_step8_redeploy_thaw, sort_keys=True, default=str), flush=True)

    return app
