from __future__ import annotations
import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"

from .api import app
from .cfb_game_total_page1_v2_step3_closeout import install_startup as install_step3_startup
from .cfb_game_total_page1_v2_step4_closeout import install_startup as install_step4_startup

install_step3_startup(app)
install_step4_startup(app)
