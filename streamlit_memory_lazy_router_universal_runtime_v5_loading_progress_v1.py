"""Terminal successor adding truthful universal loading progress.

Delegates all route ownership to the current navigation-speed regression repair
terminal so NBA PRA, CFB Top Picks V19, and NFL rushing routing stay unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1 as prior
from universal_page_experience_runtime_v4 import render_page_experience_app_v4

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • LOADING PROGRESS V1"
FROZEN_RUNTIME = prior.FROZEN_RUNTIME
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime = prior.frozen_runtime
resolve_destination = prior.resolve_destination
frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_page_experience_app_v4(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
