from __future__ import annotations
import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"

from .api import app
from . import wnba_data_step3_streamlit_refresh_gate as gate

gate.REPAIR_RECEIPT = "67b46ded9a1a4fc9df56799e98bf10842a90310dccca67188270968cb0e48503"
gate.install_startup(app)
