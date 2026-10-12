from __future__ import annotations

import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_PREMERGE_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC_ON_START"] = "0"

from .api import app
from .cfb_step8_terminal_postmerge_registry_rebind_v1 import install_startup
from .nba_spread_step2_authority_prep_g4 import install_startup as install_nba_spread_step2_authority_prep
from .nba_spread_step2_static_diagnostic_g3 import install_startup as install_nba_spread_step2_static_diagnostic
from .nba_spread_step2_static_diagnostic_route_g3 import install as install_nba_spread_step2_static_diagnostic_route

install_startup(app)
install_nba_spread_step2_authority_prep(app)
install_nba_spread_step2_static_diagnostic(app)
install_nba_spread_step2_static_diagnostic_route(app)
