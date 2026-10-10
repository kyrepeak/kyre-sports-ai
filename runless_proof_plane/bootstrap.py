from __future__ import annotations
import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"] = "0"

from .api import app
from . import cfb_game_total_page2_step8_finalizer as finalizer

finalizer.MAIN_SHA = "5d20d527467edf046b7b1705d44b815242565e60"
finalizer.PREMERGE_SHA = "d80ae6267fddd8e5999833158c532be0278a6ed5"
finalizer.PREMERGE_RECEIPT_DIGEST = "5b3db8245cfeef1af93957949ac0604bf1f24f485f5dd6720be12c5a4330953c"
finalizer.LEASE_ID = "SCOPE-LEASE-3C0C0D0741EFC4A4ADB77D64"
finalizer.ARTIFACT_MAP = {
    "app.py": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
    "cfb_game_total_page2_step8_final_runtime_v1.py": "7033e96c9216dceec78ad4030ceaaf87567e6e13",
    "devsystem/cfb_game_total_page2_step8_live_cert_v1.py": "422b54320df359732499344794b4e1887cb14daa",
    "devsystem/execution_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "e1b3bb8bbca106e3520af8fa585871fd89398eec",
    "devsystem/runless_proof_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "22c7bb6e7731cf72e5e24ec36645bd0cd72b9451",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py": "154760d34b4f33aed1efafdf2b026262eb0e332b",
    "tests/test_cfb_game_total_page2_step8_final_v1.py": "9c71f1d2393e4e1cd950fdcc2f6722662c3240bf",
}

_original_freeze = finalizer._freeze_and_reconcile

def _freeze_with_original_app_thaw(client):
    repair_candidate = finalizer.PREMERGE_SHA
    finalizer.PREMERGE_SHA = "09a5efc543e5f8c57f3ac6686bd34e5932ba3685"
    try:
        return _original_freeze(client)
    finally:
        finalizer.PREMERGE_SHA = repair_candidate

finalizer._freeze_and_reconcile = _freeze_with_original_app_thaw

from .cfb_game_total_page2_step8_finalizer_with_browser import install_startup as install_cfb_page2_step8_finalizer

install_cfb_page2_step8_finalizer(app)
