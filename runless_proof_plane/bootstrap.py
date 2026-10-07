from __future__ import annotations
import os

# Runless Final-Mile Convergence Accelerator V1 — Task 17 Step 1 proof authority.
# The exact thaw was already granted and is intentionally NOT replayed here.
os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START"] = "0"
os.environ["RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START"] = "0"

from .api import app
from .task17_step1_registry_recovery import install_startup as install_registry_recovery
from .task17_step1_proof import install_startup as install_proof

# Material state repair must happen before the one Runless proof attempt.
install_registry_recovery(app)
install_proof(app)
