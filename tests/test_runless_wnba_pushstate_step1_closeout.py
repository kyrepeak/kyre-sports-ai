from __future__ import annotations

import json
from urllib import request

PROOF_PLANE = "https://runless-proof-plane.onrender.com"
PROOF_ID = "wnba-pra-history-multisource-v1-step1-d6dcc11493fcb12f-56640b33135c6e1f"


def test_read_terminal_wnba_history_step1_runless_status():
    with request.urlopen(PROOF_PLANE + "/status/" + PROOF_ID, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    print("WNBA_RUNLESS_STATUS=" + json.dumps(result, sort_keys=True), flush=True)
    assert result.get("state") == "FAILED", result
    assert result.get("candidate_sha") == "d6dcc11493fcb12f1fc45adcb6323699d1ead1ba", result
