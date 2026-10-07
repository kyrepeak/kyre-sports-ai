from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from devsystem.frozen_artifact_registry_v1 import evaluate_head
from devsystem.runless_proof_plan_v1 import load_plan
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

from .executor import execute_static_slice
from .fingerprint import build_fingerprint
from .gate import publish_gate
from .models import FailureClass, ProofState
from .public_probe import run_public_probe
from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend
from .step2a import Step2AError, Step2ASnapshot, authorize_proof
from .workspace import CandidateWorkspace

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"


class RunlessProofFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _proof_id(request) -> str:
    suffix = _digest(
        {
            "task_id": request.task_id,
            "workstream": request.workstream,
            "candidate_sha": request.candidate_sha,
            "lease_id": request.lease_id,
            "authorization_id": request.authorization_id,
        }
    )[:16]
    return f"{request.task_id}-{request.candidate_sha[:16]}-{suffix}"


def _repository_url(repository: str) -> str:
    return f"https://x-access-token@github.com/{repository}.git"


def _verify_frozen_candidate(client, candidate_sha: str, tree: dict[str, str]) -> dict[str, Any]:
    registry = GithubRegistryBackend(client).read_registry()
    evaluate_head(registry, tree, head_sha=candidate_sha)
    return {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": [str(item["thaw_id"]) for item in registry.get("active_thaws", [])],
    }


def _decode_json_content(raw: dict[str, Any] | None, error: str) -> dict[str, Any]:
    if not raw or raw.get("encoding") != "base64":
        raise Step2AError(error)
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Step2AError(error) from exc


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_live_scope_lease(client, lease_id: str) -> str:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(
        _decode_json_content(raw, "RUNLESS_SCOPE_LEASE_STATE_READ_FAILED")
    )
    now = datetime.now(timezone.utc)
    matches = [
        holder
        for holder in state.get("holders", [])
        if holder.get("lease_id") == lease_id and now < _utc(holder["expires_at_utc"])
    ]
    if len(matches) != 1:
        raise Step2AError("RUNLESS_SCOPE_LEASE_NOT_LIVE")
    return str(matches[0]["lease_id"])


def _path_map(tree: dict[str, str], paths: tuple[str, ...], label: str) -> dict[str, str]:
    missing = [path for path in paths if path not in tree]
    if missing:
        raise RunlessProofFailure(f"RUNLESS_{label}_MISSING:" + ",".join(sorted(missing)))
    return {path: tree[path] for path in sorted(paths)}


def _receipt_store(client, candidate_sha: str, settings) -> ReceiptStore:
    return ReceiptStore(
        GithubReceiptBackend(
            client,
            candidate_sha,
            settings.receipt_ref,
            settings.receipt_path,
        ),
        settings.receipt_ref,
        settings.receipt_path,
    )


def _failed_result(orchestrator, proof_id, request_fingerprint, request, settings, client, detail, failure_class):
    status = orchestrator.fail(proof_id, request_fingerprint, detail)
    status.failure_class = failure_class
    publish_gate(client, request.candidate_sha, "failure", None, settings.gate_name)
    return {
        "proof_id": proof_id,
        "status": "FAILED",
        "state": status.state.value,
        "candidate_sha": request.candidate_sha,
        "failure_class": failure_class.value,
        "detail": detail,
        "github_actions_enabled": False,
    }


def execute_proof_request(request, *, settings, github_client, orchestrator, receipts):
    """Execute one exact pre-merge Runless proof chain.

    The chain intentionally stops at MERGE_AUTHORIZED. Merge, post-merge
    verification, freeze and read-back remain later Task-17 closeout stages.
    """
    if getattr(github_client, "repository", settings.repository) != settings.repository:
        raise Step2AError("RUNLESS_REPOSITORY_IDENTITY_DRIFT")

    commit = github_client.commit(request.candidate_sha)
    if str(commit.get("sha") or "") != request.candidate_sha:
        raise Step2AError("RUNLESS_EXACT_HEAD_DRIFT")
    main_sha = github_client.branch_sha("main")
    token = github_client.auth.installation_token()

    with CandidateWorkspace(
        _repository_url(settings.repository),
        request.candidate_sha,
        token=token,
    ) as workspace:
        plan = load_plan(request.task_id, workspace.path)
        if plan.workstream != request.workstream:
            raise Step2AError("RUNLESS_PLAN_WORKSTREAM_MISMATCH")

        tree = github_client.tree_blobs(request.candidate_sha)
        registry = _verify_frozen_candidate(github_client, request.candidate_sha, tree)
        live_lease = _read_live_scope_lease(github_client, request.lease_id)
        snapshot = Step2ASnapshot(
            candidate_sha=request.candidate_sha,
            main_sha=main_sha,
            registry_revision=registry["revision"],
            registry_hash=registry["state_hash"],
            active_thaws=tuple(registry["active_thaws"]),
            scope_lease=live_lease,
            rollback_anchor=main_sha,
            workstream=plan.workstream,
        )
        authorize_proof(snapshot, request)

        artifact_map = _path_map(tree, plan.artifacts, "ARTIFACT")
        dependency_map = _path_map(tree, plan.dependencies, "DEPENDENCY")
        fingerprint = build_fingerprint(
            artifact_map,
            dependency_map,
            policy={
                "commands": [list(command) for command in plan.commands],
                "probes": [probe.__dict__ for probe in plan.probes],
                "timeout_seconds": plan.timeout_seconds,
                "live_ttl_seconds": plan.live_ttl_seconds,
                "freeze_token": plan.freeze_token,
            },
            scope={
                "task_id": plan.task_id,
                "workstream": plan.workstream,
                "lease_id": request.lease_id,
                "authorization_id": request.authorization_id,
            },
            deployment_identity=settings.deployment_identity,
        )

        proof_id = _proof_id(request)
        request_fingerprint = _digest(
            {
                "request": request.model_dump(mode="json"),
                "proof_fingerprint": fingerprint.digest,
            }
        )
        orchestrator.start(request, proof_id, request_fingerprint)
        orchestrator.advance(proof_id, ProofState.LOCK_2A)
        orchestrator.advance(proof_id, ProofState.FINGERPRINT)
        orchestrator.advance(proof_id, ProofState.REUSE_OR_PROVE)

        static_evidence = execute_static_slice(plan, workspace)
        failed_static = next((item for item in static_evidence if not item.ok), None)
        if failed_static:
            return _failed_result(
                orchestrator,
                proof_id,
                request_fingerprint,
                request,
                settings,
                github_client,
                f"RUNLESS_STATIC_PROOF_FAILED:{failed_static.name}",
                failed_static.failure_class,
            )

        orchestrator.advance(proof_id, ProofState.PUBLIC_CHECK_IF_REQUIRED)
        public_evidence = [
            run_public_probe(probe, deployment_identity=settings.deployment_identity)
            for probe in plan.probes
        ]
        failed_public = next((item for item in public_evidence if not item.ok), None)
        if failed_public:
            return _failed_result(
                orchestrator,
                proof_id,
                request_fingerprint,
                request,
                settings,
                github_client,
                f"RUNLESS_PUBLIC_PROOF_FAILED:{failed_public.name}",
                failed_public.failure_class,
            )

        evidence = static_evidence + public_evidence
        evidence_digests = [_digest(item.model_dump(mode="json")) for item in evidence]
        registry_receipt = {
            "revision": registry["revision"],
            "state_hash": registry["state_hash"],
            "active_thaws": list(registry["active_thaws"]),
        }
        store = _receipt_store(github_client, request.candidate_sha, settings)
        receipt_path = f"{store.base_path}/{proof_id}.json"
        if store.backend.exists(receipt_path, store.ref):
            receipt = store.get(proof_id)
            if (
                receipt.get("candidate_sha") != request.candidate_sha
                or receipt.get("task_id") != request.task_id
                or receipt.get("workstream") != request.workstream
            ):
                raise RunlessProofFailure("RUNLESS_RECEIPT_IDENTITY_COLLISION")
        else:
            receipt = build_runless_receipt(
                proof_id=proof_id,
                task_id=request.task_id,
                project="API2",
                workstream=request.workstream,
                step="task17-step1-real-prove-execution",
                candidate_sha=request.candidate_sha,
                artifact_map=artifact_map,
                dependency_map=dependency_map,
                registry_before=registry_receipt,
                registry_after=registry_receipt,
                evidence_digests=evidence_digests,
                failure_class=FailureClass.NONE.value,
                deployment_identity=settings.deployment_identity,
                proof_fingerprint=fingerprint.digest,
            )
            store.put(receipt)

        receipts[proof_id] = receipt
        status = orchestrator.advance(proof_id, ProofState.RECEIPT)
        status.receipt_digest = receipt["digest"]
        orchestrator.advance(proof_id, ProofState.RUNLESS_FINAL_GATE)
        publish_gate(
            github_client,
            request.candidate_sha,
            "success",
            receipt,
            settings.gate_name,
        )
        status = orchestrator.advance(proof_id, ProofState.MERGE_AUTHORIZED)

        return {
            "proof_id": proof_id,
            "status": status.state.value,
            "state": status.state.value,
            "candidate_sha": request.candidate_sha,
            "receipt": receipt,
            "receipt_digest": receipt["digest"],
            "proof_fingerprint": fingerprint.digest,
            "artifact_count": len(artifact_map),
            "dependency_count": len(dependency_map),
            "static_evidence_count": len(static_evidence),
            "public_evidence_count": len(public_evidence),
            "github_actions_enabled": False,
        }
