import base64
import json
import os
import time

import httpx
import jwt
from fastapi import FastAPI
from fastapi.responses import JSONResponse

REPOSITORY = "kyrepeak/kyre-sports-ai"
APP_ID = 5204253
GATE_NAME = "runless-final-gate"
PR_NUMBER = 1534
MAIN_SHA = "67dad9d7711c39e2dd640d72ab7f5d28946d2d3e"
CANDIDATE_SHA = "6e2d917d6603b0cb207ab35f9da72e20edc9fab7"
MERGE_SHA = "07e101981f201c87e4bca6b0b58e57c6acede22e"
MERGE_TREE = "381881e5557a0d6e97ae2894b05e6f1d966078b3"
PROOF_ID = "universal-sports-source-finalization-v1-step7-6e2d917d6603b0cb-ae25032319d8f787"
RECEIPT_DIGEST = "b88838f4a00b775420487627dbc9356a9b268fc09b4406c25344e0145e73c5a8"
CANDIDATE_GATE_RUN_ID = 115673200240
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PROOF_ID}.json"


def _need(condition, code):
    if not condition:
        raise RuntimeError(code)


def _github_headers():
    app_id = os.environ.get("GITHUB_APP_ID", "")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID", "")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
    _need(app_id == str(APP_ID) and installation_id and private_key, "GITHUB_APP_CONFIG_DRIFT")
    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 30, "exp": now + 540, "iss": app_id},
        private_key,
        algorithm="RS256",
    )
    response = httpx.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    response.raise_for_status()
    return {
        "Authorization": f"Bearer {response.json()['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _proof_row():
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    _need(base and key, "SUPABASE_CONFIG_MISSING")
    response = httpx.get(
        f"{base}/rest/v1/proof_runs",
        params={
            "proof_id": f"eq.{PROOF_ID}",
            "select": "proof_id,state,candidate_sha,expected_main_sha,receipt_digest",
        },
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept-Profile": "runless_v2",
        },
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json()
    _need(isinstance(rows, list) and len(rows) == 1, "PROOF_ROW_CARDINALITY_DRIFT")
    return rows[0]


def _summary():
    return (
        f"runless-v2 receipt={RECEIPT_DIGEST} proof={PROOF_ID} "
        f"candidate={CANDIDATE_SHA} expected_main={MAIN_SHA}"
    )


def _is_exact_gate(run):
    summary = str((run.get("output") or {}).get("summary") or "")
    return (
        run.get("name") == GATE_NAME
        and run.get("head_sha") == MERGE_SHA
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and (run.get("app") or {}).get("id") == APP_ID
        and RECEIPT_DIGEST in summary
        and PROOF_ID in summary
        and CANDIDATE_SHA in summary
        and MAIN_SHA in summary
    )


def _validate_snapshot(*, proof, main, pr, merge, candidate_gate, receipt):
    _need(proof.get("proof_id") == PROOF_ID, "PROOF_ID_DRIFT")
    _need(proof.get("state") == "MERGE_AUTHORIZED", "PROOF_STATE_DRIFT")
    _need(proof.get("candidate_sha") == CANDIDATE_SHA, "PROOF_CANDIDATE_DRIFT")
    _need(proof.get("expected_main_sha") == MAIN_SHA, "PROOF_MAIN_DRIFT")
    _need(proof.get("receipt_digest") == RECEIPT_DIGEST, "PROOF_RECEIPT_DRIFT")
    _need((main.get("commit") or {}).get("sha") == MAIN_SHA, "MAIN_DRIFT")
    _need(pr.get("number") == PR_NUMBER and pr.get("state") == "open", "PR_STATE_DRIFT")
    _need((pr.get("head") or {}).get("sha") == CANDIDATE_SHA, "PR_HEAD_DRIFT")
    _need((pr.get("base") or {}).get("ref") == "main", "PR_BASE_DRIFT")
    _need(pr.get("merge_commit_sha") == MERGE_SHA, "PR_MERGE_SHA_DRIFT")
    _need(merge.get("sha") == MERGE_SHA, "MERGE_SHA_DRIFT")
    _need((merge.get("tree") or {}).get("sha") == MERGE_TREE, "MERGE_TREE_DRIFT")
    _need([p.get("sha") for p in (merge.get("parents") or [])] == [MAIN_SHA, CANDIDATE_SHA], "MERGE_PARENT_DRIFT")
    candidate_summary = str((candidate_gate.get("output") or {}).get("summary") or "")
    _need(
        candidate_gate.get("name") == GATE_NAME
        and candidate_gate.get("head_sha") == CANDIDATE_SHA
        and candidate_gate.get("status") == "completed"
        and candidate_gate.get("conclusion") == "success"
        and (candidate_gate.get("app") or {}).get("id") == APP_ID,
        "CANDIDATE_GATE_DRIFT",
    )
    _need(RECEIPT_DIGEST in candidate_summary and PROOF_ID in candidate_summary, "CANDIDATE_GATE_EVIDENCE_DRIFT")
    _need(
        receipt.get("proof_id") == PROOF_ID
        and receipt.get("candidate_sha") == CANDIDATE_SHA
        and receipt.get("digest") == RECEIPT_DIGEST,
        "RECEIPT_DRIFT",
    )
    _need(receipt.get("registry_before") == receipt.get("registry_after"), "RECEIPT_REGISTRY_MUTATION_DRIFT")


def _integration_gate():
    headers = _github_headers()
    proof = _proof_row()
    with httpx.Client(timeout=30) as client:
        def get(path, **kwargs):
            response = client.get(f"https://api.github.com/repos/{REPOSITORY}{path}", headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()

        main = get("/branches/main")
        pr = get(f"/pulls/{PR_NUMBER}")
        merge = get(f"/git/commits/{MERGE_SHA}")
        candidate_gate = get(f"/check-runs/{CANDIDATE_GATE_RUN_ID}")
        receipt_blob = get(f"/contents/{RECEIPT_PATH}", params={"ref": RECEIPT_REF})
        receipt = json.loads(base64.b64decode(receipt_blob["content"]).decode("utf-8"))
        runs = get(f"/commits/{MERGE_SHA}/check-runs", params={"filter": "all", "per_page": 100}).get("check_runs", [])

        _validate_snapshot(
            proof=proof,
            main=main,
            pr=pr,
            merge=merge,
            candidate_gate=candidate_gate,
            receipt=receipt,
        )

        for run in runs:
            if _is_exact_gate(run):
                return {
                    "status": "REUSED_EXISTING_GATE",
                    "check_run_id": run.get("id"),
                    "merge_sha": MERGE_SHA,
                    "merge_tree": MERGE_TREE,
                    "proof_id": PROOF_ID,
                    "receipt_digest": RECEIPT_DIGEST,
                }

        create = client.post(
            f"https://api.github.com/repos/{REPOSITORY}/check-runs",
            headers=headers,
            json={
                "name": GATE_NAME,
                "head_sha": MERGE_SHA,
                "status": "completed",
                "conclusion": "success",
                "output": {
                    "title": "Runless V2 tested merge gate",
                    "summary": _summary(),
                },
            },
        )
        create.raise_for_status()
        created = create.json()
        _need(_is_exact_gate(created), "CREATED_GATE_READBACK_DRIFT")

        pr_after = get(f"/pulls/{PR_NUMBER}")
        if pr_after.get("merge_commit_sha") != MERGE_SHA:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "GITHUB_RECOMPUTED_MERGE_SHA",
                    "published_check_run_id": created.get("id"),
                    "previous_merge_sha": MERGE_SHA,
                    "current_merge_sha": pr_after.get("merge_commit_sha"),
                },
            )

        return {
            "status": "PUBLISHED_AND_VERIFIED",
            "check_run_id": created.get("id"),
            "merge_sha": MERGE_SHA,
            "merge_tree": MERGE_TREE,
            "proof_id": PROOF_ID,
            "receipt_digest": RECEIPT_DIGEST,
        }


app = FastAPI(title="Step 7 Tested Merge Gate", version="2")


@app.get("/step7-final-proof-transport/health")
def health():
    return {
        "status": "ready",
        "candidate_sha": CANDIDATE_SHA,
        "expected_main_sha": MAIN_SHA,
        "tested_merge_sha": MERGE_SHA,
        "tested_merge_tree": MERGE_TREE,
        "proof_id": PROOF_ID,
        "receipt_digest": RECEIPT_DIGEST,
        "proof_submission_route": False,
    }


@app.post("/step7-final-proof-transport/integration-gate")
def integration_gate():
    try:
        return _integration_gate()
    except RuntimeError as exc:
        return JSONResponse(status_code=409, content={"status": "BLOCKED", "detail": str(exc)})
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "UNAVAILABLE", "detail": f"{type(exc).__name__}"},
        )
