import os
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

PROVE_URL = "https://kyre-runless-proof.vercel.app/prove"
REPOSITORY = "kyrepeak/kyre-sports-ai"
GATE_RUN_ID = 115673200240
TASK_ID = "universal-sports-source-finalization-v1-step7"
WORKSTREAM = "universal-sports-source-finalization-v1"
CANDIDATE_SHA = "6e2d917d6603b0cb207ab35f9da72e20edc9fab7"
LEASE_ID = "SCOPE-LEASE-A70614DFEA642E4A5501A845"
AUTHORIZATION_ID = "universal-sports-source-finalization-v1-step7-final-authorization"
EXPECTED_MAIN_SHA = "67dad9d7711c39e2dd640d72ab7f5d28946d2d3e"


def build_payload():
    return {
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "authorization_id": AUTHORIZATION_ID,
        "expected_main_sha": EXPECTED_MAIN_SHA,
    }


def submit_proof(token, *, post=None):
    if not token:
        raise RuntimeError("RUNLESS_PROOF_AUTH_TOKEN_REQUIRED")
    if post is None:
        import httpx
        post = httpx.post
    response = post(
        PROVE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json=build_payload(),
        timeout=240,
    )
    try:
        body = response.json()
    except Exception:
        body = {"detail": "NON_JSON_RESPONSE"}
    return {"status_code": int(response.status_code), "body": body}


def sanitize_gate(check, commit_runs):
    return {
        "check_run": {
            "id": check.get("id"),
            "name": check.get("name"),
            "head_sha": check.get("head_sha"),
            "status": check.get("status"),
            "conclusion": check.get("conclusion"),
            "app": {
                "id": (check.get("app") or {}).get("id"),
                "slug": (check.get("app") or {}).get("slug"),
            },
            "pull_requests": [
                {
                    "number": item.get("number"),
                    "head_sha": (item.get("head") or {}).get("sha"),
                    "base_sha": (item.get("base") or {}).get("sha"),
                }
                for item in (check.get("pull_requests") or [])
            ],
        },
        "matching_commit_runs": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "head_sha": item.get("head_sha"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "app_id": (item.get("app") or {}).get("id"),
                "pull_requests": [pr.get("number") for pr in (item.get("pull_requests") or [])],
            }
            for item in commit_runs
            if item.get("name") == "runless-final-gate"
        ],
    }


def github_gate_snapshot():
    import httpx
    import jwt

    app_id = os.environ.get("GITHUB_APP_ID", "")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID", "")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
    if not app_id or not installation_id or not private_key:
        raise RuntimeError("GITHUB_APP_CONFIG_REQUIRED")

    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 30, "exp": now + 540, "iss": app_id},
        private_key,
        algorithm="RS256",
    )
    app_headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30) as client:
        token_response = client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers=app_headers,
        )
        token_response.raise_for_status()
        installation_token = token_response.json()["token"]
        headers = {
            "Authorization": f"Bearer {installation_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        check_response = client.get(
            f"https://api.github.com/repos/{REPOSITORY}/check-runs/{GATE_RUN_ID}",
            headers=headers,
        )
        check_response.raise_for_status()
        runs_response = client.get(
            f"https://api.github.com/repos/{REPOSITORY}/commits/{CANDIDATE_SHA}/check-runs?filter=all&per_page=100",
            headers=headers,
        )
        runs_response.raise_for_status()
        return sanitize_gate(
            check_response.json(),
            runs_response.json().get("check_runs", []),
        )


app = FastAPI(title="Step 7 Runless Proof Transport", version="3")


@app.get("/step7-final-proof-transport/health")
def step7_final_proof_transport_health():
    return {
        "status": "ready",
        "task_id": TASK_ID,
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "authorization_id": AUTHORIZATION_ID,
        "expected_main_sha": EXPECTED_MAIN_SHA,
    }


@app.get("/step7-final-proof-transport/gate")
def step7_final_proof_transport_gate():
    try:
        return github_gate_snapshot()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": f"GATE_INSPECTION_UNAVAILABLE:{type(exc).__name__}"},
        )


@app.post("/step7-final-proof-transport")
def step7_final_proof_transport():
    try:
        result = submit_proof(os.environ.get("RUNLESS_PROOF_AUTH_TOKEN", ""))
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={"status_code": 503, "body": {"detail": "TRANSPORT_CONFIGURATION_MISSING"}},
        )
    status_code = result["status_code"]
    if status_code < 100 or status_code > 599:
        status_code = 502
    return JSONResponse(status_code=status_code, content=result)
