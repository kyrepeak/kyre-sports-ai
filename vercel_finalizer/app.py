from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vercel_finalizer.authority import FinalizerAuthorityError, resolve_authority
from vercel_finalizer.gate_publication import (
    GatePublicationError,
    claim_publication,
    complete_publication,
    exact_gate_check,
    find_exact_gate,
)
from vercel_finalizer.receipt_binding import ReceiptBindingError, resolve_receipt_binding

APP_ID_EXPECTED = "5204253"
REPOSITORY = "kyrepeak/kyre-sports-ai"
GATE_NAME = "runless-final-gate"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")

app = FastAPI(title="Kyre Sports Finalizer", version="1.2.0")


@dataclass(frozen=True)
class Settings:
    app_id: str
    installation_id: str
    private_key: str
    supabase_url: str
    supabase_service_role_key: str
    repository: str = REPOSITORY
    gate_name: str = GATE_NAME

    @classmethod
    def from_env(cls) -> "Settings":
        app_id = os.getenv("GITHUB_APP_ID", "").strip()
        installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID", "").strip()
        private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
        supabase_url = os.getenv("SUPABASE_URL", "").strip()
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if app_id != APP_ID_EXPECTED:
            raise RuntimeError("FINALIZER_GITHUB_APP_ID_MISMATCH")
        if not installation_id:
            raise RuntimeError("FINALIZER_INSTALLATION_ID_REQUIRED")
        if not private_key:
            raise RuntimeError("FINALIZER_PRIVATE_KEY_REQUIRED")
        if not supabase_url or not service_key:
            raise RuntimeError("FINALIZER_RUNLESS_AUTHORITY_REQUIRED")
        return cls(app_id, installation_id, private_key, supabase_url, service_key)


class ProveRequest(BaseModel):
    workstream: str
    task_id: str
    candidate_sha: str
    fencing_generation: int
    proof_digest: str


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _app_jwt(settings: Settings) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 30, "exp": now + 540, "iss": settings.app_id},
        settings.private_key,
        algorithm="RS256",
    )


def _installation_token(settings: Settings, client: httpx.Client) -> str:
    response = client.post(
        f"https://api.github.com/app/installations/{settings.installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {_app_jwt(settings)}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("FINALIZER_INSTALLATION_TOKEN_MISSING")
    return str(token)


def _check_runs(client: httpx.Client, token: str, sha: str) -> list[dict[str, Any]]:
    response = client.get(
        f"https://api.github.com/repos/{REPOSITORY}/commits/{sha}/check-runs",
        headers=_headers(token),
    )
    response.raise_for_status()
    return list(response.json().get("check_runs", []))


def _publish_success(
    client: httpx.Client,
    token: str,
    sha: str,
    proof_digest: str,
    proof_id: str,
) -> dict[str, Any]:
    receipt_digest = proof_digest.removeprefix("sha256:")
    response = client.post(
        f"https://api.github.com/repos/{REPOSITORY}/check-runs",
        headers=_headers(token),
        json={
            "name": GATE_NAME,
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "Runless V2 Proof Authority",
                "summary": f"runless-v2 receipt={receipt_digest} proof={proof_id}",
            },
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or int(payload.get("id") or 0) <= 0:
        raise GatePublicationError("FINALIZER_GATE_PUBLISH_RESPONSE_INVALID")
    return dict(payload)


@app.get("/health")
def health() -> dict[str, Any]:
    configured = all(
        os.getenv(key)
        for key in (
            "GITHUB_APP_ID",
            "GITHUB_APP_INSTALLATION_ID",
            "GITHUB_APP_PRIVATE_KEY",
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
        )
    )
    return {
        "status": "ok" if configured else "degraded",
        "configured": configured,
        "gate": GATE_NAME,
        "repository": REPOSITORY,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "authority": "runless_v2",
    }


@app.post("/prove")
def prove(request: ProveRequest) -> dict[str, Any]:
    sha = request.candidate_sha.strip().lower()
    if not _SHA40.fullmatch(sha):
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
            authority = resolve_authority(
                client,
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
                workstream=request.workstream,
                task_id=request.task_id,
                candidate_sha=sha,
                fencing_generation=request.fencing_generation,
            )
            if authority.candidate_sha != sha:
                raise HTTPException(status_code=409, detail="FINALIZER_AUTHORITY_SHA_MISMATCH")

            token = _installation_token(settings, client)
            binding = resolve_receipt_binding(
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

            requested_claim_token = uuid.uuid4().hex
            claim = claim_publication(
                client,
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
                proof_id=authority.proof_id,
                candidate_sha=sha,
                fencing_generation=authority.fencing_generation,
                proof_digest=proof_digest,
                claim_token=requested_claim_token,
            )

            checks = _check_runs(client, token, sha)
            if claim.reused:
                gate = exact_gate_check(
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

            existing = find_exact_gate(
                checks,
                candidate_sha=sha,
                proof_digest=proof_digest,
                proof_id=authority.proof_id,
            )
            if existing is not None:
                completed_id = complete_publication(
                    client,
                    supabase_url=settings.supabase_url,
                    service_role_key=settings.supabase_service_role_key,
                    proof_id=authority.proof_id,
                    claim_token=str(claim.claim_token),
                    gate_check_run_id=int(existing["id"]),
                )
                return {
                    "status": "success",
                    "reused": True,
                    "candidate_sha": sha,
                    "proof_digest": proof_digest,
                    "proof_id": authority.proof_id,
                    "gate_check_run_id": completed_id,
                }

            published = _publish_success(
                client,
                token,
                sha,
                proof_digest,
                authority.proof_id,
            )
            published_id = int(published["id"])
            gate = exact_gate_check(
                _check_runs(client, token, sha),
                candidate_sha=sha,
                proof_digest=proof_digest,
                proof_id=authority.proof_id,
                expected_check_run_id=published_id,
            )
            completed_id = complete_publication(
                client,
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
                proof_id=authority.proof_id,
                claim_token=str(claim.claim_token),
                gate_check_run_id=int(gate["id"]),
            )
            return {
                "status": "success",
                "reused": False,
                "candidate_sha": sha,
                "proof_digest": proof_digest,
                "proof_id": authority.proof_id,
                "gate_check_run_id": completed_id,
            }
    except (FinalizerAuthorityError, ReceiptBindingError, GatePublicationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FINALIZER_ERROR:{type(exc).__name__}") from exc
