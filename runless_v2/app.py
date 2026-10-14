from __future__ import annotations

import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

PROVE_URL = "https://kyre-runless-proof.vercel.app/prove"
PAYLOAD = {
    "task_id": "universal-sports-source-finalization-v1-step8",
    "workstream": "universal-sports-source-finalization-v1",
    "candidate_sha": "aecf8bbf83a61ac31a082856bd83a0267eccd5a1",
    "lease_id": "SCOPE-LEASE-BF74A9DA76E8620374013601",
    "authorization_id": "universal-sports-source-finalization-v1-step8-final-authorization",
    "expected_main_sha": "07e101981f201c87e4bca6b0b58e57c6acede22e",
}

app = FastAPI(title="Step 8 Runless Proof Transport", version="1")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "healthy",
        "service": "step8-runless-proof-transport",
        "candidate_sha": PAYLOAD["candidate_sha"],
        "secret_present": bool(os.environ.get("RUNLESS_PROOF_AUTH_TOKEN", "").strip()),
    }


@app.get("/step8-final-proof-transport")
def step8_final_proof_transport():
    token = os.environ.get("RUNLESS_PROOF_AUTH_TOKEN", "").strip()
    if not token:
        return JSONResponse(
            status_code=503,
            content={"status_code": 503, "body": {"detail": "TRANSPORT_CONFIGURATION_MISSING"}},
        )
    try:
        response = httpx.post(
            PROVE_URL,
            headers={"Authorization": f"Bearer {token}"},
            json=PAYLOAD,
            timeout=240,
        )
        try:
            body = response.json()
        except Exception:
            body = {"detail": "NON_JSON_RESPONSE"}
        status = response.status_code if 100 <= response.status_code <= 599 else 502
        return JSONResponse(
            status_code=status,
            content={"status_code": response.status_code, "body": body},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status_code": 503, "body": {"detail": f"TRANSPORT_UNAVAILABLE:{type(exc).__name__}"}},
        )
