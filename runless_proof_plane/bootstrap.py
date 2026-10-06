from __future__ import annotations
import os

# WNBA Data Completeness Repair V1 Step 1 exact-head candidate gate.
# Previous one-shot WNBA publication/freeze paths are disarmed; this startup
# verifies only PR #1421 source/ID truth and publishes its Runless gate.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from .wnba_data_step1_source_id_gate import install_startup_gate

install_startup_gate(app)
