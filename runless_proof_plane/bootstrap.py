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
os.environ["RPP_NBA_SPREAD_STEP2_AUTHORITY_PREP_ON_START"] = "0"
os.environ["RPP_NBA_SPREAD_STEP2_G4_AUTHORITY_PREP_ON_START"] = "0"
os.environ["RPP_NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT_ON_START"] = "0"

from .api import app
from .nba_spread_step2_authority_prep_g4 import install_startup as install_nba_spread_step2_authority_prep
from .nba_spread_step2_postmerge_closeout_r3 import install_startup as install_nba_spread_step2_postmerge_closeout
from .nba_spread_step2_static_diagnostic_g3 import install_startup as install_nba_spread_step2_static_diagnostic
from .nba_spread_step2_static_diagnostic_route_g3 import install as install_nba_spread_step2_static_diagnostic_route
from .nba_spread_step3_authority_prove import install_startup as install_nba_spread_step3_authority_prove
from .nba_spread_step3_finalize_startup import install_startup as install_nba_spread_step3_finalize
from .nba_spread_step4_finalize_startup import install_startup as install_nba_spread_step4_finalize
from .universal_sports_step5_authority_prove import install_startup as install_universal_sports_step5_authority_prove

# CFB Step-8 terminal postmerge rebind is intentionally not installed here.
# It is terminal, targets an old main SHA, and its unconditional startup thread
# can race the active proof owner's first GitHub App token request on cold boot.
install_nba_spread_step2_authority_prep(app)
install_nba_spread_step2_postmerge_closeout(app)
install_nba_spread_step2_static_diagnostic(app)
install_nba_spread_step2_static_diagnostic_route(app)
install_nba_spread_step3_authority_prove(app)
install_nba_spread_step3_finalize(app)
install_nba_spread_step4_finalize(app)
install_universal_sports_step5_authority_prove(app)
