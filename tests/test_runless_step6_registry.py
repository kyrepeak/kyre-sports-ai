"""One-shot Runless bridge for API2 CFB Step-4 final side-market convergence.

Submits exactly one /prove request for the immutable product candidate and its
Step-2A scope lease. Infrastructure-only; retire to the inert shim immediately
after the terminal proof result.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROOF_URL = "https://runless-proof-plane.onrender.com/prove"
CANDIDATE_SHA = "3d1d6a0a7a0be69e252aa5168887f21a72baf6d4"
EXPECTED_MAIN_SHA = "2a8039a5f2dc9980711674e92b6d7ec35ab5df29"
LEASE_ID = "SCOPE-LEASE-BDBD39318EEAC420E02FCB03"
AUTHORIZATION_ID = "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-FINAL-SIDE-MARKET-R1"


def test_cfb_step4_final_side_market_exact_head_runless() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-final-side-market",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "authorization_id": AUTHORIZATION_ID,
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
