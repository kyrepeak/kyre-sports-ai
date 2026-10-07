from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError

CANDIDATE = "778d7bf1eb29107e32bd49cacc1035954ac47db4"
MAIN = "aba567ca13d1a01d9ef783efcff47b784b414a5c"
LEASE = "SCOPE-LEASE-58276A81543E070B30D3D29C"
WORKSTREAM = "api2-wnba-pra-history-v1-step1"
TASK_ID = "wnba-pra-history-multisource-v1-step1"
BRANCH = "api2-wnba-step1-bref-fallback-r1"
PROOF_PLANE = "https://runless-proof-plane.onrender.com"


def _json_get(url: str) -> dict:
    with request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def test_submit_wnba_step1_bref_fallback_tdd_red():
    branch = _json_get("https://api.github.com/repos/kyrepeak/kyre-sports-ai/branches/" + BRANCH)
    assert branch["commit"]["sha"] == CANDIDATE
    main = _json_get("https://api.github.com/repos/kyrepeak/kyre-sports-ai/branches/main")
    assert main["commit"]["sha"] == MAIN
    health = _json_get(PROOF_PLANE + "/health")
    assert health.get("mode") == "full", health
    assert health.get("proof_authority") == "enabled", health
    assert health.get("github_actions_enabled") is False, health
    payload = json.dumps({
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": CANDIDATE,
        "lease_id": LEASE,
        "authorization_id": "kyre-authorized-wnba-step1-bref-fallback-tdd-red-20261007",
        "expected_main_sha": MAIN,
    }).encode("utf-8")
    req = request.Request(PROOF_PLANE + "/prove", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=900) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise AssertionError(f"RUNLESS_HTTP_{exc.code}:{detail}") from exc
    assert result.get("state") == "FAILED", json.dumps(result, sort_keys=True)
    assert result.get("candidate_sha") == CANDIDATE, result
