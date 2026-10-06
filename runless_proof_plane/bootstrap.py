from __future__ import annotations
import os

# WNBA Data Completeness Repair V1 Step 1 merged-main closeout.
# Previous one-shot WNBA paths are disarmed; this startup verifies the exact
# merged main, publishes its Runless gate, and atomically freezes Step 1 only.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from .wnba_data_step1_closeout import install_startup_closeout

install_startup_closeout(app)
