from __future__ import annotations

import json
from urllib import request

CANDIDATE = "5b6c45559f1f7fb50145e97e71c295daa58494e5"
MAIN = "219ed8367207538a909986841e66807e408feede"
LEASE = "SCOPE-LEASE-7A285464DFFA4D4BD9DDB632"
WORKSTREAM = "api2-wnba-pra-history-v1-step1"
TASK_ID = "wnba-pra-history-multisource-v1-step1"
PROOF_PLANE = "https://runless-proof-plane.onrender.com"


def _json_get(url: str) -> dict:
    with request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def test_submit_one_exact_wnba_history_step1_runless_proof():
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
        holder
        for holder in lease.get("holders", [])
        if holder.get("lease_id") == LEASE
        and holder.get("owner_id") == WORKSTREAM
    ]
    assert len(holders) == 1
    assert holders[0]["scope"]["resource_identity"]["candidate_sha"] == CANDIDATE
    assert holders[0]["scope"]["resource_identity"]["main_sha"] == MAIN
    assert (
        holders[0]["scope"]["resource_identity"]["registry_state_hash"]
        == "c724272b73372ececa74be33c8310b2fae7586ce9fae4e6bafe735918587bea3"
    )

    health = _json_get(PROOF_PLANE + "/health")
    assert health.get("mode") == "full", health
    assert health.get("proof_authority") == "enabled", health
    assert health.get("github_actions_enabled") is False, health

    payload = json.dumps(
        {
            "task_id": TASK_ID,
            "workstream": WORKSTREAM,
            "candidate_sha": CANDIDATE,
            "lease_id": LEASE,
            "authorization_id": "kyre-authorized-wnba-step1-final-mile-20261007",
            "expected_main_sha": MAIN,
        }
    ).encode("utf-8")
    req = request.Request(
        PROOF_PLANE + "/prove",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=900) as response:
        result = json.loads(response.read().decode("utf-8"))
    assert result.get("state") == "MERGE_AUTHORIZED", result
    assert result.get("candidate_sha") == CANDIDATE, result
    assert result.get("github_actions_enabled") is False, result
