"""Kyre Sports AI Streamlit entrypoint — cache-stable CFB O/U fast route live.

Router V74 keeps Router V73's direct College Football Over/Under route and
advances only that route to Clean Page V33 / Slate V16 cache stability.

The optimization removes certified display-only ``market_*`` context from the
expensive frozen analysis cache key, while the explicit analysis-line threshold
remains part of that cache key. Latest market display fields are restored after
analysis. Clean Page performance profiling remains active.

Permanent protections remain unchanged: frozen V14 projection math, official
ESPN identity recovery, Schedule V7 future-slate coverage, no fuzzy game
matching, no synthetic IDs, and 0.0% sportsbook projection influence.

Deployment heartbeat:
STREAMLIT_MAIN_V74_CFB_OU_CACHE_STABLE_ANALYSIS_2026-09-11.
"""
from __future__ import annotations

# Retain explicit frozen predecessor imports so the permanent DevSystem guard
# continues proving older active contracts while V74 is the additive top layer.
from streamlit_memory_lazy_router_v63 import render_app as _frozen_v63_render_app
from streamlit_memory_lazy_router_v64 import render_app as _frozen_v64_render_app
from streamlit_memory_lazy_router_v65 import render_app as _frozen_v65_render_app
from streamlit_memory_lazy_router_v66 import render_app as _frozen_v66_render_app
from streamlit_memory_lazy_router_v67 import render_app as _frozen_v67_render_app
from streamlit_memory_lazy_router_v68 import render_app as _frozen_v68_render_app
from streamlit_memory_lazy_router_v69 import render_app as _frozen_v69_render_app
from streamlit_memory_lazy_router_v70 import render_app as _frozen_v70_render_app
from streamlit_memory_lazy_router_v71 import render_app as _frozen_v71_render_app
from streamlit_memory_lazy_router_v72 import render_app as _frozen_v72_render_app
from streamlit_memory_lazy_router_v73 import render_app as _frozen_v73_render_app
from streamlit_memory_lazy_router_v74 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V74_CFB_OU_CACHE_STABLE_ANALYSIS_2026-09-11"

render_app()
