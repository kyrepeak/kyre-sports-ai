import json
import urllib.error
import urllib.request


def test_submit_ulsb_step2_runless_proof_generation2_once():
    payload = {
        "task_id": "universal-live-status-board-v1-step2-authoritative-chat-ownership",
        "workstream": "universal-live-status-board-v1",
        "candidate_sha": "374dbb2a4702a6a5f87b977c8822db93e8481897",
        "lease_id": "SCOPE-LEASE-E5C0D43F1ACD5F3F0E9E522E",
        "authorization_id": "AUTH-UNIVERSAL-LIVE-STATUS-BOARD-V1-STEP2-R2",
        "expected_main_sha": "20f23cae36b70ba702657546296560c5432203dc",
    }
    request = urllib.request.Request(
        "https://runless-proof-plane.onrender.com/prove",
        data=json.dumps(payload, sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = response.read().decode("utf-8", "replace")
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = int(exc.code)
    print(f"ULSB_STEP2_RUNLESS_HTTP={status}", flush=True)
    print("ULSB_STEP2_RUNLESS_BODY=" + body, flush=True)
    assert status == 200, body
