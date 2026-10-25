"""API2 Step 2A one-problem/one-path and one-use repair authority."""
from __future__ import annotations
import hashlib, json
from copy import deepcopy
from typing import Any, Mapping
from devsystem.api2_isolation_guard_v1 import validate_api2_authority
VERSION="API2_STEP2A_AUTHORITY_V1"
class Step2AError(RuntimeError): pass
def _digest(value: Any) -> str: return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def begin_problem(state: Mapping[str, Any], *, problem_id: str, branch: str, proof_path: str) -> dict[str, Any]:
    validate_api2_authority({"system":"api2","problem_id":problem_id,"branch":branch,"proof_path":proof_path}); out=deepcopy(dict(state)); active=out.get("active_problem"); requested={"problem_id":problem_id,"branch":branch,"proof_path":proof_path}
    if active and active!=requested: raise Step2AError("API2_MULTIPLE_ACTIVE_PROBLEMS_OR_PATHS_FORBIDDEN")
    out["active_problem"]=requested; out.setdefault("consumed_authorizations",[]); return out
def authorize_repair(state: Mapping[str, Any], *, repair: Mapping[str, Any], reliability: Mapping[str, Any], anti_loop: Mapping[str, Any]) -> dict[str, Any]:
    if not state.get("active_problem"): raise Step2AError("API2_NO_ACTIVE_PROBLEM")
    if reliability.get("allowed") is not True: raise Step2AError("API2_STEP2B_NOT_GREEN")
    if anti_loop.get("allowed") is not True: raise Step2AError("API2_ANTI_LOOP_NOT_SATISFIED")
    payload={"system":"api2","path":state["active_problem"],"repair":dict(repair),"step2b":reliability.get("decision_digest"),"anti_loop":anti_loop.get("decision")}; return {**payload,"authorization_id":"API2-AUTH-"+_digest(payload)[:24],"single_use":True}
def consume_authorization(state: Mapping[str, Any], authorization: Mapping[str, Any]) -> dict[str, Any]:
    out=deepcopy(dict(state)); consumed=list(out.get("consumed_authorizations") or []); auth_id=str(authorization.get("authorization_id") or "")
    if not auth_id or auth_id in consumed: raise Step2AError("API2_AUTHORIZATION_ALREADY_USED_OR_INVALID")
    consumed.append(auth_id); out["consumed_authorizations"]=consumed; return out
