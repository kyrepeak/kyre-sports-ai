from __future__ import annotations
import os

# MONSTER Task 17 Step 4 — authoritative RED proof through Runless.
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

prove.TASK_ID = "runless-task17-step4-event-driven-resume"
prove.WORKSTREAM = "runless-task17-step4"
prove.CANDIDATE_SHA = "aea7f674e5a98a315802f5b6b519a85134710ee8"
prove.EXPECTED_MAIN_SHA = "7e8dfad79fb2745439ae1985de4d392b4e90f451"
prove.LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
prove.AUTHORIZATION_ID = "AUTH-RUNLESS-TASK17-STEP4-RED-R1"
prove.install_startup(app)
