from __future__ import annotations

import json
import urllib.error
import urllib.request


CANDIDATE = "6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b"
EXPECTED_MAIN = "8ad570f765daf0884fe6f963f10982b05a414b60"
LEASE_ID = "SCOPE-LEASE-2FEF82C73C72C46AE97410C9"
AUTHORIZATION_ID = "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-R2-6CE49C"


def test_submit_cfb_game_total_step4_runless_once() -> None:
    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-prediction-market",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": CANDIDATE,
        "lease_id": LEASE_ID,
        "authorization_id": AUTHORIZATION_ID,
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
        return
    except Exception as exc:
        print("STEP4_RUNLESS_TRANSPORT_ERROR=" + type(exc).__name__ + ":" + str(exc), flush=True)
        return

    data = json.loads(raw)
    print("STEP4_RUNLESS_STATE=" + str(data.get("state")), flush=True)
    print("STEP4_RUNLESS_PROOF_ID=" + str(data.get("proof_id")), flush=True)
    print("STEP4_RUNLESS_RECEIPT_DIGEST=" + str(data.get("receipt_digest")), flush=True)
