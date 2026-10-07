from __future__ import annotations

import json
from urllib import request

PROOF_PLANE = "https://runless-proof-plane.onrender.com"
PROOF_ID = "wnba-pra-history-multisource-v1-step1-d6dcc11493fcb12f-56640b33135c6e1f"


def test_emit_terminal_wnba_history_step1_runless_status():
    with request.urlopen(PROOF_PLANE + "/status/" + PROOF_ID, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    assert result.get("state") == "MERGE_AUTHORIZED", json.dumps(result, sort_keys=True)
