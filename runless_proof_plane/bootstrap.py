from __future__ import annotations
import os

# WNBA pushState Repair V1 Step 1 final freeze/read-back.
# Candidate and merged-main check publication are disarmed; only the narrow
# CAS-protected four-artifact freeze is armed.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "1"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_SHA"] = "896bd5f78ef6b6f7d7084413cc1e35ac6489fdc2"

from .api import app
from .wnba_pushstate_step1_closeout import install_startup_gate

install_startup_gate(app)
