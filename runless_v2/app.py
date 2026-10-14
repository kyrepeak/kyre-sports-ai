from __future__ import annotations

import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

PROVE_URL = "https://kyre-runless-proof.vercel.app/prove"
PAYLOAD = {
    "task_id": "nba-spread-step4-most-bet-feature-v1",
    "workstream": "nba-spread-two-page-v1",
    "candidate_sha": "5b66e5ecfdc5e7f672367109f880d93e93f863a5",
    "lease_id": "SCOPE-LEASE-EADEC1FD7033345BC5EAE73F",
    "authorization_id": "nba-spread-step4-final-authorization-v2",
    "expected_main_sha": "5aae6cfb46aabfa360b6aadff87f85385fb31946",
}

app = FastAPI(title="NBA Spread Step 4 Runless Proof Transport", version="1")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "healthy",
        "service": "nba-spread-step4-runless-proof-transport",
        "candidate_sha": PAYLOAD["candidate_sha"],
        "secret_present": bool(os.environ.get("RUNLESS_PROOF_AUTH_TOKEN", "").strip()),
    }


@app.get("/step4-final-proof-transport")
def step4_final_proof_transport():
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
