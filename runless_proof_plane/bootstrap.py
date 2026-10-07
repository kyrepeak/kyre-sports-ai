from __future__ import annotations
import os

# MONSTER Task 17 Step 3 — atomic post-merge reuse + freeze closeout at canonical registry 171.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from . import task17_step3_atomic_closeout as closeout

closeout.EXPECTED_REGISTRY_REVISION = 171
closeout.EXPECTED_REGISTRY_HASH = "b94df998b0910a1a03cf25a7dd69ce6d191dcbd4c1b3f6ea4cfaadc7db4125e3"
closeout.install_startup(app)
