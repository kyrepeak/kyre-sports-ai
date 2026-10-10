import json
import urllib.error
import urllib.request


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            body = response.read().decode()
            print(f"ULSB_STEP2_DIAG {url} status={response.status} body={body}", flush=True)
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"ULSB_STEP2_DIAG {url} status={exc.code} body={body}", flush=True)
        raise


def test_ulsb_step2_runless_health_and_github_auth():
    health_status, health = _get("https://runless-proof-plane.onrender.com/health")
    github_status, github = _get("https://runless-proof-plane.onrender.com/diagnostics/github")
    assert health_status == 200
    assert health.get("mode") == "full"
    assert health.get("proof_authority") == "enabled"
    assert github_status == 200
    assert github.get("status") == "GREEN"
