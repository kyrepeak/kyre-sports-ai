from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx

from .models import FailureClass
from .sandbox_executor import SandboxEvidence


@dataclass(frozen=True)
class PublicProbe:
    url: str
    kind: str = "http"
    timeout_seconds: int = 30
    deployment_identity_header: str | None = None


async def run_public_probe(
    probe: PublicProbe,
    *,
    deployment_identity: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> SandboxEvidence:
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=probe.timeout_seconds, follow_redirects=True)
    try:
        try:
            response = await http.get(probe.url)
            text = response.text
            observed = (
                response.headers.get(probe.deployment_identity_header)
                if probe.deployment_identity_header
                else deployment_identity
            )
            ok = 200 <= response.status_code < 400
            if deployment_identity and observed and observed != deployment_identity:
                ok = False
            return SandboxEvidence(
                name=f"public:{probe.url}",
                ok=ok,
                stdout_digest=hashlib.sha256(text.encode()).hexdigest(),
                stderr_digest=hashlib.sha256(b"").hexdigest(),
                failure_class=FailureClass.NONE if ok else FailureClass.PUBLIC_PROOF,
                detail="" if ok else "RUNLESS_V2_PUBLIC_PROOF_FAILED",
            )
        except Exception:
            return SandboxEvidence(
                name=f"public:{probe.url}",
                ok=False,
                stdout_digest=hashlib.sha256(b"").hexdigest(),
                stderr_digest=hashlib.sha256(b"").hexdigest(),
                failure_class=FailureClass.INFRA,
                detail="RUNLESS_V2_PUBLIC_PROBE_UNAVAILABLE",
            )
    finally:
        if owns_client:
            await http.aclose()
