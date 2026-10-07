from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError

CANDIDATE = "53f5f11a8c13566b8578ebc8dba3aedeaedd59f7"
MAIN = "219ed8367207538a909986841e66807e408feede"
LEASE = "SCOPE-LEASE-58276A81543E070B30D3D29C"
WORKSTREAM = "api2-wnba-pra-history-v1-step1"
TASK_ID = "wnba-pra-history-multisource-v1-step1"
PROOF_PLANE = "https://runless-proof-plane.onrender.com"


def _json_get(url: str) -> dict:
    with request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def test_submit_exact_fixed_wnba_history_step1_runless_proof():
    branch = _json_get(
        "https://api.github.com/repos/kyrepeak/kyre-sports-ai/branches/"
        "api2-wnba-pra-history-v1-step1-multisource-r1"
    )
    assert branch["commit"]["sha"] == CANDIDATE
    main = _json_get("https://api.github.com/repos/kyrepeak/kyre-sports-ai/branches/main")
    assert main["commit"]["sha"] == MAIN
    lease = _json_get(
        "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
        "monster-scope-aware-execution-leases/"
        "devsystem/scope_aware_execution_lease_state_v1.json"
    )
    holders = [
        h for h in lease.get("holders", [])
        if h.get("lease_id") == LEASE and h.get("owner_id") == WORKSTREAM
    ]
    assert len(holders) == 1
    identity = holders[0]["scope"]["resource_identity"]
    assert identity["candidate_sha"] == CANDIDATE
    assert identity["main_sha"] == MAIN

    health = _json_get(PROOF_PLANE + "/health")
    assert health.get("mode") == "full", health
    assert health.get("proof_authority") == "enabled", health
    assert health.get("github_actions_enabled") is False, health

    payload = json.dumps({
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": CANDIDATE,
        "lease_id": LEASE,
        "authorization_id": "kyre-authorized-wnba-step1-final4-proof-20261007",
        "expected_main_sha": MAIN,
    }).encode("utf-8")
    req = request.Request(
        PROOF_PLANE + "/prove",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=900) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise AssertionError(f"RUNLESS_HTTP_{exc.code}:{detail}") from exc

    assert result.get("state") == "MERGE_AUTHORIZED", json.dumps(result, sort_keys=True)
    assert result.get("candidate_sha") == CANDIDATE, result
    assert result.get("receipt_digest"), result
    assert result.get("github_actions_enabled") is False, result
