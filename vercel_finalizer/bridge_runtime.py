from __future__ import annotations

import os
import re
import uuid
from typing import Any

import httpx
from fastapi import HTTPException


def install_bridge(ns: dict[str, Any]) -> None:
    Settings = ns["Settings"]
    app = ns["app"]

    @classmethod
    def from_env(cls):
        app_id = os.getenv("GITHUB_APP_ID", "").strip()
        installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID", "").strip()
        private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
        supabase_url = os.getenv("SUPABASE_URL", "").strip()
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if app_id != ns["APP_ID_EXPECTED"]:
            raise RuntimeError("FINALIZER_GITHUB_APP_ID_MISMATCH")
        if not installation_id:
            raise RuntimeError("FINALIZER_INSTALLATION_ID_REQUIRED")
        if not private_key:
            raise RuntimeError("FINALIZER_PRIVATE_KEY_REQUIRED")
        if not supabase_url:
            raise RuntimeError("FINALIZER_RUNLESS_AUTHORITY_REQUIRED")
        return cls(app_id, installation_id, private_key, supabase_url, service_key)

    Settings.from_env = from_env

    app.router.routes[:] = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) not in {"/health", "/health/authority", "/prove"}
    ]

    def health() -> dict[str, Any]:
        configured = all(
            os.getenv(key)
            for key in (
                "GITHUB_APP_ID",
                "GITHUB_APP_INSTALLATION_ID",
                "GITHUB_APP_PRIVATE_KEY",
                "SUPABASE_URL",
            )
        )
        transport = (
            "direct_supabase"
            if os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            else "supabase_edge_bridge"
        )
        return {
            "status": "ok" if configured else "degraded",
            "configured": configured,
            "gate": ns["GATE_NAME"],
            "repository": ns["REPOSITORY"],
            "render_dependency": False,
            "github_actions_fallback": 0,
            "authority": "runless_v2",
            "authority_transport": transport,
        }

    def health_authority() -> dict[str, Any]:
        try:
            settings = Settings.from_env()
            if settings.supabase_service_role_key:
                return {
                    "status": "ok",
                    "transport": "direct_supabase",
                    "app_id": ns["APP_ID_EXPECTED"],
                    "supabase": "configured",
                }
            with httpx.Client(timeout=15) as client:
                body = ns["authority_bridge_health"](
                    client,
                    supabase_url=settings.supabase_url,
                    app_jwt=ns["_app_jwt"](settings),
                )
            return {
                "status": "ok",
                "transport": "supabase_edge_bridge",
                "app_id": str(body["app_id"]),
                "supabase": str(body.get("supabase") or "healthy"),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"FINALIZER_AUTHORITY_HEALTH_FAILED:{type(exc).__name__}",
            ) from exc

    def prove(request):
        sha = request.candidate_sha.strip().lower()
        if not ns["_SHA40"].fullmatch(sha):
            raise HTTPException(status_code=400, detail="FINALIZER_INVALID_CANDIDATE_SHA")
        proof_digest = request.proof_digest.strip().lower()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", proof_digest):
            raise HTTPException(status_code=400, detail="FINALIZER_INVALID_PROOF_DIGEST")
        deployed_sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
        if deployed_sha and deployed_sha != sha:
            raise HTTPException(status_code=409, detail="FINALIZER_DEPLOYMENT_SHA_MISMATCH")

        try:
            settings = Settings.from_env()
            with httpx.Client(timeout=15) as client:
                app_jwt = ns["_app_jwt"](settings)
                if settings.supabase_service_role_key:
                    authority = ns["resolve_authority"](
                        client,
                        supabase_url=settings.supabase_url,
                        service_role_key=settings.supabase_service_role_key,
                        workstream=request.workstream,
                        task_id=request.task_id,
                        candidate_sha=sha,
                        fencing_generation=request.fencing_generation,
                    )
                else:
                    authority = ns["resolve_authority_via_bridge"](
                        client,
                        supabase_url=settings.supabase_url,
                        app_jwt=app_jwt,
                        workstream=request.workstream,
                        task_id=request.task_id,
                        candidate_sha=sha,
                        fencing_generation=request.fencing_generation,
                    )
                if authority.candidate_sha != sha:
                    raise HTTPException(status_code=409, detail="FINALIZER_AUTHORITY_SHA_MISMATCH")

                token = ns["_installation_token"](settings, client)
                binding = ns["resolve_receipt_binding"](
                    client,
                    token=token,
                    repository=settings.repository,
                    receipt_ref=os.getenv("RPP_RECEIPT_REF", "runless-proof-receipts").strip()
                    or "runless-proof-receipts",
                    receipt_path=os.getenv("RPP_RECEIPT_PATH", "devsystem/runless_proof_receipts").strip()
                    or "devsystem/runless_proof_receipts",
                    authority=authority,
                    requested_proof_digest=proof_digest,
                )
                proof_digest = binding.proof_digest
                claim_token = uuid.uuid4().hex

                if settings.supabase_service_role_key:
                    claim = ns["claim_publication"](
                        client,
                        supabase_url=settings.supabase_url,
                        service_role_key=settings.supabase_service_role_key,
                        proof_id=authority.proof_id,
                        candidate_sha=sha,
                        fencing_generation=authority.fencing_generation,
                        proof_digest=proof_digest,
                        claim_token=claim_token,
                    )
                else:
                    claim = ns["claim_publication_via_bridge"](
                        client,
                        supabase_url=settings.supabase_url,
                        app_jwt=app_jwt,
                        proof_id=authority.proof_id,
                        candidate_sha=sha,
                        fencing_generation=authority.fencing_generation,
                        proof_digest=proof_digest,
                        claim_token=claim_token,
                    )

                checks = ns["_check_runs"](client, token, sha)
                if claim.reused:
                    gate = ns["exact_gate_check"](
                        checks,
                        candidate_sha=sha,
                        proof_digest=proof_digest,
                        proof_id=authority.proof_id,
                        expected_check_run_id=claim.gate_check_run_id,
                    )
                    return {
                        "status": "success",
                        "reused": True,
                        "candidate_sha": sha,
                        "proof_digest": proof_digest,
                        "proof_id": authority.proof_id,
                        "gate_check_run_id": int(gate["id"]),
                    }

                existing = ns["find_exact_gate"](
                    checks,
                    candidate_sha=sha,
                    proof_digest=proof_digest,
                    proof_id=authority.proof_id,
                )
                if existing is not None:
                    completed_id = _complete(
                        ns,
                        client,
                        settings,
                        app_jwt,
                        authority.proof_id,
                        str(claim.claim_token),
                        int(existing["id"]),
                    )
                    return {
                        "status": "success",
                        "reused": True,
                        "candidate_sha": sha,
                        "proof_digest": proof_digest,
                        "proof_id": authority.proof_id,
                        "gate_check_run_id": completed_id,
                    }

                published = ns["_publish_success"](
                    client, token, sha, proof_digest, authority.proof_id
                )
                published_id = int(published["id"])
                gate = ns["exact_gate_check"](
                    ns["_check_runs"](client, token, sha),
                    candidate_sha=sha,
                    proof_digest=proof_digest,
                    proof_id=authority.proof_id,
                    expected_check_run_id=published_id,
                )
                completed_id = _complete(
                    ns,
                    client,
                    settings,
                    app_jwt,
                    authority.proof_id,
                    str(claim.claim_token),
                    int(gate["id"]),
                )
                return {
                    "status": "success",
                    "reused": False,
                    "candidate_sha": sha,
                    "proof_digest": proof_digest,
                    "proof_id": authority.proof_id,
                    "gate_check_run_id": completed_id,
                }
        except (
            ns["FinalizerAuthorityError"],
            ns["ReceiptBindingError"],
            ns["GatePublicationError"],
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"FINALIZER_ERROR:{type(exc).__name__}",
            ) from exc

    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/health/authority", health_authority, methods=["GET"])
    app.add_api_route("/prove", prove, methods=["POST"])


def _complete(
    ns: dict[str, Any],
    client: Any,
    settings: Any,
    app_jwt: str,
    proof_id: str,
    claim_token: str,
    gate_check_run_id: int,
) -> int:
    if settings.supabase_service_role_key:
        return ns["complete_publication"](
            client,
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            proof_id=proof_id,
            claim_token=claim_token,
            gate_check_run_id=gate_check_run_id,
        )
    return ns["complete_publication_via_bridge"](
        client,
        supabase_url=settings.supabase_url,
        app_jwt=app_jwt,
        proof_id=proof_id,
        claim_token=claim_token,
        gate_check_run_id=gate_check_run_id,
    )
