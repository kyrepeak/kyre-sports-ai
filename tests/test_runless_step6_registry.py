"""One-shot Runless bridge for CFB Game Total Page 1 V2 Step-4 public repair.

This executor submits exactly one /prove request for the exact candidate/lease
below. It is infrastructure-only and grants no product authority itself.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROOF_URL = "https://runless-proof-plane.onrender.com/prove"
CANDIDATE_SHA = "73a70ec8882e3e1229ee1d069e78e74735ec23c7"
EXPECTED_MAIN_SHA = "81eab31f78e65728a9b55a5ac578706fd6971bec"
LEASE_ID = "SCOPE-LEASE-4B8F762C168F6B609CA466FC"


def test_cfb_game_total_step4_public_repair_exact_head_runless() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-public-repair",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "authorization_id": "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-PUBLIC-REPAIR-R3",
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
