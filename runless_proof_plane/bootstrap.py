from __future__ import annotations
import os

# MONSTER Task 17 Step 6 — exact GREEN candidate proof through Runless.
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
prove.CANDIDATE_SHA = "4a7bf1142de2d9f2527003395c643013ce67c243"
prove.EXPECTED_MAIN_SHA = "299cc72b502285a1fe714c2e513e363013ad3e90"
prove.LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
prove.AUTHORIZATION_ID = "AUTH-RUNLESS-TASK17-STEP6-GREEN-R1"
prove.install_startup(app)
