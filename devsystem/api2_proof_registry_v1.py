"""API2-owned exact-candidate GREEN proof registry."""
from __future__ import annotations
import hashlib, json, re
from copy import deepcopy
from typing import Any, Mapping

VERSION="API2_PROOF_REGISTRY_V1"
BASE_REF="refs/heads/api2-main"
PROOF_REF="refs/heads/api2-proof-registry"
_SHA40=re.compile(r"^[0-9a-f]{40}$")
_HASH64=re.compile(r"^[0-9a-f]{64}$")
class ProofError(RuntimeError): pass

def _hash(value: Mapping[str, Any]) -> str:
    raw=deepcopy(dict(value)); raw.pop("state_hash",None)
    return hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

def new_registry() -> dict[str, Any]:
    out={"version":VERSION,"system":"api2","base_ref":BASE_REF,"proof_ref":PROOF_REF,"revision":0,"entries":{}}
    out["state_hash"]=_hash(out); return out

def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    out=deepcopy(dict(registry))
    if out.get("version")!=VERSION or out.get("system")!="api2" or out.get("base_ref")!=BASE_REF or out.get("proof_ref")!=PROOF_REF:
        raise ProofError("API2_PROOF_REGISTRY_IDENTITY_INVALID")
    if out.get("state_hash")!=_hash(out): raise ProofError("API2_PROOF_REGISTRY_HASH_MISMATCH")
    return out

def record_green_proof(registry: Mapping[str, Any], *, proof_id: str, candidate_sha: str, base_sha: str, evidence_digest: str, artifacts: Mapping[str,str], acceptance_proofs: Mapping[str,bool], certification: Mapping[str,Any]) -> dict[str, Any]:
    out=validate_registry(registry)
    if not str(proof_id).startswith("api2-") or proof_id in out["entries"]: raise ProofError("API2_PROOF_ID_INVALID_OR_EXISTS")
    if not _SHA40.fullmatch(candidate_sha) or not _SHA40.fullmatch(base_sha) or not _HASH64.fullmatch(evidence_digest): raise ProofError("API2_PROOF_EVIDENCE_INVALID")
    if not artifacts or any(not _SHA40.fullmatch(str(v)) for v in artifacts.values()): raise ProofError("API2_PROOF_ARTIFACTS_INVALID")
    if not acceptance_proofs or any(v is not True for v in acceptance_proofs.values()): raise ProofError("API2_PROOF_ACCEPTANCE_INCOMPLETE")
    if certification.get("status")!="GREEN": raise ProofError("API2_PROOF_CERTIFICATION_NOT_GREEN")
    entry={"proof_id":proof_id,"state":"GREEN","candidate_sha":candidate_sha,"base_sha":base_sha,"evidence_digest":evidence_digest,"artifacts":dict(sorted(artifacts.items())),"acceptance_proofs":dict(sorted(acceptance_proofs.items())),"certification":deepcopy(dict(certification)),"foreign_authority_used":False}
    entry["proof_hash"]=_hash(entry)
    out["revision"]+=1; out["entries"][proof_id]=entry; out["state_hash"]=_hash(out); return out

def verify_proof(registry: Mapping[str, Any], proof_id: str) -> dict[str, Any]:
    out=validate_registry(registry); entry=deepcopy((out.get("entries") or {}).get(proof_id))
    if not entry or entry.get("state")!="GREEN" or entry.get("foreign_authority_used") is not False: raise ProofError("API2_PROOF_NOT_GREEN")
    observed=entry.pop("proof_hash",None)
    if observed!=_hash(entry): raise ProofError("API2_PROOF_HASH_MISMATCH")
    entry["proof_hash"]=observed; return entry
