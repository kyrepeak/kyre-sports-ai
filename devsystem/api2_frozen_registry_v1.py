"""API2-owned immutable-success registry."""
from __future__ import annotations
import hashlib, json, re
from copy import deepcopy
from typing import Any, Mapping
VERSION="API2_FROZEN_REGISTRY_V1"; BASE_REF="refs/heads/api2-main"; _SHA40=re.compile(r"^[0-9a-f]{40}$"); _HASH64=re.compile(r"^[0-9a-f]{64}$")
class FreezeError(RuntimeError): pass
def _hash(value: Mapping[str, Any]) -> str:
    raw=deepcopy(dict(value)); raw.pop("state_hash",None); return hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def new_registry() -> dict[str, Any]:
    out={"version":VERSION,"system":"api2","base_ref":BASE_REF,"revision":0,"entries":{}}; out["state_hash"]=_hash(out); return out
def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    out=deepcopy(dict(registry))
    if out.get("version")!=VERSION or out.get("system")!="api2" or out.get("base_ref")!=BASE_REF: raise FreezeError("API2_FREEZE_REGISTRY_IDENTITY_INVALID")
    if out.get("state_hash")!=_hash(out): raise FreezeError("API2_FREEZE_REGISTRY_HASH_MISMATCH")
    return out
def freeze_checkpoint(registry: Mapping[str, Any], *, checkpoint_id: str, candidate_sha: str, merged_sha: str, evidence_digest: str, artifacts: Mapping[str,str]) -> dict[str, Any]:
    out=validate_registry(registry)
    if checkpoint_id in out["entries"]: raise FreezeError("API2_FREEZE_CHECKPOINT_EXISTS")
    if not checkpoint_id.startswith("API2_") or not _SHA40.fullmatch(candidate_sha) or not _SHA40.fullmatch(merged_sha) or not _HASH64.fullmatch(evidence_digest): raise FreezeError("API2_FREEZE_EVIDENCE_INVALID")
    if not artifacts or any(not _SHA40.fullmatch(str(v)) for v in artifacts.values()): raise FreezeError("API2_FREEZE_ARTIFACTS_INVALID")
    out["revision"]+=1; out["entries"][checkpoint_id]={"checkpoint_id":checkpoint_id,"status":"FROZEN","candidate_sha":candidate_sha,"merged_sha":merged_sha,"evidence_digest":evidence_digest,"artifacts":dict(sorted(artifacts.items()))}; out["state_hash"]=_hash(out); return out
def verify_checkpoint(registry: Mapping[str, Any], checkpoint_id: str) -> dict[str, Any]:
    out=validate_registry(registry); entry=out["entries"].get(checkpoint_id)
    if not entry or entry.get("status")!="FROZEN": raise FreezeError("API2_CHECKPOINT_NOT_FROZEN")
    return deepcopy(entry)
