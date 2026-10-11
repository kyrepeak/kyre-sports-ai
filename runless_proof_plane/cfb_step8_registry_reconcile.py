from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.frozen_registry_auto_reconciler_v1 import plan_auto_reconciliation
from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    authorize_scope,
    validate_state as validate_scope_state,
    verify_scope_identity,
)

from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
MERGED_THAW_TARGET = "a1fbecbb5d5dd96d71ad21d4961bf8407c80be9e"
EXPECTED_REVISION = 269
EXPECTED_HASH = "8165c8a50fd2c524b9d23ec512e64e3308f0addb43135d9a18a6ae8d5f89396c"
EXPECTED_SOURCE_MAIN = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
EXPECTED_THAW = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
EXPECTED_OTHER_THAWS = {
    "THAW-CFB-GT-PAGE2-STEP7-REPAIR-R1",
    "THAW-CFB-GT-PAGE2-STEP7-REVIEW-RED-R1",
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
}
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-33230837D3158A060679D8BD"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-recovery-finalization"


class Step8RegistryReconcileFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise Step8RegistryReconcileFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _json_text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _authorize(client, registry):
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_scope_state(_decode(raw))
    holders = [h for h in state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER]
    if len(holders) != 1:
        raise Step8RegistryReconcileFailure("RECONCILE_LEASE_NOT_UNIQUE")
    holder = holders[0]
    now = datetime.now(timezone.utc)
    expiry = datetime.fromisoformat(str(holder["expires_at_utc"]).replace("Z", "+00:00"))
    if now >= expiry:
        raise Step8RegistryReconcileFailure("RECONCILE_LEASE_EXPIRED")
    identity = verify_scope_identity(
        holder["scope"],
        observed_resource_identity={"main_sha": MAIN_SHA, "registry_state_hash": str(registry["state_hash"])},
    )
    if identity.get("allowed") is not True:
        raise Step8RegistryReconcileFailure("RECONCILE_RESOURCE_IDENTITY_DRIFT")
    gate = authorize_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        now_utc=now.isoformat().replace("+00:00", "Z"),
        action_scope={
            "write_paths": [REGISTRY_PATH],
            "dependency_tokens": ["cfb:game-total:step8", "registry:cfb-game-total:step8"],
            "shared_resources": ["ref:monster-frozen-artifact-registry"],
            "resource_identity": {},
            "exclusive": False,
        },
    )
    if gate.get("allowed") is not True:
        raise Step8RegistryReconcileFailure("RECONCILE_ACTION_SCOPE_NOT_AUTHORIZED")


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8RegistryReconcileFailure("MAIN_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise Step8RegistryReconcileFailure("REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise Step8RegistryReconcileFailure("REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != EXPECTED_SOURCE_MAIN:
        raise Step8RegistryReconcileFailure("REGISTRY_SOURCE_MAIN_DRIFT")

    _authorize(client, registry)

    thaw_ids = {str(row.get("thaw_id") or "") for row in registry.get("active_thaws", [])}
    if thaw_ids != EXPECTED_OTHER_THAWS | {EXPECTED_THAW}:
        raise Step8RegistryReconcileFailure("ACTIVE_THAW_SET_DRIFT")

    main_tree = client.tree_blobs(MAIN_SHA)
    planned = plan_auto_reconciliation(
        registry,
        actual_blobs=main_tree,
        main_sha=MAIN_SHA,
        merged_authority_heads=[MERGED_THAW_TARGET],
    )
    if planned.get("decision") != "AUTO_RECONCILIATION_PLANNED" or planned.get("apply_allowed") is not True:
        raise Step8RegistryReconcileFailure("AUTO_RECONCILIATION_NOT_AUTHORIZED:" + str(planned.get("decision")))
    authorities = planned.get("authorized_thaws") or []
    if {str(row.get("thaw_id") or "") for row in authorities} != {EXPECTED_THAW}:
        raise Step8RegistryReconcileFailure("RECONCILIATION_AUTHORITY_SET_DRIFT")
    retired = set(planned.get("retired_empty_thaw_grants") or [])
    if retired != {EXPECTED_THAW}:
        raise Step8RegistryReconcileFailure("RECONCILIATION_RETIRED_THAW_DRIFT")
    next_registry = planned.get("planned_registry")
    if not isinstance(next_registry, dict):
        raise Step8RegistryReconcileFailure("PLANNED_REGISTRY_MISSING")
    validate_registry(next_registry)
    remaining = {str(row.get("thaw_id") or "") for row in next_registry.get("active_thaws", [])}
    if remaining != EXPECTED_OTHER_THAWS:
        raise Step8RegistryReconcileFailure("UNRELATED_THAW_PRESERVATION_FAILED")
    if str(next_registry.get("source_main_sha") or "") != MAIN_SHA:
        raise Step8RegistryReconcileFailure("NEXT_SOURCE_MAIN_DRIFT")

    client.update_content(
        REGISTRY_PATH,
        _json_text(next_registry),
        backend.branch,
        "registry: reconcile merged CFB Game Total Step 8 thaw before recovery proof",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if readback != next_registry:
        raise Step8RegistryReconcileFailure("REGISTRY_READBACK_MISMATCH")
    return {
        "status": "GREEN",
        "decision": "CFB_STEP8_REGISTRY_RECONCILED",
        "previous_revision": EXPECTED_REVISION,
        "revision": int(readback["revision"]),
        "previous_state_hash": EXPECTED_HASH,
        "state_hash": str(readback["state_hash"]),
        "source_main_sha": str(readback["source_main_sha"]),
        "retired_thaw": EXPECTED_THAW,
        "unrelated_thaws_preserved": len(EXPECTED_OTHER_THAWS),
        "retry_after_state_change_only": True,
    }


def install_startup(app):
    app.state.cfb_step8_registry_reconcile = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_step8_registry_reconcile = execute(app)
        except Exception as exc:
            app.state.cfb_step8_registry_reconcile = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5000],
            }
        print("CFB_STEP8_REGISTRY_RECONCILE=" + json.dumps(app.state.cfb_step8_registry_reconcile, sort_keys=True, default=str), flush=True)

    return app
