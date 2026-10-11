from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    authorize_scope,
    validate_state as validate_scope_state,
    verify_scope_identity,
)

from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
REGISTRY_SOURCE_MAIN = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
EXPECTED_REVISION = 269
EXPECTED_HASH = "8165c8a50fd2c524b9d23ec512e64e3308f0addb43135d9a18a6ae8d5f89396c"
STEP8_THAW = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
TASK14_THAW = "THAW-RUNLESS-TASK14-MANUAL-FALLBACK"
V43_PATH = "cfb_game_total_clean_page_v43.py"
V43_FROM = "ebb7bfa20489598a62891ec4e5e868fe350c8712"
V43_TO = "3a05f8f3f9d434a462da702d429e7db990c9b528"
EXPECTED_REMAINING_THAWS = {
    "THAW-CFB-GT-PAGE2-STEP7-REPAIR-R1",
    "THAW-CFB-GT-PAGE2-STEP7-REVIEW-RED-R1",
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
}
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-A19E4C7B8D2F60513C9A77E4"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-registry-repair"

STALE_BASELINE_UPDATES = {
    ".github/workflows/api2-control-plane-efficiency-v1-step1-workflow-fanout-governor.yml": {"from_blob": "0ab2d1d0a4c0f527bac4e3b32899b838914a4a08", "to_blob": "030c70853cdc38af709435e70465e94d1b18c7e3"},
    ".github/workflows/api2-proof-architecture-v1-step2-required-integration-lanes.yml": {"from_blob": "be8d0b985f9c2e96fbf89abf2b07c2a1e1433595", "to_blob": "dd45ac094207379e6f195e8215582209937155e7"},
    ".github/workflows/api2-proof-architecture-v1-step3-dependency-auto-refresh.yml": {"from_blob": "afe4388538dfd4e3cfb7cea48faa5308f9ee956d", "to_blob": "98349881f7b48f3400f0e885a87d861bb5b1147b"},
    ".github/workflows/api2-proof-architecture-v1-step5-failure-domain-separation.yml": {"from_blob": "fa12ddbb637f92afb6e75f7526021607c446c8f1", "to_blob": "d8ef13953b5fec632d8ab38dca6fdc9220f0f45e"},
    ".github/workflows/api2-proof-architecture-v1-step6-frozen-registry-lifecycle.yml": {"from_blob": "657d4095083891b528c3dbd7ffa67bb50408f224", "to_blob": "e160da4b261c4ebf60e4686c906023a3ce1aa685"},
    ".github/workflows/api2-proof-architecture-v1-step7-end-to-end-convergence.yml": {"from_blob": "1daa66a7e9421916c06a9e9338305784102462b7", "to_blob": "832e66008f601690cb6e094f3c762ce372a88b63"},
    ".github/workflows/registry-race-v1-step3-wait-one-resume.yml": {"from_blob": "68a23e37a5d4f4e2766d4ef73bbb209b2b4ac650", "to_blob": "e6853ff19a3b7f643eba6e597296be8b94972eb2"},
    ".github/workflows/wnba-nav-step6-fast-cert.yml": {"from_blob": "ae0dffbae828a97ca7409a808475892902eb5857", "to_blob": "5194e53b25e542d0ab5b7b222e2195495b55351e"},
    ".github/workflows/wnba-nav-step6-responsive-cert.yml": {"from_blob": "50cede7754cc19ea60d305a49986be66d645be6a", "to_blob": "aa5ac4170966ca75f8d576e43fcced4c85b59abc"},
    ".github/workflows/wnba-pra-speed-v3-step7-precompute.yml": {"from_blob": "56ff291abf9d92a18e2978ae4213381efbcd78fb", "to_blob": "ac04cf236450dddddec05930e655214afd65f567"},
    ".github/workflows/wnba-pra-speed-v3-step8-visible-first.yml": {"from_blob": "9166a39d5d4638d71938049eedb8470d440a4701", "to_blob": "1b8647e8ecfdf87516d7cbdd9057cb84d5684415"},
    ".github/workflows/devsystem-targeted-ci.yml": {"from_blob": "eaf314176069a90ab4de25a9f73933b708951768", "to_blob": "25dd53cf1722f2f44319335e2f909b08c440ee69"},
    ".github/workflows/wnba-pra-repair-v1-step3-data-completeness.yml": {"from_blob": "bd73f14edb2ce84db7c8e3a8a70774bf50e37ef7", "to_blob": "153a63b725abbb3bd68af5c47cb06a9d7ec7af3d"},
    "devsystem/runless_legacy_proof_workflows_v1.txt": {"from_blob": "bab729f2f843d39b63060428751eb60d27c09fa8", "to_blob": "023bc6af036a1ef757fa2c669be8d664829ec535"},
    "devsystem/workflow_fanout_governor_v1.py": {"from_blob": "6b1562c2118e1e6b3fbd679659ef4cb0440e6f2e", "to_blob": "c8019b2ddf5b1d80221d7bced592c76a07d6ec4a"},
    "devsystem/workflow_fanout_policy_v1.json": {"from_blob": "5fb31429a40ae1bdd8e54a9e80102978df0da13f", "to_blob": "97a4c20794032448985ab94650917f9d6017c0af"},
    "tests/test_devsystem_workflow_fanout_governor_v1.py": {"from_blob": "1989b7a12396059ed2140de7fe1b1a88f286112e", "to_blob": "cb154996775a10a303695b0cad9d8899f13ca3c3"},
}

class Step8RegistryReconcileFailure(RuntimeError):
    pass

def _decode(raw):
    if not raw or raw.get("encoding") != "base64": raise Step8RegistryReconcileFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())
def _json_text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
def _authorize(client, registry):
    state = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_REF)))
    holders = [h for h in state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER]
    if len(holders) != 1: raise Step8RegistryReconcileFailure("RECONCILE_LEASE_NOT_UNIQUE")
    holder = holders[0]
    now = datetime.now(timezone.utc)
    expiry = datetime.fromisoformat(str(holder["expires_at_utc"]).replace("Z", "+00:00"))
    if now >= expiry: raise Step8RegistryReconcileFailure("RECONCILE_LEASE_EXPIRED")
    identity = verify_scope_identity(holder["scope"], observed_resource_identity={"main_sha": MAIN_SHA, "registry_state_hash": str(registry["state_hash"])})
    if identity.get("allowed") is not True: raise Step8RegistryReconcileFailure("RECONCILE_RESOURCE_IDENTITY_DRIFT")
    gate = authorize_scope(state, owner_id=LEASE_OWNER, lease_id=LEASE_ID, now_utc=now.isoformat().replace("+00:00", "Z"), action_scope={"write_paths":[REGISTRY_PATH],"dependency_tokens":["cfb:game-total:step8","registry:cfb-game-total:step8","runless:task14:manual-fallback","runless:task15:fanout-quarantine"],"shared_resources":["ref:monster-frozen-artifact-registry"],"resource_identity":{},"exclusive":False})
    if gate.get("allowed") is not True: raise Step8RegistryReconcileFailure("RECONCILE_ACTION_SCOPE_NOT_AUTHORIZED")

def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA: raise Step8RegistryReconcileFailure("MAIN_DRIFT")
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry(); validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION: raise Step8RegistryReconcileFailure("REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH: raise Step8RegistryReconcileFailure("REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != REGISTRY_SOURCE_MAIN: raise Step8RegistryReconcileFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    _authorize(client, registry)
    source_tree = client.tree_blobs(REGISTRY_SOURCE_MAIN); current_tree = client.tree_blobs(MAIN_SHA)
    for path, pair in STALE_BASELINE_UPDATES.items():
        expected = str(pair["to_blob"])
        if str(source_tree.get(path) or "") != expected: raise Step8RegistryReconcileFailure("STALE_BASELINE_NOT_PRESENT_IN_SOURCE_MAIN:" + path)
        if str(current_tree.get(path) or "") != expected: raise Step8RegistryReconcileFailure("STALE_BASELINE_MOVED_AFTER_SOURCE_MAIN:" + path)
    before_thaws = {str(row.get("thaw_id") or "") for row in registry.get("active_thaws", [])}
    if before_thaws != EXPECTED_REMAINING_THAWS | {STEP8_THAW, TASK14_THAW}: raise Step8RegistryReconcileFailure("ACTIVE_THAW_SET_DRIFT")
    baseline_plan = plan_baseline_forward_port(registry, updates=STALE_BASELINE_UPDATES, source_main_sha=REGISTRY_SOURCE_MAIN)
    baseline_registry = baseline_plan["registry"]
    if int(baseline_registry["revision"]) != EXPECTED_REVISION + 1: raise Step8RegistryReconcileFailure("BASELINE_REPAIR_REVISION_DRIFT")
    if set(baseline_plan.get("retired_empty_thaw_grants") or []) != {TASK14_THAW}: raise Step8RegistryReconcileFailure("BASELINE_REPAIR_THAW_RETIREMENT_DRIFT")
    baseline_thaws = {str(row.get("thaw_id") or "") for row in baseline_registry.get("active_thaws", [])}
    if baseline_thaws != EXPECTED_REMAINING_THAWS | {STEP8_THAW}: raise Step8RegistryReconcileFailure("BASELINE_REPAIR_UNRELATED_THAW_DRIFT")
    if str(current_tree.get(V43_PATH) or "") != V43_TO: raise Step8RegistryReconcileFailure("STEP8_V43_MAIN_BLOB_DRIFT")
    step8_plan = plan_baseline_forward_port(baseline_registry, updates={V43_PATH:{"from_blob":V43_FROM,"to_blob":V43_TO}}, source_main_sha=MAIN_SHA)
    final_registry = step8_plan["registry"]
    if int(final_registry["revision"]) != EXPECTED_REVISION + 2: raise Step8RegistryReconcileFailure("STEP8_FORWARD_PORT_REVISION_DRIFT")
    if str(final_registry["source_main_sha"]) != MAIN_SHA: raise Step8RegistryReconcileFailure("STEP8_FORWARD_PORT_SOURCE_MAIN_DRIFT")
    if set(step8_plan.get("retired_empty_thaw_grants") or []) != {STEP8_THAW}: raise Step8RegistryReconcileFailure("STEP8_THAW_RETIREMENT_DRIFT")
    remaining = {str(row.get("thaw_id") or "") for row in final_registry.get("active_thaws", [])}
    if remaining != EXPECTED_REMAINING_THAWS: raise Step8RegistryReconcileFailure("FINAL_UNRELATED_THAW_PRESERVATION_FAILED")
    validate_registry(final_registry)
    client.update_content(REGISTRY_PATH, _json_text(final_registry), backend.branch, "registry: self-heal stale Runless baseline and forward-port merged CFB Step 8", backend._blob_sha)
    readback = backend.read_registry(); validate_registry(readback)
    if readback != final_registry: raise Step8RegistryReconcileFailure("REGISTRY_READBACK_MISMATCH")
    return {"status":"GREEN","decision":"CFB_STEP8_REGISTRY_RECONCILED","previous_revision":EXPECTED_REVISION,"baseline_repair_revision":EXPECTED_REVISION+1,"revision":int(readback["revision"]),"previous_state_hash":EXPECTED_HASH,"state_hash":str(readback["state_hash"]),"source_main_sha":str(readback["source_main_sha"]),"stale_baseline_path_count":len(STALE_BASELINE_UPDATES),"baseline_updated_entry_count":len(baseline_plan.get("updated_entries") or []),"step8_updated_entry_count":len(step8_plan.get("updated_entries") or []),"retired_thaws":sorted([TASK14_THAW,STEP8_THAW]),"remaining_thaws":sorted(EXPECTED_REMAINING_THAWS),"single_registry_write":True,"product_runtime_mutation":False,"retry_after_state_change_only":True}

def install_startup(app):
    app.state.cfb_step8_registry_reconcile = {"status":"NOT_RUN"}
    @app.on_event("startup")
    def _run():
        try: app.state.cfb_step8_registry_reconcile = execute(app)
        except Exception as exc: app.state.cfb_step8_registry_reconcile = {"status":"FAIL","error":type(exc).__name__,"detail":str(exc)[:12000]}
        print("CFB_STEP8_REGISTRY_RECONCILE=" + json.dumps(app.state.cfb_step8_registry_reconcile, sort_keys=True, default=str), flush=True)
    return app
