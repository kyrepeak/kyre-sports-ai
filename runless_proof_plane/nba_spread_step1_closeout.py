from __future__ import annotations

import json
import os


def run_and_print(client):
    mode = os.getenv("RPP_NBA_SPREAD_TERMINAL_MODE", "").strip().lower()
    final_main_sha = os.getenv("RPP_NBA_SPREAD_TERMINAL_MAIN_SHA", "").strip().lower()
    if not mode:
        result = {
            "status": "IDLE",
            "decision": "NBA_SPREAD_TERMINAL_MODE_NOT_ARMED",
        }
        print("NBA_SPREAD_STEP1_CLOSEOUT=" + json.dumps(result, sort_keys=True), flush=True)
        return result

    from .nba_spread_step1_terminal_finalization import run_and_print as run_terminal

    result = run_terminal(client, mode, final_main_sha)
    print("NBA_SPREAD_STEP1_CLOSEOUT=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    return result
