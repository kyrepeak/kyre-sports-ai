"""Active router wrapper for WNBA PRA Speed V3 Step 7 precompute."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step6 as frozen_parent
import wnba_pra_speed_v3_step7_precompute as step7

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 7 PRECOMPUTE"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step6"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    return step7.render_step7_route(frozen_parent.render_app)


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
