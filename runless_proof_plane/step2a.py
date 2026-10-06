from __future__ import annotations
from dataclasses import dataclass
from .models import ProofRequest
@dataclass(frozen=True)
class Step2ASnapshot: candidate_sha:str; main_sha:str; registry_revision:int; registry_hash:str; active_thaws:tuple[str,...]; scope_lease:str; rollback_anchor:str; workstream:str
@dataclass(frozen=True)
class Step2AAuthorization: authorization_id:str; candidate_sha:str; workstream:str; lease_id:str
class Step2AError(RuntimeError):pass
def build_snapshot(request:ProofRequest,state_reader):
    s=state_reader(request);return Step2ASnapshot(s["candidate_sha"],s["main_sha"],int(s["registry_revision"]),s["registry_hash"],tuple(s.get("active_thaws",())),s["scope_lease"],s["rollback_anchor"],s["workstream"])
def authorize_proof(snapshot,request):
    if snapshot.candidate_sha!=request.candidate_sha:raise Step2AError("RUNLESS_EXACT_HEAD_DRIFT")
    if snapshot.workstream!=request.workstream:raise Step2AError("RUNLESS_CROSS_WORKSTREAM_REJECTED")
    if snapshot.scope_lease!=request.lease_id:raise Step2AError("RUNLESS_SCOPE_LEASE_MISMATCH")
    if request.expected_main_sha and snapshot.main_sha!=request.expected_main_sha:raise Step2AError("RUNLESS_MAIN_IDENTITY_DRIFT")
    return Step2AAuthorization(request.authorization_id,request.candidate_sha,request.workstream,request.lease_id)
