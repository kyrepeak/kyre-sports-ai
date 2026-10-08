"""One-shot Runless bridge for API2 CFB Page1 V2 Step5 certification R3."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROOF_URL = "https://runless-proof-plane.onrender.com/prove"
CANDIDATE_SHA = "0d5ec9bd4ec10562350693b9fac23cb95541f337"
EXPECTED_MAIN_SHA = "53c4bf0aa194befe56934d476f0f1a1a22d3d40d"
LEASE_ID = "SCOPE-LEASE-C52D38FE9D8B0EB537998E00"
AUTHORIZATION_ID = "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP5-PACE-POSSESSIONS-R3"


def test_cfb_step5_pace_exact_head_runless_r3() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step5-pace-possessions",
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
