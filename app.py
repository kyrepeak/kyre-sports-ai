"""Kyre Sports AI Streamlit entrypoint — CFB O/U parallel prewarm live.

Router V75 keeps Router V74's direct College Football Over/Under route and
advances only that route to Clean Page V34.

V34 overlaps independent certified analysis-source cache warmups with the live
sportsbook request. The selected-game analysis still runs through cache-stable
Slate V16 -> official-identity V15 -> frozen V14 unchanged. The optimization
changes wall-clock scheduling only; it does not change model inputs, formulas,
qualification, ranking, selection, or sportsbook semantics.

Permanent protections remain unchanged: frozen V14 projection math, official
ESPN identity recovery, Schedule V7 future-slate coverage, no fuzzy game
matching, no synthetic IDs, and 0.0% sportsbook projection influence.

Deployment heartbeat:
STREAMLIT_MAIN_V75_CFB_OU_PARALLEL_PREWARM_2026-09-11.
"""
from __future__ import annotations

# Retain explicit frozen predecessor imports so the permanent DevSystem guard
# continues proving older active contracts while V75 is the additive top layer.
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
from streamlit_memory_lazy_router_v74 import render_app as _frozen_v74_render_app
from streamlit_memory_lazy_router_v75 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V75_CFB_OU_PARALLEL_PREWARM_2026-09-11"

render_app()
