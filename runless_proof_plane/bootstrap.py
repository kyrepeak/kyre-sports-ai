from __future__ import annotations
import json
import os

# WNBA Data Completeness Repair V1 Step 2 live hydration candidate gate.
# Exact-head proof only: no product mutation, merge, registry write, or freeze.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from .wnba_data_step2_live_hydration_gate import install_startup_gate

install_startup_gate(app)

@app.on_event("startup")
def _report_wnba_data_step2_live_hydration_gate():
    print(
        "WNBA_DATA_STEP2_LIVE_HYDRATION_GATE_STATUS="
        + json.dumps(app.state.wnba_data_step2_live_hydration_gate, sort_keys=True),
        flush=True,
    )
