from __future__ import annotations

import hashlib
import json
from typing import Any

from .github_authority import GithubAuthorityError
from .models import FailureClass, ProofRequest, ProofResult, ProofState
from .public_probe import PublicProbe, run_public_probe
from .receipt_contract import build_receipt, validate_receipt
from .sandbox_executor import SandboxExecutionError


class ProofServiceError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def build_proof_id(request: ProofRequest) -> str:
    suffix = _digest({
        "task_id": request.task_id,
        "workstream": request.workstream,
        "candidate_sha": request.candidate_sha,
        "lease_id": request.lease_id,
        "authorization_id": request.authorization_id,
    })[:16]
    return f"{request.task_id}-{request.candidate_sha[:16]}-{suffix}"


def _proof_fingerprint(context: dict[str, Any], plan: dict[str, Any], request: ProofRequest) -> str:
    return _digest({
        "artifacts": context["artifact_map"],
        "dependencies": context["dependency_map"],
        "policy": {
            "commands": plan.get("commands", []),
            "probes": plan.get("probes", []),
            "timeout_seconds": plan.get("timeout_seconds", 900),
            "live_ttl_seconds": plan.get("live_ttl_seconds", 900),
            "freeze_token": plan.get("freeze_token"),
        },
        "scope": {
            "task_id": request.task_id,
            "workstream": request.workstream,
            "lease_id": request.lease_id,
            "authorization_id": request.authorization_id,
        },
    })


def _request_fingerprint(request: ProofRequest, proof_fingerprint: str) -> str:
    return _digest({
        "request": request.model_dump(mode="json"),
        "proof_fingerprint": proof_fingerprint,
    })


def _evidence_digest(item: Any) -> str:
    if hasattr(item, "model_dump"):
        item = item.model_dump(mode="json")
    return _digest(item)


def _failure_detail(exc: BaseException) -> str:
    return str(exc) or type(exc).__name__


def _identity_failure_class(detail: str) -> FailureClass:
    upper = detail.upper()
    if "REGISTRY" in upper or "FROZEN" in upper or "THAW" in upper:
        return FailureClass.REGISTRY
    if "RECEIPT" in upper and ("COLLISION" in upper or "TAMPER" in upper):
        return FailureClass.SECURITY
    if any(marker in upper for marker in ("IDENTITY", "HEAD", "MAIN", "LEASE", "PLAN_WORKSTREAM")):
        return FailureClass.IDENTITY
    return FailureClass.INFRA


def _failed_result(request: ProofRequest, proof_id: str, status: Any) -> ProofResult:
    return ProofResult(
        proof_id=proof_id,
        status=ProofState.FAILED,
        candidate_sha=request.candidate_sha,
        receipt=None,
        receipt_digest=getattr(status, "receipt_digest", None),
    )


def _load_plan(github: Any, request: ProofRequest) -> dict[str, Any]:
    path = f"devsystem/runless_proof_plans/{request.task_id}.json"
    try:
        plan = github._content_json(path, request.candidate_sha)
    except Exception as exc:
        raise ProofServiceError("RUNLESS_V2_PLAN_LOAD_FAILED") from exc
    if plan.get("task_id") != request.task_id:
        raise ProofServiceError("RUNLESS_V2_PLAN_ID_MISMATCH")
    if plan.get("workstream") != request.workstream or not plan.get("freeze_token"):
        raise ProofServiceError("RUNLESS_V2_PLAN_REQUIRED_FIELDS")
    return plan


def _preflight(github: Any, request: ProofRequest, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    candidate_tree = github.tree_blobs(request.candidate_sha)
    main_sha = github.main_sha()
    main_tree = github.tree_blobs(main_sha)
    context = github.verify_step2a(request, plan, candidate_tree, main_tree)
    return context, candidate_tree


def _validate_reused_receipt(proof_id: str, request: ProofRequest, mirror: dict[str, Any], github: Any) -> dict[str, Any]:
    receipt = mirror.get("receipt_json")
    if not isinstance(receipt, dict):
        raise ProofServiceError("RUNLESS_V2_REUSE_RECEIPT_REQUIRED")
    validate_receipt(receipt)
    if (
        receipt.get("proof_id") != proof_id
        or receipt.get("task_id") != request.task_id
        or receipt.get("workstream") != request.workstream
        or receipt.get("candidate_sha") != request.candidate_sha
        or mirror.get("receipt_digest") != receipt.get("digest")
    ):
        raise ProofServiceError("RUNLESS_V2_REUSE_RECEIPT_IDENTITY_MISMATCH")
    immutable = github.put_or_read_receipt(receipt)
    if immutable.get("digest") != receipt["digest"]:
        raise ProofServiceError("RUNLESS_V2_REUSE_RECEIPT_READBACK_MISMATCH")
    return immutable


async def execute_proof_request(
    request: ProofRequest,
    *,
    state_store: Any,
    github: Any,
    sandbox: Any,
) -> ProofResult:
    plan = _load_plan(github, request)
    context, candidate_tree = _preflight(github, request, plan)
    proof_fingerprint = _proof_fingerprint(context, plan, request)
    request_fingerprint = _request_fingerprint(request, proof_fingerprint)
    proof_id = build_proof_id(request)
    ttl_seconds = int(plan.get("live_ttl_seconds", 900))

    claim = state_store.claim(
        request,
        request_fingerprint,
        ttl_seconds,
        proof_id=proof_id,
    )

    if claim.reused:
        durable = state_store.status(proof_id)
        if durable.state is ProofState.MERGE_AUTHORIZED:
            mirror = state_store.receipt_mirror(proof_id)
            receipt = _validate_reused_receipt(proof_id, request, mirror, github)
            return ProofResult(
                proof_id=proof_id,
                status=ProofState.MERGE_AUTHORIZED,
                candidate_sha=request.candidate_sha,
                receipt=receipt,
                receipt_digest=receipt["digest"],
            )
        return ProofResult(
            proof_id=proof_id,
            status=durable.state,
            candidate_sha=request.candidate_sha,
            receipt=None,
            receipt_digest=durable.receipt_digest,
        )

    state_store.advance(proof_id, ProofState.IDENTIFY, ProofState.LOCK_2A, claim)
    state_store.advance(proof_id, ProofState.LOCK_2A, ProofState.FINGERPRINT, claim)
    state_store.advance(proof_id, ProofState.FINGERPRINT, ProofState.REUSE_OR_PROVE, claim)

    try:
        sandbox_result = await sandbox.execute(
            candidate_sha=request.candidate_sha,
            task_id=request.task_id,
            github_token=github.installation_token(),
            timeout_seconds=int(plan.get("timeout_seconds", 900)),
        )
    except SandboxExecutionError as exc:
        detail = _failure_detail(exc)
        failure_class = _identity_failure_class(detail)
        if failure_class is FailureClass.INFRA:
            failed = state_store.release_infra(claim, detail=detail)
        else:
            failed = state_store.record_failure_and_release(
                claim,
                failure_class=failure_class,
                detail=detail,
                record_fingerprint=True,
            )
        return _failed_result(request, proof_id, failed)
    except Exception as exc:
        failed = state_store.release_infra(
            claim, detail=f"RUNLESS_V2_SANDBOX_UNAVAILABLE:{type(exc).__name__}"
        )
        return _failed_result(request, proof_id, failed)

    if _canonical(sandbox_result.plan) != _canonical(plan):
        failed = state_store.record_failure_and_release(
            claim,
            failure_class=FailureClass.PLAN,
            detail="RUNLESS_V2_SANDBOX_PLAN_DRIFT",
            record_fingerprint=True,
        )
        return _failed_result(request, proof_id, failed)

    failed_evidence = next((item for item in sandbox_result.evidence if not item.ok), None)
    if failed_evidence is not None or not sandbox_result.ok:
        detail = failed_evidence.detail if failed_evidence is not None else "RUNLESS_V2_STATIC_PROOF_EMPTY"
        failure_class = failed_evidence.failure_class if failed_evidence is not None else FailureClass.INFRA
        if failure_class is FailureClass.INFRA:
            failed = state_store.release_infra(claim, detail=detail)
        else:
            failed = state_store.record_failure_and_release(
                claim,
                failure_class=failure_class,
                detail=detail,
                record_fingerprint=True,
            )
        return _failed_result(request, proof_id, failed)

    state_store.advance(
        proof_id, ProofState.REUSE_OR_PROVE, ProofState.PUBLIC_CHECK_IF_REQUIRED, claim
    )

    public_evidence = []
    for raw_probe in plan.get("probes", []):
        probe = PublicProbe(**raw_probe)
        evidence = await run_public_probe(probe)
        public_evidence.append(evidence)
        if not evidence.ok:
            if evidence.failure_class is FailureClass.INFRA:
                failed = state_store.release_infra(claim, detail=evidence.detail)
            else:
                failed = state_store.record_failure_and_release(
                    claim,
                    failure_class=FailureClass.PUBLIC_PROOF,
                    detail=evidence.detail or "RUNLESS_V2_PUBLIC_PROOF_FAILED",
                    record_fingerprint=True,
                )
            return _failed_result(request, proof_id, failed)

    state_store.advance(
        proof_id, ProofState.PUBLIC_CHECK_IF_REQUIRED, ProofState.RECEIPT, claim
    )

    evidence_digests = [
        _evidence_digest(item) for item in [*sandbox_result.evidence, *public_evidence]
    ]
    registry_receipt = dict(context["registry"])
    receipt = build_receipt(
        proof_id=proof_id,
        task_id=request.task_id,
        project="API2",
        workstream=request.workstream,
        step="runless-v2-premerge",
        candidate_sha=request.candidate_sha,
        artifact_map=context["artifact_map"],
        dependency_map=context["dependency_map"],
        registry_before=registry_receipt,
        registry_after=registry_receipt,
        evidence_digests=evidence_digests,
        failure_class=FailureClass.NONE.value,
        proof_fingerprint=proof_fingerprint,
        request_fingerprint=request_fingerprint,
    )

    try:
        receipt = github.put_or_read_receipt(receipt)
    except GithubAuthorityError as exc:
        detail = _failure_detail(exc)
        failed = state_store.record_failure_and_release(
            claim,
            failure_class=_identity_failure_class(detail),
            detail=detail,
            record_fingerprint=True,
        )
        return _failed_result(request, proof_id, failed)

    state_store.advance(proof_id, ProofState.RECEIPT, ProofState.RUNLESS_FINAL_GATE, claim)

    claim = state_store.renew(claim, ttl_seconds)
    try:
        current_main = github.main_sha()
        fresh_main_tree = github.tree_blobs(current_main)
        github.verify_step2a(request, plan, candidate_tree, fresh_main_tree)
    except GithubAuthorityError as exc:
        detail = _failure_detail(exc)
        failed = state_store.record_failure_and_release(
            claim,
            failure_class=_identity_failure_class(detail),
            detail=detail,
            record_fingerprint=True,
        )
        return _failed_result(request, proof_id, failed)

    try:
        gate = github.publish_gate_and_readback(request.candidate_sha, receipt)
    except GithubAuthorityError as exc:
        failed = state_store.release_infra(claim, detail=_failure_detail(exc))
        return _failed_result(request, proof_id, failed)

    durable = state_store.record_merge_authorized_and_release_execution(
        claim,
        proof_fingerprint=proof_fingerprint,
        receipt_digest=receipt["digest"],
        gate_check_run_id=int(gate["id"]),
        receipt_json=receipt,
        github_receipt_ref="runless-proof-receipts",
        github_receipt_path=f"devsystem/runless_proof_receipts/{proof_id}.json",
    )
    return ProofResult(
        proof_id=proof_id,
        status=durable.state,
        candidate_sha=request.candidate_sha,
        receipt=receipt,
        receipt_digest=receipt["digest"],
    )
