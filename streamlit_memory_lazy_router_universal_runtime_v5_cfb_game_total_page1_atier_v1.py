"""Terminal successor for CFB Game Total Page 1 A-tier V1."""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1 as prior
from universal_page_experience_runtime_v5 import render_page_experience_app_v5
from universal_runtime_v5_loader_cfb_game_total_page1_atier_v1 import resolve_destination

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • CFB GAME TOTAL PAGE1 A-TIER V1"
FROZEN_RUNTIME = prior.FROZEN_RUNTIME
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime = prior.frozen_runtime
frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_page_experience_app_v5(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
