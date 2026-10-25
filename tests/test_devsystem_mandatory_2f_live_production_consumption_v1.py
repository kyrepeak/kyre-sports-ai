from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def _load():
    path=ROOT/"devsystem/mandatory_2f_live_production_consumption_v1.py"
    assert path.is_file(),"Step 2F production module missing"
    spec=importlib.util.spec_from_file_location("mandatory_2f_live_production_consumption_v1",path); assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module


def _green():
    sha="a"*40
    return {"task_id":"monster-step2f-test","candidate_sha":sha,"deployment_applicable":True,"deployment":{"id":"monster-prod-123","sha":sha,"environment":"production","production":True,"preview":False,"healthy":True,"stale":False,"project":"kyre-sports-ai"},"stable_alias":{"url":"https://pickvault.streamlit.app","target_deployment_id":"monster-prod-123","target_sha":sha,"healthy":True},"canonical_endpoint":{"url":"https://pickvault.streamlit.app/?sport=nfl&market=passing-yards","healthy":True,"router_owner":"nfl_passing_yards_simple_qb_grid_v1","expected_router_owner":"nfl_passing_yards_simple_qb_grid_v1","schema":"monster-route-v1","expected_schema":"monster-route-v1","consumer_verified":True},"smoke":{"required":["nfl:passing-yards"],"passed":["nfl:passing-yards"]},"rollback_anchor":{"deployment_id":"monster-prod-122","sha":"b"*40},"promotion_lanes":1}


def test_step2f_accepts_exact_candidate_live_at_stable_alias():
    mod=_load(); result=mod.validate_production_attestation(_green())
    assert result["status"]=="GREEN" and result["step2f_enforced"] is True and result["exact_head_deployed"] is True and result["stable_alias_parity"] is True and result["real_website_consumption_verified"] is True and result["final_verification_authorized"] is True


def test_step2f_blocks_sha_alias_preview_health_schema_smoke_and_lane_drift():
    mod=_load(); mutations=[]
    a=_green(); a["deployment"]["sha"]="c"*40; mutations.append(a)
    a=_green(); a["stable_alias"]["target_sha"]="c"*40; mutations.append(a)
    a=_green(); a["deployment"]["preview"]=True; mutations.append(a)
    a=_green(); a["deployment"]["stale"]=True; mutations.append(a)
    a=_green(); a["canonical_endpoint"]["healthy"]=False; mutations.append(a)
    a=_green(); a["canonical_endpoint"]["router_owner"]="wrong"; mutations.append(a)
    a=_green(); a["canonical_endpoint"]["schema"]="wrong"; mutations.append(a)
    a=_green(); a["canonical_endpoint"]["consumer_verified"]=False; mutations.append(a)
    a=_green(); a["smoke"]["passed"]=[]; mutations.append(a)
    a=_green(); a["rollback_anchor"]={}; mutations.append(a)
    a=_green(); a["promotion_lanes"]=2; mutations.append(a)
    for attestation in mutations:
        result=mod.validate_production_attestation(attestation)
        assert result["status"]=="BLOCKED" and result["next_legal_action"]=="RETURN_TO_MONSTER_STEP_2C" and result["failure_fingerprint"]


def test_step2f_allows_control_plane_n_a_only_when_explicit_and_read_only():
    mod=_load(); result=mod.validate_production_attestation({"task_id":"monster-control-only","candidate_sha":"d"*40,"deployment_applicable":False,"control_plane_only":True,"network_calls":False,"auto_mutate":False,"product_runtime_mutation":False,"rollback_anchor":{"sha":"e"*40,"kind":"verified-parent"}})
    assert result["status"]=="GREEN" and result["deployment_applicable"] is False and result["deployment_proof"]=="NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE"
    bad=mod.validate_production_attestation({"task_id":"monster-control-only","candidate_sha":"d"*40,"deployment_applicable":False,"control_plane_only":True,"network_calls":True,"auto_mutate":False,"product_runtime_mutation":False,"rollback_anchor":{"sha":"e"*40}})
    assert bad["status"]=="BLOCKED"


def test_step2f_contract_self_test_is_green():
    mod=_load(); result=mod.contract_self_test()
    assert result["status"]=="GREEN" and result["monster_only"] is True and result["blind_redeploy_allowed"] is False
