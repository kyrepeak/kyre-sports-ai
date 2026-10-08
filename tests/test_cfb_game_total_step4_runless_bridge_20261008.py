from __future__ import annotations

import json
import urllib.error
import urllib.request


CANDIDATE = "51666e746090f73c565da08f61e11ec49c9f96e6"
EXPECTED_MAIN = "8ad570f765daf0884fe6f963f10982b05a414b60"
LEASE_ID = "SCOPE-LEASE-969F634ED2F0B24328861E04"


def test_submit_cfb_game_total_step4_runless_once() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-prediction-market",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": CANDIDATE,
        "lease_id": LEASE_ID,
        "authorization_id": "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-R1",
        "expected_main_sha": EXPECTED_MAIN,
    }
    request = urllib.request.Request(
        "https://runless-proof-plane.onrender.com/prove",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            raw = response.read().decode("utf-8")
            print("STEP4_RUNLESS_HTTP_STATUS=" + str(response.status), flush=True)
            print("STEP4_RUNLESS_RESPONSE=" + raw, flush=True)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        print("STEP4_RUNLESS_HTTP_ERROR=" + str(exc.code), flush=True)
        print("STEP4_RUNLESS_RESPONSE=" + raw, flush=True)
        raise AssertionError(raw) from exc

    data = json.loads(raw)
    assert data.get("candidate_sha") == CANDIDATE
    assert data.get("status") == "MERGE_AUTHORIZED"
    assert data.get("state") == "MERGE_AUTHORIZED"
    assert data.get("github_actions_enabled") is False
