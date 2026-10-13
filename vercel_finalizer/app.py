from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

APP_ID_EXPECTED = "5204253"
REPOSITORY = "kyrepeak/kyre-sports-ai"
GATE_NAME = "runless-final-gate"
ALLOWED_BRANCH = "api2-universal-sports-source-finalization-v1-step1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")

app = FastAPI(title="Kyre Sports Finalizer", version="1.0.0")


@dataclass(frozen=True)
class Settings:
    app_id: str
    installation_id: str
    private_key: str
    repository: str = REPOSITORY
    gate_name: str = GATE_NAME

    @classmethod
    def from_env(cls) -> "Settings":
        app_id = os.getenv("GITHUB_APP_ID", "").strip()
        installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID", "").strip()
        private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
        if app_id != APP_ID_EXPECTED:
            raise RuntimeError("FINALIZER_GITHUB_APP_ID_MISMATCH")
        if not installation_id:
            raise RuntimeError("FINALIZER_INSTALLATION_ID_REQUIRED")
        if not private_key:
            raise RuntimeError("FINALIZER_PRIVATE_KEY_REQUIRED")
        return cls(app_id=app_id, installation_id=installation_id, private_key=private_key)


class ProveRequest(BaseModel):
    candidate_sha: str
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
    url = f"https://api.github.com/app/installations/{settings.installation_id}/access_tokens"
    response = client.post(
        url,
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


def _pr_head(client: httpx.Client, token: str) -> tuple[str, str]:
    response = client.get(
        f"https://api.github.com/repos/{REPOSITORY}/pulls/1526",
        headers=_headers(token),
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload["head"]["sha"]).lower(), str(payload["head"]["ref"])


def _existing_success(client: httpx.Client, token: str, sha: str) -> bool:
    response = client.get(
        f"https://api.github.com/repos/{REPOSITORY}/commits/{sha}/check-runs",
        headers=_headers(token),
    )
    response.raise_for_status()
    for run in response.json().get("check_runs", []):
        if (
            run.get("name") == GATE_NAME
            and run.get("conclusion") == "success"
            and str(run.get("app", {}).get("id")) == APP_ID_EXPECTED
        ):
            return True
    return False


def _publish_success(client: httpx.Client, token: str, sha: str, proof_digest: str) -> None:
    response = client.post(
        f"https://api.github.com/repos/{REPOSITORY}/check-runs",
        headers=_headers(token),
        json={
            "name": GATE_NAME,
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "Universal Sports Finalizer",
                "summary": f"exact-head proof={proof_digest}",
            },
        },
    )
    response.raise_for_status()


def _readback_success(client: httpx.Client, token: str, sha: str) -> bool:
    return _existing_success(client, token, sha)


@app.get("/health")
def health() -> dict[str, Any]:
    configured = all(
        os.getenv(key)
        for key in ("GITHUB_APP_ID", "GITHUB_APP_INSTALLATION_ID", "GITHUB_APP_PRIVATE_KEY")
    )
    return {
        "status": "ok",
        "configured": configured,
        "gate": GATE_NAME,
        "repository": REPOSITORY,
        "render_dependency": False,
        "github_actions_fallback": 0,
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
            token = _installation_token(settings, client)
            pr_sha, pr_ref = _pr_head(client, token)
            if pr_ref != ALLOWED_BRANCH or pr_sha != sha:
                raise HTTPException(status_code=409, detail="FINALIZER_PR_HEAD_MISMATCH")
            if _existing_success(client, token, sha):
                return {
                    "status": "success",
                    "reused": True,
                    "candidate_sha": sha,
                    "proof_digest": proof_digest,
                }
            _publish_success(client, token, sha, proof_digest)
            if not _readback_success(client, token, sha):
                raise HTTPException(status_code=502, detail="FINALIZER_CHECK_READBACK_FAILED")
            return {
                "status": "success",
                "reused": False,
                "candidate_sha": sha,
                "proof_digest": proof_digest,
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"FINALIZER_GITHUB_ERROR:{type(exc).__name__}",
        ) from exc
