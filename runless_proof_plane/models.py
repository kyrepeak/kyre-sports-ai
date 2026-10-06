from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

class FailureClass(str, Enum):
    NONE="NONE"; PLAN="PLAN"; IDENTITY="IDENTITY"; LEASE="LEASE"; REGISTRY="REGISTRY"; STATIC_PROOF="STATIC_PROOF"; PUBLIC_PROOF="PUBLIC_PROOF"; INFRA="INFRA"; SECURITY="SECURITY"

class ProofState(str, Enum):
    IDENTIFY="IDENTIFY"; LOCK_2A="2A_LOCK"; FINGERPRINT="FINGERPRINT"; REUSE_OR_PROVE="REUSE_OR_PROVE"; PUBLIC_CHECK_IF_REQUIRED="PUBLIC_CHECK_IF_REQUIRED"; RECEIPT="RECEIPT"; RUNLESS_FINAL_GATE="RUNLESS_FINAL_GATE"; MERGE_AUTHORIZED="MERGE_AUTHORIZED"; MERGED="MERGED"; POST_MERGE_VERIFY="POST_MERGE_VERIFY"; FREEZE="FREEZE"; READ_BACK="READ_BACK"; GREEN_FROZEN="GREEN_FROZEN"; FAILED="FAILED"; WAIT="WAIT"

class ProofRequest(BaseModel):
    task_id:str; workstream:str; candidate_sha:str=Field(pattern=r"^[0-9a-f]{40}$"); lease_id:str; authorization_id:str; expected_main_sha:str|None=None
class SliceEvidence(BaseModel):
    name:str; ok:bool; command:list[str]|None=None; stdout_digest:str|None=None; stderr_digest:str|None=None; duration_seconds:float=0.0; failure_class:FailureClass=FailureClass.NONE; deployment_identity:str|None=None; observed_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class ProofStatus(BaseModel):
    proof_id:str; state:ProofState; task_id:str; workstream:str; candidate_sha:str; failure_class:FailureClass=FailureClass.NONE; detail:str=""; receipt_digest:str|None=None
