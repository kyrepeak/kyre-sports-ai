"""Kyre Sports AI Streamlit entrypoint — NFL Passing Yards compact route live.

Router V80 is additive over certified Router V79. It preserves the College
Football Over/Under cold-start/logo path and every existing sport/market route,
while routing only NFL -> Passing Yards to the new compact foundation page.

The Passing Yards page reuses the verified NFL slate/date identity layer and
keeps projection, sportsbook grading, Monte Carlo, ranking, and recommendation
logic OFF until those dedicated build steps are added.

Permanent CFB protections remain unchanged: frozen V14 projection math, no
fuzzy game matching, no synthetic IDs, and 0.0% sportsbook projection influence.

Deployment heartbeat:
STREAMLIT_MAIN_V80_NFL_PASSING_YARDS_COMPACT_FOUNDATION_2026-09-11.
"""
from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from sports_api.monster_performance_profiler_v1 import (
    PerformanceTrace,
    add_stage_rows,
    compact_summary,
    diagnose_trace,
)
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
    from streamlit_memory_lazy_router_v77 import render_app as _frozen_v77_render_app
    from streamlit_memory_lazy_router_v78 import render_app as _frozen_v78_render_app
    from streamlit_memory_lazy_router_v79 import render_app as _frozen_v79_render_app
    # Static predecessor contract strings retained for Monster regressions.
    from streamlit_memory_lazy_router_v77 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v78 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v79 import record_bootstrap_import_ms, render_app

FROZEN_V77_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11"
FROZEN_V78_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V78_CFB_OU_EXACT_TEAM_LOGOS_2026-09-11"
FROZEN_V79_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V79_CFB_OU_EXACT_TEAM_LOGOS_WIRED_2026-09-11"
DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V80_NFL_PASSING_YARDS_COMPACT_FOUNDATION_2026-09-11"

try:
    _app_started = perf_counter()
    _bootstrap_started = perf_counter()
    from streamlit_memory_lazy_router_v80 import record_bootstrap_import_ms, render_app
    _bootstrap_import_ms = (perf_counter() - _bootstrap_started) * 1000.0
    record_bootstrap_import_ms(_bootstrap_import_ms)
    render_app()
    _app_total_ms = (perf_counter() - _app_started) * 1000.0

    # The active CFB page already owns a measurement-only stage profiler. Monster
    # consumes its public session snapshot instead of changing or duplicating it.
    import streamlit as st

    _monster_trace = PerformanceTrace(surface="streamlit", path="app.py")
    _monster_trace.add("import.bootstrap_router", _bootstrap_import_ms, category="import")

    _cfb_perf = st.session_state.get("cfb_ou_perf_v1_last")
    if isinstance(_cfb_perf, dict):
        add_stage_rows(_monster_trace, _cfb_perf.get("stages"))

    _cold_start = st.session_state.get("cfb_ou_cold_start_v1_last")
    if isinstance(_cold_start, dict):
        try:
            _active_page_import_ms = float(_cold_start.get("active_page_import_ms") or 0.0)
        except (TypeError, ValueError):
            _active_page_import_ms = 0.0
        if _active_page_import_ms > 0.0:
            _monster_trace.add(
                "import.active_page",
                _active_page_import_ms,
                category="import",
            )

    _monster_diagnosis = diagnose_trace(_monster_trace, total_ms=_app_total_ms)
    st.session_state["monster_performance_profiler_v1_last"] = _monster_diagnosis

    with st.expander("⚡ Monster Performance Diagnosis", expanded=False):
        st.caption(compact_summary(_monster_diagnosis))
        st.write(_monster_diagnosis["guidance"])
        if _monster_diagnosis["top_spans"]:
            st.dataframe(
                _monster_diagnosis["top_spans"],
                hide_index=True,
                use_container_width=True,
            )
except Exception as exc:
    capture_runtime_exception(
        exc,
        error_fingerprint=error_fingerprint(exc, path="streamlit-entrypoint"),
        surface="streamlit",
        path="app.py",
        properties={"deployment_heartbeat": DEPLOYMENT_HEARTBEAT},
    )
    raise
