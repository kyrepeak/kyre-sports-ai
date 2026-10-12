from __future__ import annotations

import base64
import json
import os
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state
from .registry import GithubRegistryBackend, REGISTRY_PATH

ENV = "RPP_NBA_SPREAD_STEP2_AUTHORITY_PREP_ON_START"
TASK_ID = "nba-spread-step2-site-activation-v1"
BRANCH = "nba-spread-step2-site-activation-r1"
CANDIDATE_SHA = "6804bfe0dff50d37cc8a097eff34a1f6a75526c1"
PRIOR_CANDIDATE_SHA = "21c31d5971c74ce1ff0ca0a22c2adffc6467d1c7"
SOURCE_MAIN_SHA = "9a7afa1fe19d62eed444088a8e77ca6c45e0bfb1"
PR = "1521"
THAW_ID = "THAW-NBA-SPREAD-STEP2-SITE-ACTIVATION-R1"
OWNER_ID = "chatgpt:api2:nba-spread-step2-site-activation-v1"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
THAW_FILES = {
    "app.py": {"from_blob": "426a53efd90b6e15149f78d1cb61acfb1e1195c3", "to_blob": "a8802aa8e32b430e5c33378ab1105ca877b934c1"},
    "tests/test_devsystem_change_classifier_v1.py": {"from_blob": "265129d2ce89da49426b36059294fcba381cfb7b", "to_blob": "6b064453b2d79ab933ce58f9d2a504e34f6fbd21"},
}
WRITE_PATHS = (
    "app.py",
    "devsystem/devsystem_manifest_v1.json",
    "devsystem/execution_plans/nba-spread-step2-site-activation-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step2-site-activation-v1.json",
    "devsystem/task_ledgers/nba-spread-step2-site-activation-v1.json",
    "nba_spread_page_v1.py",
    "nba_spread_step2_activation_v1.py",
    "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py",
    "tests/test_devsystem_change_classifier_v1.py",
    "tests/test_nba_spread_step2_site_activation_v1.py",
)

class AuthorityPrepFailure(RuntimeError):
    pass

def _decode(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise AuthorityPrepFailure(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())

def _rebind_thaw(client):
    if client.branch_sha("main") != SOURCE_MAIN_SHA: raise AuthorityPrepFailure("NBA_STEP2_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA: raise AuthorityPrepFailure("NBA_STEP2_CANDIDATE_DRIFT")
    backend = GithubRegistryBackend(client)
    current = backend.read_registry(); validated = validate_registry(current)
    if str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA: raise AuthorityPrepFailure("NBA_STEP2_REGISTRY_MAIN_DRIFT")
    main_tree = client.tree_blobs(SOURCE_MAIN_SHA); candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    for path,pair in THAW_FILES.items():
        if str(validated["artifacts"].get(path) or "") != pair["from_blob"]: raise AuthorityPrepFailure("NBA_STEP2_FROZEN_BASELINE_DRIFT:"+path)
        if str(main_tree.get(path) or "") != pair["from_blob"]: raise AuthorityPrepFailure("NBA_STEP2_MAIN_BLOB_DRIFT:"+path)
        if str(candidate_tree.get(path) or "") != pair["to_blob"]: raise AuthorityPrepFailure("NBA_STEP2_CANDIDATE_BLOB_DRIFT:"+path)
    exact = {"thaw_id":THAW_ID,"status":"ACTIVE","target_head_sha":CANDIDATE_SHA,"files":deepcopy(THAW_FILES)}
    indexes=[i for i,x in enumerate(current.get("active_thaws",[])) if x.get("thaw_id")==THAW_ID]
    if len(indexes)!=1: raise AuthorityPrepFailure("NBA_STEP2_THAW_IDENTITY_DRIFT")
    existing=current["active_thaws"][indexes[0]]
    if existing==exact: return current
    if str(existing.get("target_head_sha") or "") != PRIOR_CANDIDATE_SHA or existing.get("files") != THAW_FILES:
        raise AuthorityPrepFailure("NBA_STEP2_PRIOR_THAW_DRIFT")
    updated=deepcopy(current); updated["active_thaws"][indexes[0]]=exact; updated["revision"]=int(current["revision"])+1
    updated.pop("state_hash",None); updated["state_hash"]=registry_hash(_payload_without_hash(updated)); validate_registry(updated)
    client.update_content(REGISTRY_PATH,json.dumps(updated,indent=2,sort_keys=True,ensure_ascii=True)+"\n",backend.branch,"registry: rebind NBA Spread Step2 thaw to generation 3",backend._blob_sha)
    rb=backend.read_registry(); validate_registry(rb)
    if [x for x in rb.get("active_thaws",[]) if x.get("thaw_id")==THAW_ID] != [exact]: raise AuthorityPrepFailure("NBA_STEP2_THAW_READBACK_MISMATCH")
    return rb

def _rebind_lease(client, registry):
    raw=client.content(LEASE_PATH,ref=LEASE_REF); state=validate_state(_decode(raw,"NBA_STEP2_SCOPE_LEASE")); working=state
    stale=[str(h["lease_id"]) for h in working.get("holders",[]) if h.get("owner_id")==OWNER_ID and str((h.get("scope") or {}).get("resource_identity",{}).get("candidate_sha") or "") != CANDIDATE_SHA]
    for lease_id in stale:
        result=release_scope(working,owner_id=OWNER_ID,lease_id=lease_id,expected_revision=int(working["revision"]),expected_state_hash=str(working["state_hash"]))
        if result["result"].get("allowed") is not True: raise AuthorityPrepFailure("NBA_STEP2_STALE_LEASE_RELEASE_FAILED")
        working=result["state"]
    now=datetime.now(timezone.utc)
    scope=build_scope(write_paths=WRITE_PATHS,dependency_tokens=("workstream:nba-spread-two-page-v1",),shared_resources=("entrypoint:app.py",),resource_identity={"candidate_sha":CANDIDATE_SHA,"pr":PR,"source_main_sha":SOURCE_MAIN_SHA,"registry_state_hash":str(registry["state_hash"])})
    claimed=claim_scope(working,owner_id=OWNER_ID,now_utc=now.isoformat().replace("+00:00","Z"),scope=scope,expected_revision=int(working["revision"]),expected_state_hash=str(working["state_hash"]),ttl_seconds=900,frozen_paths=tuple(validate_registry(registry)["artifacts"].keys()),thawed_paths=tuple(THAW_FILES.keys()))
    if claimed["result"].get("allowed") is not True: raise AuthorityPrepFailure("NBA_STEP2_SCOPE_LEASE_BLOCKED:"+str(claimed["result"].get("decision")))
    client.update_content(LEASE_PATH,json.dumps(claimed["state"],indent=2,sort_keys=True,ensure_ascii=True)+"\n",LEASE_REF,"lease: bind NBA Spread Step2 generation 3 exact scope",str(raw.get("sha") or ""))
    rb=validate_state(_decode(client.content(LEASE_PATH,ref=LEASE_REF),"NBA_STEP2_SCOPE_LEASE_READBACK")); lease_id=str(claimed["result"]["lease_id"])
    if len([h for h in rb.get("holders",[]) if h.get("lease_id")==lease_id])!=1: raise AuthorityPrepFailure("NBA_STEP2_SCOPE_LEASE_READBACK_MISMATCH")
    return {"lease_id":lease_id,"lease_revision":int(rb["revision"]),"lease_state_hash":str(rb["state_hash"]),"released_stale_lease_ids":stale}

def execute(client):
    registry=_rebind_thaw(client); lease=_rebind_lease(client,registry)
    return {"status":"GREEN","candidate_sha":CANDIDATE_SHA,"main_sha":SOURCE_MAIN_SHA,"thaw_id":THAW_ID,"registry_revision":int(registry["revision"]),"registry_state_hash":str(registry["state_hash"]),**lease,"github_actions_fallback":0}

def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV,"").strip()!="1": return
        try: result=execute(app.state.github_client)
        except Exception as exc: result={"status":"FAIL","error":type(exc).__name__,"detail":str(exc)[:1800]}
        app.state.nba_spread_step2_authority_prep_g3=result
        print("NBA_SPREAD_STEP2_AUTHORITY_PREP_G3="+json.dumps(result,sort_keys=True),flush=True)
    return app
