from __future__ import annotations
import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"

from .api import app
from .api2_finalization_authority_step6_closeout import install_startup as install_api2_step6_closeout
from .cfb_game_total_page1_v2_step1_prove import install_startup as install_cfb_game_total_page1_step1_prove

install_api2_step6_closeout(app)
install_cfb_game_total_page1_step1_prove(app)
