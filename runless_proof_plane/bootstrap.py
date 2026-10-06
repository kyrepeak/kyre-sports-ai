from __future__ import annotations
import os

# Runless full proof authority for the WNBA pushState Repair V1 Step 1 closeout.
# This branch is the mutable Runless control plane, not product main.
# All prior one-shot WNBA Step-9 mutation hooks are explicitly disarmed.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"

from .api import app
from .wnba_pushstate_step1_closeout import install_startup_gate

install_startup_gate(app)
