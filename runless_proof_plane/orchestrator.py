from __future__ import annotations
from .models import ProofState,ProofStatus
ORDER=[ProofState.IDENTIFY,ProofState.LOCK_2A,ProofState.FINGERPRINT,ProofState.REUSE_OR_PROVE,ProofState.PUBLIC_CHECK_IF_REQUIRED,ProofState.RECEIPT,ProofState.RUNLESS_FINAL_GATE,ProofState.MERGE_AUTHORIZED,ProofState.MERGED,ProofState.POST_MERGE_VERIFY,ProofState.FREEZE,ProofState.READ_BACK,ProofState.GREEN_FROZEN]
class ProofOrchestrator:
    def __init__(self):self._active={};self._statuses={};self._failed_fingerprints=set()
    def start(self,request,proof_id,request_fingerprint):
        if request.workstream in self._active:raise RuntimeError("RUNLESS_WORKSTREAM_BUSY")
        if request_fingerprint in self._failed_fingerprints:raise RuntimeError("RUNLESS_UNCHANGED_FAILED_REQUEST_BLOCKED")
        s=ProofStatus(proof_id=proof_id,state=ProofState.IDENTIFY,task_id=request.task_id,workstream=request.workstream,candidate_sha=request.candidate_sha);self._active[request.workstream]=proof_id;self._statuses[proof_id]=s;return s
    def advance(self,proof_id,target):
        s=self._statuses[proof_id]
        if ORDER.index(target)!=ORDER.index(s.state)+1:raise RuntimeError("RUNLESS_ILLEGAL_TRANSITION")
        s.state=target
        if target==ProofState.GREEN_FROZEN:self._active.pop(s.workstream,None)
        return s
    def fail(self,proof_id,request_fingerprint,detail=""):
        s=self._statuses[proof_id];s.state=ProofState.FAILED;s.detail=detail;self._failed_fingerprints.add(request_fingerprint);self._active.pop(s.workstream,None);return s
    def status(self,proof_id):return self._statuses[proof_id]
    def resume_from_webhook(self,event):return event
