from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from datetime import datetime,timezone
@dataclass(frozen=True)
class ProofFingerprint: digest:str; artifacts:dict[str,str]; dependencies:dict[str,str]; policy_hash:str; scope_hash:str; deployment_identity:str|None=None
@dataclass(frozen=True)
class ReuseDecision: reusable:bool; reason:str
def _hash(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def build_fingerprint(artifacts,dependencies,policy,scope,deployment_identity=None):
    p={"artifacts":artifacts,"dependencies":dependencies,"policy":policy,"scope":scope,"deployment_identity":deployment_identity};return ProofFingerprint(_hash(p),artifacts,dependencies,_hash(policy),_hash(scope),deployment_identity)
def evaluate_slice_reuse(old,new,*,live=False,observed_at=None,ttl_seconds=900):
    if old.artifacts!=new.artifacts:return ReuseDecision(False,"ARTIFACT_DRIFT")
    if old.dependencies!=new.dependencies:return ReuseDecision(False,"DEPENDENCY_DRIFT")
    if old.policy_hash!=new.policy_hash:return ReuseDecision(False,"POLICY_DRIFT")
    if old.scope_hash!=new.scope_hash:return ReuseDecision(False,"SCOPE_DRIFT")
    if live:
        if old.deployment_identity!=new.deployment_identity:return ReuseDecision(False,"DEPLOYMENT_IDENTITY_DRIFT")
        if not observed_at or (datetime.now(timezone.utc)-observed_at).total_seconds()>ttl_seconds:return ReuseDecision(False,"LIVE_EVIDENCE_STALE")
    return ReuseDecision(True,"UNCHANGED_CONTENT")
