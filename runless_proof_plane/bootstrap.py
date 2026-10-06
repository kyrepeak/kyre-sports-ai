from __future__ import annotations
import os

# WNBA PRA Repair V1 Step 9 final closeout control.
# This branch is the mutable Runless control plane, not product main.
# Force the already-configured GitHub App service into full proof mode for the
# single idempotent Step-9 freeze/read-back operation. Stale activation and all
# unrelated startup mutation hooks remain disabled.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "1"
os.environ["RPP_WNBA_STEP9_FREEZE_MERGED_SHA"] = "f8fe7aef9f9519750aaa9053716d2059c9bbdb83"
os.environ["RPP_WNBA_STEP9_FREEZE_TOKEN"] = "WNBA_PRA_REPAIR_V1_STEP9_FROZEN"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"

from .api import app
