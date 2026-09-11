"""Kyre Sports AI Streamlit entrypoint — CFB O/U performance profiler live.

Router V72 keeps Router V71 / Clean Page V31 certified and activates additive
Clean Page V32 for College Football Over/Under only.

Clean Page V32 is measurement-only instrumentation around the already-certified
V31 path. It records server-side timing for schedule loading, market loading,
market attachment, selected-game analysis, readable presentation work, and the
full-slate UI path so real bottlenecks can be identified before any optimization
is attempted. It does not change schedule identity, sportsbook semantics,
projection inputs, projection math, ranking, qualification, or selection.

Permanent protections remain unchanged: frozen V14 projection math, official
ESPN identity recovery, no fuzzy game matching, no synthetic IDs, and 0.0%
sportsbook projection influence.

Deployment heartbeat:
STREAMLIT_MAIN_V72_CFB_OU_PERFORMANCE_PROFILER_2026-09-11.
"""
from __future__ import annotations

# Retain explicit frozen predecessor imports so the permanent DevSystem guard
# continues proving older active contracts while V72 is the additive top layer.
from streamlit_memory_lazy_router_v63 import render_app as _frozen_v63_render_app
from streamlit_memory_lazy_router_v64 import render_app as _frozen_v64_render_app
from streamlit_memory_lazy_router_v65 import render_app as _frozen_v65_render_app
from streamlit_memory_lazy_router_v66 import render_app as _frozen_v66_render_app
from streamlit_memory_lazy_router_v67 import render_app as _frozen_v67_render_app
from streamlit_memory_lazy_router_v68 import render_app as _frozen_v68_render_app
from streamlit_memory_lazy_router_v69 import render_app as _frozen_v69_render_app
from streamlit_memory_lazy_router_v70 import render_app as _frozen_v70_render_app
from streamlit_memory_lazy_router_v71 import render_app as _frozen_v71_render_app
from streamlit_memory_lazy_router_v72 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V72_CFB_OU_PERFORMANCE_PROFILER_2026-09-11"

render_app()
