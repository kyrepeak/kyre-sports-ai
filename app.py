"""Kyre Sports AI Streamlit entrypoint — CFB O/U identity bridge live.

Router V71 keeps Router V70 / Clean Page V30 certified and activates additive
Clean Page V31 for College Football Over/Under only.

Clean Page V31 preserves Schedule V7 future-slate coverage, readable Steps 4-12,
Market Adapter V2 freshness + exact official ESPN event-ID attachment, Step 5C
market intelligence at 0.0% projection influence, and every frozen projection /
qualification rule. The only new active-path behavior is Slate V15, which
reapplies Schedule V7's strict official identity recovery immediately before the
frozen V14 analyzer. It can recover by exact ESPN event ID, exact ESPN team IDs,
or the already-certified unique deterministic alias such as Norfolk St. ->
Norfolk State. Collisions fail closed. No fuzzy game matching. No synthetic IDs.

Deployment heartbeat:
STREAMLIT_MAIN_V71_CFB_OU_DOWNSTREAM_IDENTITY_BRIDGE_2026-09-11.
"""
from __future__ import annotations

# Retain explicit frozen predecessor imports so the permanent DevSystem guard
# continues proving older active contracts while V71 is the additive top layer.
from streamlit_memory_lazy_router_v63 import render_app as _frozen_v63_render_app
from streamlit_memory_lazy_router_v64 import render_app as _frozen_v64_render_app
from streamlit_memory_lazy_router_v65 import render_app as _frozen_v65_render_app
from streamlit_memory_lazy_router_v66 import render_app as _frozen_v66_render_app
from streamlit_memory_lazy_router_v67 import render_app as _frozen_v67_render_app
from streamlit_memory_lazy_router_v68 import render_app as _frozen_v68_render_app
from streamlit_memory_lazy_router_v69 import render_app as _frozen_v69_render_app
from streamlit_memory_lazy_router_v70 import render_app as _frozen_v70_render_app
from streamlit_memory_lazy_router_v71 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V71_CFB_OU_DOWNSTREAM_IDENTITY_BRIDGE_2026-09-11"

render_app()