from __future__ import annotations
import os

# MONSTER Task 17 Step 5 — authoritative RED proof through Runless.
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

prove.TASK_ID = "runless-task17-step5-atomic-closeout"
prove.WORKSTREAM = "runless-task17-step5"
prove.CANDIDATE_SHA = "39eababb98b157fdb6046aa58f8f6ee88f3c053e"
prove.EXPECTED_MAIN_SHA = "0f54693bea39146747b98cbb7d15c0a4c778f0c8"
prove.LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
prove.AUTHORIZATION_ID = "AUTH-RUNLESS-TASK17-STEP5-RED-R1"
prove.install_startup(app)
