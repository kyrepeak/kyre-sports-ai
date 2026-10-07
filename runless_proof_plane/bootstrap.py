from __future__ import annotations
import os

# MONSTER Task 17 Step 6 — reconcile registry after authorized WNBA merge.
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

reconcile.OLD_MAIN_SHA = "74229f28ea7f2cca1063c2d6b689171646cd1bf8"
reconcile.NEW_MAIN_SHA = "299cc72b502285a1fe714c2e513e363013ad3e90"
reconcile.EXPECTED_REVISION = 176
reconcile.EXPECTED_REGISTRY_HASH = "bd7b9276f05b426b3db8e10f4da0eb81016be11ee8e05c59890dd46c7c8e9c8f"
reconcile.install_startup(app)
