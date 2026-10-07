from __future__ import annotations
import os

# MONSTER Task 17 Step 4 — reconcile frozen-registry identity after authorized WNBA merge.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from . import task17_step3_registry_reconcile as reconcile

reconcile.OLD_MAIN_SHA = "d2e2b45398e4a22c1e020a5fb5aca7b10e1debbb"
reconcile.NEW_MAIN_SHA = "7e8dfad79fb2745439ae1985de4d392b4e90f451"
reconcile.EXPECTED_REVISION = 172
reconcile.EXPECTED_REGISTRY_HASH = "bfd5e53afc7ad90bf77f542416336b0c1682f6a9385f457f15a78d364b7732c7"
reconcile.install_startup(app)
