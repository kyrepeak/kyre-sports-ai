"""Permanent API2 execution controller."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping, Sequence
import devsystem.api2_anti_loop_v1 as anti
from devsystem.api2_step2a_authority_v1 import begin_problem, authorize_repair as step2a_authorize, consume_authorization
from devsystem.api2_step2b_reliability_gate_v1 import validate_repair
VERSION="API2_EXECUTION_CONTROLLER_V2"
class ControllerError(RuntimeError): pass
def new_state(*, problem_id: str, branch: str, proof_path: str, acceptance_criteria: Sequence[str] | None=None) -> dict[str, Any]:
    authority=begin_problem({},problem_id=problem_id,branch=branch,proof_path=proof_path)
    return {"system":"api2","authority":authority,"problem_id":problem_id,"branch":branch,"proof_path":proof_path,"acceptance_criteria":list(acceptance_criteria or []),"phase":"READY","anti_loop":{},"step2c":None,"step2b":None,"authorization":None,"verification_status":"NOT_STARTED","green":False,"frozen":False,"blocker":None}
def record_failure(state: Mapping[str, Any], *, action: Mapping[str, Any], evidence: Sequence[Any], hypothesis: str) -> dict[str, Any]:
    out=deepcopy(dict(state)); out["anti_loop"]=anti.record_failure(out.get("anti_loop") or {},action=action,evidence=evidence,hypothesis=hypothesis); out["failed_action"]=dict(action); out["failure_evidence"]=list(evidence); out["failure_hypothesis"]=hypothesis; out["phase"]="STEP_2C"; out["step2c_status"]="REQUIRED"; out["step2b_status"]="WAITING"; out["step2a_status"]="BLOCKED"; return out
def submit_step2c(state: Mapping[str, Any], investigation: Mapping[str, Any]) -> dict[str, Any]:
    if state.get("phase")!="STEP_2C": raise ControllerError("API2_STEP2C_OUT_OF_ORDER")
    out=deepcopy(dict(state)); out["step2c"]=dict(investigation)
    if investigation.get("human_only_blocker") is True: out["phase"]="HUMAN_ONLY_BLOCKER"; out["blocker"]=dict(investigation); out["step2c_status"]="HUMAN_ONLY_BLOCKER"; return out
    if investigation.get("next_phase")!="STEP_2B" or not investigation.get("root_cause") or not investigation.get("evidence_digest"): raise ControllerError("API2_STEP2C_EVIDENCE_INCOMPLETE")
    out["phase"]="STEP_2B"; out["step2c_status"]="GREEN"; out["step2b_status"]="REQUIRED"; return out
def submit_step2b(state: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    if state.get("phase")!="STEP_2B": raise ControllerError("API2_STEP2B_OUT_OF_ORDER")
    out=deepcopy(dict(state)); decision=validate_repair(payload); out["step2b"]=decision
    if decision.get("allowed") is not True: out["phase"]="STEP_2C"; out["step2b_status"]="BLOCKED"; out["step2c_status"]="REQUIRED_DEEPER_INVESTIGATION"; out["step2a_status"]="BLOCKED"; return out
    inv=state.get("step2c") or {}; anti_decision=anti.authorize_retry(state.get("anti_loop") or {},action=state.get("failed_action") or {},evidence=[inv.get("evidence_digest")],hypothesis=str(inv.get("hypothesis") or inv.get("root_cause") or "")); out["anti_loop_decision"]=anti_decision
    if anti_decision.get("allowed") is not True: out["phase"]="STEP_2C"; out["step2b_status"]="GREEN"; out["step2c_status"]="REQUIRED_DEEPER_INVESTIGATION"; out["step2a_status"]="BLOCKED"; return out
    out["phase"]="STEP_2A"; out["step2b_status"]="GREEN"; out["step2a_status"]="READY"; return out
def authorize_repair(state: Mapping[str, Any], repair: Mapping[str, Any]):
    if state.get("phase")!="STEP_2A": raise ControllerError("API2_STEP2A_OUT_OF_ORDER")
    token=step2a_authorize(state["authority"],repair=repair,reliability=state["step2b"],anti_loop=state["anti_loop_decision"]); out=deepcopy(dict(state)); out["authorization"]=token; out["phase"]="EXECUTE"; out["step2a_status"]="AUTHORIZED"; return out,token
def mark_repair_executed(state: Mapping[str, Any], authorization: Mapping[str, Any]) -> dict[str, Any]:
    if state.get("phase")!="EXECUTE" or state.get("authorization")!=dict(authorization): raise ControllerError("API2_EXECUTION_OUT_OF_ORDER")
    out=deepcopy(dict(state)); out["authority"]=consume_authorization(out["authority"],authorization); out["phase"]="VERIFY"; out["step2a_status"]="CONSUMED"; out["verification_status"]="REQUIRED"; return out
def record_verification(state: Mapping[str, Any], proofs: Mapping[str,bool]) -> dict[str, Any]:
    if state.get("phase")!="VERIFY": raise ControllerError("API2_VERIFICATION_OUT_OF_ORDER")
    criteria=list(state.get("acceptance_criteria") or [])
    if not criteria or any(proofs.get(c) is not True for c in criteria): raise ControllerError("API2_GREEN_PROOF_INCOMPLETE")
    out=deepcopy(dict(state)); out["verification_status"]="VERIFIED"; out["green"]=True; out["frozen"]=False; out["phase"]="GREEN"; out["verification_proofs"]=dict(proofs); return out
def record_freeze_readback(state: Mapping[str, Any], checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    if state.get("phase")!="GREEN" or state.get("green") is not True: raise ControllerError("API2_FREEZE_BEFORE_GREEN")
    if checkpoint.get("status")!="FROZEN" or not str(checkpoint.get("checkpoint_id") or "").startswith("API2_"): raise ControllerError("API2_FREEZE_READBACK_INVALID")
    out=deepcopy(dict(state)); out["frozen"]=True; out["phase"]="FROZEN"; out["freeze_checkpoint"]=dict(checkpoint); return out
def status_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    phase=str(state.get("phase") or "UNKNOWN"); progress={"READY":5,"STEP_2C":35,"STEP_2B":55,"STEP_2A":70,"EXECUTE":80,"VERIFY":90,"GREEN":96,"FROZEN":100,"HUMAN_ONLY_BLOCKER":0}.get(phase,10); root=(state.get("step2c") or {}).get("root_cause") or state.get("failure_hypothesis")
    return {"current_phase":phase,"progress_percent":progress,"active_problem":state.get("problem_id"),"authoritative_api2_path":{"branch":state.get("branch"),"proof_path":state.get("proof_path")},"current_root_cause_hypothesis":root,"step_2c_status":state.get("step2c_status","NOT_REQUIRED"),"step_2b_status":state.get("step2b_status","NOT_STARTED"),"step_2a_authorization_status":state.get("step2a_status","NOT_AUTHORIZED"),"anti_loop_status":"SATISFIED" if (state.get("anti_loop_decision") or {}).get("allowed") else ("ACTIVE" if state.get("anti_loop") else "IDLE"),"verification_status":state.get("verification_status"),"blocker":state.get("blocker"),"green_frozen_checkpoint":"FROZEN" if state.get("frozen") else ("GREEN" if state.get("green") else "PENDING")}
