from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FailureClass(str, Enum):
    NONE = "NONE"
    PLAN = "PLAN"
    IDENTITY = "IDENTITY"
    LEASE = "LEASE"
    REGISTRY = "REGISTRY"
    STATIC_PROOF = "STATIC_PROOF"
    PUBLIC_PROOF = "PUBLIC_PROOF"
    INFRA = "INFRA"
    SECURITY = "SECURITY"


class ProofState(str, Enum):
    IDENTIFY = "IDENTIFY"
    LOCK_2A = "2A_LOCK"
    FINGERPRINT = "FINGERPRINT"
    REUSE_OR_PROVE = "REUSE_OR_PROVE"
    PUBLIC_CHECK_IF_REQUIRED = "PUBLIC_CHECK_IF_REQUIRED"
    RECEIPT = "RECEIPT"
    RUNLESS_FINAL_GATE = "RUNLESS_FINAL_GATE"
    MERGE_AUTHORIZED = "MERGE_AUTHORIZED"
    MERGED = "MERGED"
    POST_MERGE_VERIFY = "POST_MERGE_VERIFY"
    FREEZE = "FREEZE"
    READ_BACK = "READ_BACK"
    GREEN_FROZEN = "GREEN_FROZEN"
    FAILED = "FAILED"


class ProofRequest(BaseModel):
    task_id: str
    workstream: str
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    lease_id: str
    authorization_id: str
    expected_main_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class RegistryThawRequest(BaseModel):
    repository: str = Field(min_length=1)
    workstream: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    thaw_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    from_blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    to_blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    expected_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")


class RegistryForwardPortRequest(BaseModel):
    repository: str = Field(min_length=1)
    workstream: str = Field(min_length=1)
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merged_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    thaw_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    from_blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    to_blob: str = Field(pattern=r"^[0-9a-f]{40}$")


class LeaseClaim(BaseModel):
    proof_id: str
    workstream: str
    lease_token: str | None = None
    fencing_generation: int
    expires_at: str | None = None
    state: ProofState
    reused: bool = False


class ProofStatus(BaseModel):
    proof_id: str
    task_id: str
    workstream: str
    candidate_sha: str
    expected_main_sha: str | None = None
    scope_lease_id: str
    authorization_id: str
    request_fingerprint: str
    proof_fingerprint: str | None = None
    state: ProofState
    failure_class: FailureClass = FailureClass.NONE
    detail: str = ""
    fencing_generation: int = 0
    receipt_digest: str | None = None
    gate_check_run_id: int | None = None
    merged_main_sha: str | None = None
    freeze_token: str | None = None
    manifest_state_hash: str | None = None
    terminal_at: str | None = None


class ProofResult(BaseModel):
    proof_id: str
    status: ProofState
    candidate_sha: str
    receipt: dict[str, Any] | None = None
    receipt_digest: str | None = None
