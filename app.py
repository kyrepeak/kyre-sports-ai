"""Kyre Sports AI Streamlit entrypoint — CFB Game Total V151 live recovery.

The current runtime delegates all route ownership to Router V151. V151 is
additive over frozen V150/V149 and advances only exact College Football ->
Game Total to the live-data compact recovery page. All other certified routes
remain delegated to their frozen parents.

Sportsbook projection influence remains 0.0% and stake sizing stays OFF.
"""
from __future__ import annotations

from time import perf_counter

from sports_api.monster_performance_profiler_v1 import (
    PerformanceTrace,
    add_stage_rows,
    compact_summary,
    diagnose_trace,
)
from sports_api.observability_v1 import error_fingerprint
from sports_api.posthog_error_radar_v1 import (
    capture_runtime_exception,
    run_streamlit_activation_probe,
)

FROZEN_V147_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V147_NFL_RECEIVING_YARDS_FUTURE_CARD_RENDER_FIX_2026-09-16"
FROZEN_V148_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V148_CFB_MONEYLINE_MONSTER_DASHBOARD_2026-09-16"
FROZEN_V149_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_COMPACT_DASHBOARD_2026-09-16"
FROZEN_V150_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V150_CFB_GAME_TOTAL_MONSTER_COMPACT_DASHBOARD_2026-09-16"
DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V151_CFB_GAME_TOTAL_LIVE_RECOVERY_2026-09-16"

try:
    _app_started = perf_counter()
    _bootstrap_started = perf_counter()
    from streamlit_memory_lazy_router_v151 import record_bootstrap_import_ms, render_app
    _bootstrap_import_ms = (perf_counter() - _bootstrap_started) * 1000.0
    record_bootstrap_import_ms(_bootstrap_import_ms)
    run_streamlit_activation_probe()
    render_app()
    _app_total_ms = (perf_counter() - _app_started) * 1000.0

    import streamlit as st

    _monster_trace = PerformanceTrace(surface="streamlit", path="app.py")
    _monster_trace.add("import.bootstrap_router", _bootstrap_import_ms, category="import")

    _cfb_perf = st.session_state.get("cfb_ou_perf_v1_last")
    if isinstance(_cfb_perf, dict):
        add_stage_rows(_monster_trace, _cfb_perf.get("stages"))

    _cfb_cold = st.session_state.get("cfb_ou_cold_start_v1_last")
    if isinstance(_cfb_cold, dict):
        try:
            _active_page_import_ms = float(_cfb_cold.get("active_page_import_ms") or 0.0)
        except (TypeError, ValueError):
            _active_page_import_ms = 0.0
        if _active_page_import_ms > 0.0:
            _monster_trace.add("import.active_page", _active_page_import_ms, category="import")

    _rush_cold = st.session_state.get("nfl_rushing_yards_cold_start_v1_last")
    if isinstance(_rush_cold, dict):
        try:
            _rush_page_import_ms = float(_rush_cold.get("active_page_import_ms") or 0.0)
        except (TypeError, ValueError):
            _rush_page_import_ms = 0.0
        if _rush_page_import_ms > 0.0:
            _monster_trace.add("import.nfl_rushing_page", _rush_page_import_ms, category="import")

    _rush_speed = st.session_state.get("nfl_rushing_yards_speed_v1_last")
    if isinstance(_rush_speed, dict):
        for _stage, _category in (
            ("context", "api"),
            ("projection", "analysis"),
            ("market", "market"),
            ("athlete_market", "code"),
        ):
            _bucket = _rush_speed.get(_stage)
            if not isinstance(_bucket, dict):
                continue
            try:
                _work_ms = float(_bucket.get("work_ms") or 0.0)
                _work_calls = max(1, int(_bucket.get("misses") or 1))
            except (TypeError, ValueError):
                continue
            if _work_ms > 0.0:
                _monster_trace.add(
                    f"nfl_rushing.{_stage}",
                    _work_ms,
                    category=_category,
                    calls=_work_calls,
                )

    _monster_diagnosis = diagnose_trace(_monster_trace, total_ms=_app_total_ms)
    st.session_state["monster_performance_profiler_v1_last"] = _monster_diagnosis

    with st.expander("⚡ Monster Performance Diagnosis", expanded=False):
        st.caption(compact_summary(_monster_diagnosis))
        st.write(_monster_diagnosis["guidance"])
        if _monster_diagnosis["top_spans"]:
            st.dataframe(_monster_diagnosis["top_spans"], hide_index=True, use_container_width=True)
except Exception as exc:
    capture_runtime_exception(
        exc,
        error_fingerprint=error_fingerprint(exc, path="streamlit-entrypoint"),
        surface="streamlit",
        path="app.py",
        properties={"deployment_heartbeat": DEPLOYMENT_HEARTBEAT},
    )
    raise
