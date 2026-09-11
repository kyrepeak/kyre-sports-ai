"""Kyre Sports AI Streamlit entrypoint — direct CFB O/U fast route live.

Router V73 keeps Router V72 / Clean Page V32 certified and adds one isolated
performance optimization for College Football -> Over/Under: when that route is
already active in Streamlit session state, V73 runs the frozen V1 shell directly
with the certified CFB selector adaptation and dispatches straight to Clean Page
V32 instead of traversing the historical V2-V72 wrapper chain.

Clean Page V32 performance profiling remains active, and every certified CFB
Over/Under contract remains unchanged. No schedule, market, team-data,
projection, ranking, qualification, or selection logic is changed.

Permanent protections remain unchanged: frozen V14 projection math, official
ESPN identity recovery, no fuzzy game matching, no synthetic IDs, and 0.0%
sportsbook projection influence.

Deployment heartbeat:
STREAMLIT_MAIN_V73_CFB_OU_DIRECT_FAST_ROUTE_2026-09-11.
"""
from __future__ import annotations

# Retain explicit frozen predecessor imports so the permanent DevSystem guard
# continues proving older active contracts while V73 is the additive top layer.
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
from streamlit_memory_lazy_router_v73 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V73_CFB_OU_DIRECT_FAST_ROUTE_2026-09-11"

render_app()
