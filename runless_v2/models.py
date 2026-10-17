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
    SUPERSEDED_BASE_DRIFT = "SUPERSEDED_BASE_DRIFT"
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


class AuthoritySupersession(BaseModel):
    supersession_id: str
    workstream: str
    old_proof_id: str
    old_candidate_sha: str
    old_expected_main_sha: str | None = None
    successor_candidate_sha: str
    successor_expected_main_sha: str
    reason: str
    github_pr_number: int | None = None
    github_branch: str
    old_gate_check_run_id: int
    old_receipt_digest: str
    created_at: str


class ProofResult(BaseModel):
    proof_id: str
    status: ProofState
    candidate_sha: str
    receipt: dict[str, Any] | None = None
    receipt_digest: str | None = None
