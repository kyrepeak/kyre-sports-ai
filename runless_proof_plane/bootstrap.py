from __future__ import annotations
import os

# WNBA pushState Repair V1 Step 4 final mission closeout.
# All prior one-shot WNBA publication/freeze paths remain disarmed. This
# startup certifies the already-frozen Steps 1-3 and writes only the final
# mission freeze token; product/runtime code is read-only.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from .wnba_pushstate_step4_mission_closeout import install_startup_closeout

install_startup_closeout(app)
