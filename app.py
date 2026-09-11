"""Kyre Sports AI Streamlit entrypoint — CFB O/U cold-start fast route live.

Router V77 preserves the certified V76 behavior while allowing an already-active
College Football -> Over/Under session to start without eagerly importing the
historical V63-V76 router spine. Non-fast routes still lazy-load frozen Router
V76 unchanged.

Clean Page V35 remains the active CFB Over/Under page, including freshness-safe
market snapshot reuse, parallel analysis prewarm, cache-stable analysis, the
performance profiler, official ESPN identity recovery, and Schedule V7 future
slate coverage.

Permanent protections remain unchanged: frozen V14 projection math, no fuzzy
game matching, no synthetic IDs, and 0.0% sportsbook projection influence.

Deployment heartbeat:
STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11.
"""
from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from sports_api.observability_v1 import error_fingerprint
from sports_api.posthog_error_radar_v1 import capture_runtime_exception

# Keep predecessor contracts statically visible to the permanent regression
# shield without paying their import cost on the active cold-start path.
if TYPE_CHECKING:
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
    from streamlit_memory_lazy_router_v75 import render_app as _frozen_v75_render_app
    from streamlit_memory_lazy_router_v76 import render_app as _frozen_v76_render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11"

try:
    _bootstrap_started = perf_counter()
    from streamlit_memory_lazy_router_v77 import record_bootstrap_import_ms, render_app
    record_bootstrap_import_ms((perf_counter() - _bootstrap_started) * 1000.0)
    render_app()
except Exception as exc:
    capture_runtime_exception(
        exc,
        error_fingerprint=error_fingerprint(exc, path="streamlit-entrypoint"),
        surface="streamlit",
        path="app.py",
        properties={"deployment_heartbeat": DEPLOYMENT_HEARTBEAT},
    )
    raise
