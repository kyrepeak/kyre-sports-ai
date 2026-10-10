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

finalizer.MAIN_SHA = "3065e960d3363bf6f3d70252c906b9590e7293e9"
finalizer.PREMERGE_SHA = "764e11f1f69630e4326ddfbbbc070e0840001780"
finalizer.PREMERGE_RECEIPT_DIGEST = "f12323f16847973965bf6e380e70f12cda1d68ca99af8c24e754380eb457c46e"
finalizer.LEASE_ID = "SCOPE-LEASE-779AF9201DBFD42F72EF29FC"
finalizer.ARTIFACT_MAP = {
    "app.py": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
    "cfb_game_total_page2_step8_final_runtime_v1.py": "bf3141e958826cf93cb39435e7ea809865f92a29",
    "devsystem/cfb_game_total_page2_step8_live_cert_v1.py": "422b54320df359732499344794b4e1887cb14daa",
    "devsystem/execution_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "e1b3bb8bbca106e3520af8fa585871fd89398eec",
    "devsystem/runless_proof_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "22c7bb6e7731cf72e5e24ec36645bd0cd72b9451",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py": "154760d34b4f33aed1efafdf2b026262eb0e332b",
    "tests/test_cfb_game_total_page2_step8_final_v1.py": "9b794cbdeaaa8f6fcbdf276c8c907835408a30e1",
}

_original_freeze = finalizer._freeze_and_reconcile

def _freeze_with_original_app_thaw(client):
    repaired_candidate = finalizer.PREMERGE_SHA
    finalizer.PREMERGE_SHA = "09a5efc543e5f8c57f3ac6686bd34e5932ba3685"
    try:
        return _original_freeze(client)
    finally:
        finalizer.PREMERGE_SHA = repaired_candidate

finalizer._freeze_and_reconcile = _freeze_with_original_app_thaw

from .cfb_game_total_page2_step8_finalizer_with_browser import install_startup as install_cfb_page2_step8_finalizer

install_cfb_page2_step8_finalizer(app)
