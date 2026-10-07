from __future__ import annotations
import os

# MONSTER Task 17 Step 6 — authoritative RED proof through Runless.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from . import task17_step3_candidate_prove as prove

prove.TASK_ID = "runless-task17-step6-tail-sla-telemetry"
prove.WORKSTREAM = "runless-task17-step6"
prove.CANDIDATE_SHA = "38186c1a71d3ffbaf17b4c4babc69f98c8fd23c4"
prove.EXPECTED_MAIN_SHA = "74229f28ea7f2cca1063c2d6b689171646cd1bf8"
prove.LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
prove.AUTHORIZATION_ID = "AUTH-RUNLESS-TASK17-STEP6-RED-R1"
prove.install_startup(app)
