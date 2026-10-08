"""One-shot Runless bridge for CFB Step-4 exact-event side-market repair R2.

Submits exactly one /prove request for the immutable no-thaw adapter candidate
and its product Step-2A lease. This executor bridge is infrastructure-only and
must return to the inert shim after the terminal proof result.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROOF_URL = "https://runless-proof-plane.onrender.com/prove"
CANDIDATE_SHA = "627a3307ce02fb40ab8f1f695445ea7ac9db6231"
EXPECTED_MAIN_SHA = "38698b8ed33b96547af855780953b414a6d34131"
LEASE_ID = "SCOPE-LEASE-77ECCF25CBEC1C6437C81778"


def test_cfb_step4_event_page_side_market_exact_head_runless_r2() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-event-page-side-market-repair",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "authorization_id": "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-EVENT-PAGE-SIDE-MARKET-R2",
        "expected_main_sha": EXPECTED_MAIN_SHA,
    }
    request = Request(
        PROOF_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"Runless HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise AssertionError(f"Runless transport failure: {exc}") from exc

    result = json.loads(body)
    print("RUNLESS_PROOF_RESULT=" + json.dumps(result, sort_keys=True))
    assert result.get("candidate_sha") == CANDIDATE_SHA
    assert result.get("state") == "MERGE_AUTHORIZED"
    assert result.get("status") == "MERGE_AUTHORIZED"
    assert result.get("github_actions_enabled") is False
    assert result.get("receipt_digest")
