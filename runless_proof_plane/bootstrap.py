from __future__ import annotations
import os

# WNBA pushState Repair V1 Step 1 merged-main closeout.
# Candidate publication and all prior one-shot mutation hooks are disarmed.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "1"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_SHA"] = "896bd5f78ef6b6f7d7084413cc1e35ac6489fdc2"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_SHA"] = "ab3fdb3e544500366618bea71bd29976307f0c9f"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_BASE_SHA"] = "f8fe7aef9f9519750aaa9053716d2059c9bbdb83"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_RECEIPT"] = "6c9a1d3e0525afb80ca8efe30f4d7c297f256c67c878702affc5fa99af91c914"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_WORKER_SERVICE_ID"] = "srv-db2l7vad0e5s73bhc8pg"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_WORKER_DEPLOY_ID"] = "dep-db2l7vqd0e5s73bhcbe0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_TEST_RESULT"] = "1 passed in 1.89s"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_CERT_TOKEN"] = "RUNLESS_WNBA_PUSHSTATE_STEP1_GREEN"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_OWNER"] = "_pin_deep_wnba_shell_route"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FEEDBACK_LOOP_PROVEN"] = "1"

from .api import app
from .wnba_pushstate_step1_closeout import install_startup_gate

install_startup_gate(app)
