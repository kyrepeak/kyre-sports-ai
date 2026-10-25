"""API2 Step 2C autonomous root-cause investigation contract."""
from __future__ import annotations
import hashlib, json
from typing import Any, Mapping, Sequence
VERSION = "API2_STEP2C_ROOT_CAUSE_V1"
HUMAN_ONLY_KINDS = {"missing_user_credentials","external_user_approval","unresolved_business_decision","irreversible_destructive_authorization"}

def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def classify_human_only_blocker(blocker: Mapping[str, Any] | None) -> bool:
    return bool(blocker and str(blocker.get("kind") or "") in HUMAN_ONLY_KINDS)
def investigation_domains(failure: Mapping[str, Any]) -> list[str]:
    cls = str(failure.get("class") or "UNKNOWN").upper()
    return {
        "PARSER": ["tests","parser","configuration","runtime"],
        "PROVIDER": ["provider","dependency","configuration","runtime"],
        "DEPLOYMENT": ["deployment","runtime","configuration","dependency"],
        "RUNTIME": ["runtime","tests","configuration","dependency"],
    }.get(cls, ["tests","runtime","configuration","dependency"])

def investigate(*, failure: Mapping[str, Any], probes: Sequence[Mapping[str, Any]], blocker: Mapping[str, Any] | None = None) -> dict[str, Any]:
    human = classify_human_only_blocker(blocker or failure); required = investigation_domains(failure)
    supported = [dict(p) for p in probes if p.get("supported") is True and p.get("finding") and p.get("evidence")]
    observed = {str(p.get("domain") or "") for p in supported}; missing = [d for d in required if d not in observed]
    if human:
        return {"status":"BLOCKED","human_only_blocker":True,"next_phase":"HUMAN_ONLY_BLOCKER","required_domains":required,"missing_domains":missing}
    if not supported or missing:
        return {"status":"INVESTIGATE_MORE","human_only_blocker":False,"next_phase":"STEP_2C","required_domains":required,"missing_domains":missing,"investigated_domains":sorted(observed)}
    deepest = max(supported, key=lambda p: (int(p.get("depth") or 0), str(p.get("domain") or "")))
    bundle = [{"domain":p.get("domain"),"finding":p.get("finding"),"evidence":p.get("evidence"),"depth":int(p.get("depth") or 0)} for p in supported]
    return {"status":"ROOT_CAUSE_IDENTIFIED","root_cause":str(deepest["finding"]),"hypothesis":str(deepest["finding"]),"evidence_digest":_digest(bundle),"evidence":bundle,"investigated_domains":sorted(observed),"required_domains":required,"missing_domains":[],"human_only_blocker":False,"next_phase":"STEP_2B"}
