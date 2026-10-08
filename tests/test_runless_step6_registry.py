"""One-shot Runless bridge for CFB Step-4 FanDuel side-market completeness.

Submits exactly one /prove request for the exact candidate and product Step-2A
lease. This executor bridge is infrastructure-only and grants no product
authority itself.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROOF_URL = "https://runless-proof-plane.onrender.com/prove"
CANDIDATE_SHA = "2e5c78f058384f6ba62cca6cd1ff07fc0ce72211"
EXPECTED_MAIN_SHA = "40b3049f2089833dacafda8c24086b9ef11a2cbd"
LEASE_ID = "SCOPE-LEASE-83D80ED6BEE45734F674A82C"


def test_cfb_step4_side_market_completeness_exact_head_runless() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-side-market-completeness",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "authorization_id": "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-SIDE-MARKET-COMPLETENESS-R1",
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
