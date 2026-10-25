"""API2 Step 2B fail-closed reliability/evidence gate."""
from __future__ import annotations
import hashlib, json, re
from typing import Any, Mapping
from devsystem.api2_isolation_guard_v1 import IsolationViolation, validate_api2_authority
VERSION = "API2_STEP2B_RELIABILITY_GATE_V1"; _HASH64 = re.compile(r"^[0-9a-f]{64}$")
def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def validate_repair(payload: Mapping[str, Any]) -> dict[str, Any]:
    failures=[]; data=dict(payload)
    try:
        validate_api2_authority({"system":data.get("system","api2")})
        path=dict(data.get("authoritative_path") or {})
        validate_api2_authority({"system":"api2","problem_id":path.get("problem_id"),"branch":path.get("branch"),"proof_path":path.get("proof_path")})
    except (IsolationViolation, TypeError) as exc: failures.append(str(exc))
    criteria=[str(x) for x in (data.get("acceptance_criteria") or []) if str(x)]
    if not criteria: failures.append("acceptance_criteria_missing")
    root=dict(data.get("root_cause") or {})
    if not root.get("finding") or not _HASH64.fullmatch(str(root.get("evidence_digest") or "")): failures.append("root_cause_evidence_invalid")
    for field in ("requirement_to_implementation","requirement_to_proof"):
        mapping=data.get(field) or {}
        if set(mapping)!=set(criteria) or any(not mapping.get(c) for c in criteria): failures.append(f"{field}_incomplete")
    if any(item.get("verified") is not True for item in (data.get("production_dependencies") or [])): failures.append("production_dependency_unverified")
    if any(item.get("relevant") is True and item.get("verified") is not True for item in (data.get("provider_reachability") or [])): failures.append("provider_reachability_unverified")
    if any(item.get("verified") is not True for item in (data.get("configuration_assumptions") or [])): failures.append("configuration_assumption_unverified")
    risks=data.get("regression_risks") or []
    if any(not item.get("risk") or not item.get("proof") for item in risks): failures.append("regression_risk_unmapped")
    if not data.get("verification"): failures.append("verification_missing")
    delta=dict(data.get("repair_delta") or {})
    if delta.get("materially_different") is not True: failures.append("repair_not_materially_different")
    if not _HASH64.fullmatch(str(delta.get("new_evidence_digest") or "")): failures.append("repair_new_evidence_invalid")
    if str(delta.get("prior_repair") or "") == str(delta.get("new_repair") or ""): failures.append("repair_delta_missing")
    allowed=not failures; decision={"allowed":allowed,"failures":sorted(set(failures)),"system":"api2"}; decision["decision_digest"]=_digest({"payload":data,"decision":decision}); decision["next_phase"]="STEP_2A" if allowed else "STEP_2C"; return decision
