"""API2-native deterministic execution-plan compiler compatibility entrypoint."""
from __future__ import annotations
import hashlib, json, re
from copy import deepcopy
from typing import Any, Mapping, Sequence
VERSION="API2_EXECUTION_PLAN_COMPILER_CERT_V2"; BASE_REF="refs/heads/api2-main"; _SHA40=re.compile(r"^[0-9a-f]{40}$")
class Api2ExecutionPlanFailure(RuntimeError): pass
def _hash(value: Any) -> str: return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def _checkpoints():
    return [
        {"checkpoint_id":"01_TRUTH","depends_on":[],"action_type":"READ_ONLY"},
        {"checkpoint_id":"02_STEP2B_PREFLIGHT","depends_on":["01_TRUTH"],"action_type":"READ_ONLY"},
        {"checkpoint_id":"03_STEP2A_AUTHORIZATION","depends_on":["02_STEP2B_PREFLIGHT"],"action_type":"READ_ONLY"},
        {"checkpoint_id":"04_EXECUTE","depends_on":["03_STEP2A_AUTHORIZATION"],"action_type":"MUTATION"},
        {"checkpoint_id":"05_VERIFY","depends_on":["04_EXECUTE"],"action_type":"READ_ONLY"},
        {"checkpoint_id":"06_FREEZE","depends_on":["05_VERIFY"],"action_type":"FINALIZE"},
    ]
def compile_api2_execution_plan(main_sha: str) -> dict[str, Any]:
    if not _SHA40.fullmatch(main_sha): raise Api2ExecutionPlanFailure("API2_BASE_SHA_INVALID")
    plan={"version":"API2_EXECUTION_PLAN_V2","system":"api2","authoritative_base_ref":BASE_REF,"expected_base_sha":main_sha,"checkpoints":_checkpoints(),"topological_order":[c["checkpoint_id"] for c in _checkpoints()],"failure_recovery_chain":["ANTI_LOOP","STEP_2C","STEP_2B","STEP_2A","EXECUTE","VERIFY","GREEN","FROZEN"],"mutation_requires_one_use_step2a":True,"green_requires_acceptance_proof":True,"frozen_requires_api2_registry_readback":True}
    plan["plan_id"]="API2-PLAN-"+_hash(plan)[:16]; plan["plan_digest"]="sha256:"+_hash(plan); return plan
def validate_execution_plan(plan: Mapping[str,Any], *, observed_base_sha: str) -> dict[str,Any]:
    data=deepcopy(dict(plan)); digest=data.pop("plan_digest",None); plan_id=data.pop("plan_id",None)
    expected_id="API2-PLAN-"+_hash(data)[:16]; expected_digest="sha256:"+_hash({**data,"plan_id":expected_id})
    if plan_id!=expected_id or digest!=expected_digest: raise Api2ExecutionPlanFailure("API2_PLAN_DIGEST_MISMATCH")
    if plan.get("system")!="api2" or plan.get("authoritative_base_ref")!=BASE_REF: raise Api2ExecutionPlanFailure("API2_PLAN_IDENTITY_DRIFT")
    if observed_base_sha!=plan.get("expected_base_sha"): raise Api2ExecutionPlanFailure("API2_STALE_COMPILED_PLAN")
    return deepcopy(dict(plan))
def next_checkpoint(plan: Mapping[str,Any], *, observed_base_sha: str, completed_checkpoint_ids: Sequence[str]) -> dict[str,Any]:
    validate_execution_plan(plan,observed_base_sha=observed_base_sha)
    completed_list=list(completed_checkpoint_ids)
    expected_prefix=list(plan["topological_order"][:len(completed_list)])
    if completed_list != expected_prefix:
        raise Api2ExecutionPlanFailure("API2_CHECKPOINT_HISTORY_NOT_MONOTONIC")
    completed=set(completed_list); cps=plan["checkpoints"]
    for cp in cps:
        cid=cp["checkpoint_id"]
        if cid in completed: continue
        missing=[d for d in cp["depends_on"] if d not in completed]
        if missing: raise Api2ExecutionPlanFailure("API2_CHECKPOINT_MISSING_DEPENDENCIES:"+",".join(missing))
        action="CONSUME_STEP_2A_AUTHORIZATION:04_EXECUTE" if cid=="04_EXECUTE" else "EXECUTE_CHECKPOINT:"+cid
        return {"decision":"CHECKPOINT_SELECTED","selected_checkpoint_id":cid,"next_legal_action":action,"mutation_authority":False,"step_2a_required":cid=="04_EXECUTE"}
    return {"decision":"PLAN_COMPLETE","complete":True,"next_legal_action":"VERIFY_API2_FREEZE_CONTRACT","mutation_authority":False}
def run_certification() -> dict[str,Any]:
    head="a"*40; a=compile_api2_execution_plan(head); b=compile_api2_execution_plan(head); deterministic=a==b
    validate_execution_plan(a,observed_base_sha=head)
    stale=tamper=deps=False
    try: validate_execution_plan(a,observed_base_sha="b"*40)
    except Api2ExecutionPlanFailure: stale=True
    t=deepcopy(a); t["checkpoints"][3]["action_type"]="READ_ONLY"
    try: validate_execution_plan(t,observed_base_sha=head)
    except Api2ExecutionPlanFailure: tamper=True
    try: next_checkpoint(a,observed_base_sha=head,completed_checkpoint_ids=["01_TRUTH","03_STEP2A_AUTHORIZATION"])
    except Api2ExecutionPlanFailure: deps=True
    mutation=next_checkpoint(a,observed_base_sha=head,completed_checkpoint_ids=["01_TRUTH","02_STEP2B_PREFLIGHT","03_STEP2A_AUTHORIZATION"])
    complete=next_checkpoint(a,observed_base_sha=head,completed_checkpoint_ids=a["topological_order"])
    result={"status":"GREEN","version":VERSION,"checkpoint_count":len(a["checkpoints"]),"topological_order":a["topological_order"],"deterministic_plan":deterministic,"stale_plan_blocked":stale,"tampered_plan_blocked":tamper,"dependency_bypass_blocked":deps,"mutation_checkpoint":mutation["selected_checkpoint_id"],"mutation_reenters_step2a":mutation["step_2a_required"],"mutation_authority_granted":mutation["mutation_authority"],"freeze_contract_complete":complete["next_legal_action"]=="VERIFY_API2_FREEZE_CONTRACT","network_calls":False,"auto_mutate":False,"product_runtime_mutation":False}
    if not all(result[k] for k in ("deterministic_plan","stale_plan_blocked","tampered_plan_blocked","dependency_bypass_blocked","mutation_reenters_step2a","freeze_contract_complete")): raise Api2ExecutionPlanFailure("API2_COMPILER_CERT_FAILED")
    return result
def self_test() -> dict[str,Any]: return run_certification()
