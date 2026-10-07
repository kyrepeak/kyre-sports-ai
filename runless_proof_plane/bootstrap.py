from __future__ import annotations
import os

# WNBA Data Completeness Repair V1 Step 2 merged-main closeout.
# Candidate gate has already passed. This startup verifies exact merged main,
# publishes one Runless merged-main gate, and atomically freezes Step 2 only.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from .wnba_data_step2_closeout import install_startup_closeout

install_startup_closeout(app)
