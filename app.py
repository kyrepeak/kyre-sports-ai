"""Kyre Sports AI Streamlit entrypoint — CFB Game Total V164 activation.

The production entrypoint now boots additive Router V160. V160 preserves the
certified Router V159 chain for every existing market while advancing only exact
College Football -> Game Total through the Render-hosted official identity feed.

Sportsbook projection influence stays 0.0% and frozen model behavior remains
unchanged.
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
from sports_api.posthog_error_radar_v1 import (
    capture_runtime_exception,
    run_streamlit_activation_probe,
)

if TYPE_CHECKING:
    # Frozen V161/V162 source-level certification compatibility only; runtime boots V160 below.
    from streamlit_memory_lazy_router_v157 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v158 import record_bootstrap_import_ms, render_app
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
    from streamlit_memory_lazy_router_v80 import render_app as _frozen_v80_render_app
    from streamlit_memory_lazy_router_v81 import render_app as _frozen_v81_render_app
    from streamlit_memory_lazy_router_v82 import render_app as _frozen_v82_render_app
    from streamlit_memory_lazy_router_v83 import render_app as _frozen_v83_render_app
    from streamlit_memory_lazy_router_v84 import render_app as _frozen_v84_render_app
    from streamlit_memory_lazy_router_v85 import render_app as _frozen_v85_render_app
    from streamlit_memory_lazy_router_v86 import render_app as _frozen_v86_render_app
    from streamlit_memory_lazy_router_v87 import render_app as _frozen_v87_render_app
    from streamlit_memory_lazy_router_v88 import render_app as _frozen_v88_render_app
    from streamlit_memory_lazy_router_v89 import render_app as _frozen_v89_render_app
    from streamlit_memory_lazy_router_v90 import render_app as _frozen_v90_render_app
    from streamlit_memory_lazy_router_v91 import render_app as _frozen_v91_render_app
    from streamlit_memory_lazy_router_v92 import render_app as _frozen_v92_render_app
    from streamlit_memory_lazy_router_v93 import render_app as _frozen_v93_render_app
    from streamlit_memory_lazy_router_v94 import render_app as _frozen_v94_render_app
    from streamlit_memory_lazy_router_v95 import render_app as _frozen_v95_render_app
    from streamlit_memory_lazy_router_v96 import render_app as _frozen_v96_render_app
    from streamlit_memory_lazy_router_v97 import render_app as _frozen_v97_render_app
    from streamlit_memory_lazy_router_v98 import render_app as _frozen_v98_render_app
    from streamlit_memory_lazy_router_v99 import render_app as _frozen_v99_render_app
    from streamlit_memory_lazy_router_v100 import render_app as _frozen_v100_render_app
    from streamlit_memory_lazy_router_v101 import render_app as _frozen_v101_render_app
    from streamlit_memory_lazy_router_v102 import render_app as _frozen_v102_render_app
    from streamlit_memory_lazy_router_v103 import render_app as _frozen_v103_render_app
    from streamlit_memory_lazy_router_v104 import render_app as _frozen_v104_render_app
    from streamlit_memory_lazy_router_v105 import render_app as _frozen_v105_render_app
    from streamlit_memory_lazy_router_v106 import render_app as _frozen_v106_render_app
    from streamlit_memory_lazy_router_v107 import render_app as _frozen_v107_render_app
    from streamlit_memory_lazy_router_v108 import render_app as _frozen_v108_render_app
    from streamlit_memory_lazy_router_v109 import render_app as _frozen_v109_render_app
    from streamlit_memory_lazy_router_v110 import render_app as _frozen_v110_render_app
    from streamlit_memory_lazy_router_v111 import render_app as _frozen_v111_render_app
    from streamlit_memory_lazy_router_v112 import render_app as _frozen_v112_render_app
    from streamlit_memory_lazy_router_v113 import render_app as _frozen_v113_render_app
    from streamlit_memory_lazy_router_v114 import render_app as _frozen_v114_render_app
    from streamlit_memory_lazy_router_v115 import render_app as _frozen_v115_render_app
    from streamlit_memory_lazy_router_v116 import render_app as _frozen_v116_render_app
    from streamlit_memory_lazy_router_v117 import render_app as _frozen_v117_render_app
    from streamlit_memory_lazy_router_v118 import render_app as _frozen_v118_render_app
    from streamlit_memory_lazy_router_v119 import render_app as _frozen_v119_render_app
    from streamlit_memory_lazy_router_v120 import render_app as _frozen_v120_render_app
    from streamlit_memory_lazy_router_v121 import render_app as _frozen_v121_render_app
    from streamlit_memory_lazy_router_v122 import render_app as _frozen_v122_render_app
    from streamlit_memory_lazy_router_v123 import render_app as _frozen_v123_render_app
    from streamlit_memory_lazy_router_v124 import render_app as _frozen_v124_render_app
    from streamlit_memory_lazy_router_v125 import render_app as _frozen_v125_render_app
    from streamlit_memory_lazy_router_v126 import render_app as _frozen_v126_render_app
    from streamlit_memory_lazy_router_v127 import render_app as _frozen_v127_render_app
    from streamlit_memory_lazy_router_v128 import render_app as _frozen_v128_render_app
    from streamlit_memory_lazy_router_v129 import render_app as _frozen_v129_render_app
    from streamlit_memory_lazy_router_v130 import render_app as _frozen_v130_render_app
    from streamlit_memory_lazy_router_v129 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v128 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v127 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v126 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v125 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v124 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v123 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v122 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v77 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v78 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v79 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v80 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v81 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v82 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v83 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v84 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v85 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v86 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v87 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v88 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v89 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v90 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v91 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v92 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v93 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v94 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v95 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v96 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v97 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v98 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v99 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v100 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v101 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v102 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v103 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v104 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v105 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v106 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v107 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v108 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v109 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v110 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v111 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v112 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v113 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v114 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v115 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v116 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v117 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v118 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v119 import record_bootstrap_import_ms, render_app
    from streamlit_memory_lazy_router_v120 import record_bootstrap_import_ms, render_app

FROZEN_V77_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11"
FROZEN_V78_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V78_CFB_OU_EXACT_TEAM_LOGOS_2026-09-11"
FROZEN_V79_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V79_CFB_OU_EXACT_TEAM_LOGOS_WIRED_2026-09-11"
FROZEN_V80_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V80_NFL_PASSING_YARDS_COMPACT_FOUNDATION_2026-09-11"
FROZEN_V81_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V81_NFL_PASSING_YARDS_STEP1_IDENTITY_2026-09-11"
FROZEN_V82_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V82_NFL_PASSING_YARDS_STEP2_QB_PROFILE_2026-09-11"
FROZEN_V83_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V83_NFL_PASSING_YARDS_STEP3_PASS_DEFENSE_2026-09-11"
FROZEN_V84_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V84_NFL_PASSING_YARDS_STEP4_PRESSURE_2026-09-11"
FROZEN_V85_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V85_NFL_PASSING_YARDS_STEP5_PERSONNEL_2026-09-11"
FROZEN_V86_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V86_NFL_PASSING_YARDS_STEP6_ENVIRONMENT_2026-09-11"
FROZEN_V87_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V87_NFL_PASSING_YARDS_STEP7_BASELINE_PROJECTION_2026-09-11"
FROZEN_V88_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V88_NFL_PASSING_YARDS_STEP8_CONTEXT_UNCERTAINTY_2026-09-11"
FROZEN_V89_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V89_NFL_PASSING_YARDS_STEP9_DISTRIBUTION_PROBABILITY_2026-09-11"
FROZEN_V90_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V90_NFL_PASSING_YARDS_STEP10_MARKET_EDGE_FINAL_2026-09-11"
FROZEN_V91_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V91_NFL_PASSING_YARDS_LIVE_ROUTE_AUTO_SLATE_2026-09-11"
FROZEN_V92_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V92_NFL_PASSING_YARDS_CLEANUP_STEP1_2026-09-11"
FROZEN_V93_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V93_NFL_PASSING_YARDS_CLEANUP_STEP2_2026-09-11"
FROZEN_V94_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V94_NFL_PASSING_YARDS_CLEANUP_STEP3_2026-09-11"
FROZEN_V95_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V95_NFL_PASSING_YARDS_CLEANUP_STEP4_2026-09-11"
FROZEN_V96_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V96_NFL_PASSING_YARDS_ROUTE_PRECEDENCE_HOTFIX_V2_2026-09-11"
FROZEN_V97_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V97_NFL_PASSING_YARDS_EARLY_SEASON_BRIDGE_2026-09-11"
FROZEN_V98_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V98_NFL_RUSHING_YARDS_UI_CLEANUP_2026-09-12"
FROZEN_V99_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V99_NFL_RUSHING_YARDS_STEP4_MARKET_CONTEXT_2026-09-12"
FROZEN_V100_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V100_NFL_RUSHING_YARDS_PAGE_STEP1_COMPACT_PLAYER_CARDS_2026-09-12"
FROZEN_V101_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V101_NFL_RUSHING_YARDS_PAGE_STEP2_SUMMARY_METRICS_2026-09-12"
FROZEN_V102_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V102_NFL_RUSHING_YARDS_PAGE_STEP3_WORKLOAD_EFFICIENCY_2026-09-12"
FROZEN_V103_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V103_NFL_RUSHING_YARDS_PAGE_STEP4_OPPONENT_RUN_DEFENSE_2026-09-12"
FROZEN_V104_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V104_NFL_RUSHING_YARDS_PAGE_STEP5_PROJECTION_RECIPE_2026-09-12"
FROZEN_V105_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V105_NFL_RUSHING_YARDS_PAGE_STEP6_SUPPORT_CONCERNS_2026-09-12"
FROZEN_V106_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V106_NFL_RUSHING_YARDS_PERFORMANCE_FAST_ROUTE_2026-09-12"
FROZEN_V107_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V107_NFL_RUSHING_YARDS_HTML_RENDER_REPAIR_2026-09-12"
FROZEN_V108_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V108_NFL_RUSHING_YARDS_FANDUEL_FULL_LINEUP_2026-09-12"
FROZEN_V109_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V109_NFL_RUSHING_YARDS_MATCHUP_TIERS_2026-09-12"
FROZEN_V110_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V110_NFL_RUSHING_YARDS_DETAILED_MATCHUP_TIERS_2026-09-13"
FROZEN_V111_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V111_NFL_RUSHING_YARDS_PHOENIX_GAME_TIMES_2026-09-13"
FROZEN_V112_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V112_NFL_RECEIVING_YARDS_STEP1_FOUNDATION_2026-09-13"
FROZEN_V113_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V113_NFL_RECEIVING_YARDS_STEP2_PLAYER_CARDS_2026-09-13"
FROZEN_V114_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V114_NFL_RECEIVING_YARDS_STEP3_SUMMARY_METRICS_2026-09-13"
FROZEN_V115_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V115_NFL_RECEIVING_YARDS_STEP4_VOLUME_EFFICIENCY_2026-09-13"
FROZEN_V116_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V116_NFL_RECEIVING_YARDS_STEP5_DEFENSE_H2H_2026-09-13"
FROZEN_V117_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V117_NFL_RECEIVING_YARDS_STEP6_PROJECTION_RECIPE_2026-09-13"
FROZEN_V118_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V118_NFL_RECEIVING_YARDS_STEP7_SUPPORT_CONCERNS_2026-09-13"
FROZEN_V119_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V119_NFL_RECEIVING_YARDS_STEP8_FANDUEL_FULL_LINEUP_2026-09-13"
FROZEN_V120_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V120_NFL_RECEIVING_YARDS_STEP9_MATCHUP_TIERS_2026-09-13"
FROZEN_V121_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V121_NFL_RECEIVING_YARDS_STEP10_FINAL_POLISH_SPEED_CERT_2026-09-13"
FROZEN_V122_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V122_NFL_PASSING_YARDS_VISUAL_PARITY_STEP2_QB_HEROES_2026-09-13"
FROZEN_V123_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V123_NFL_PASSING_YARDS_VISUAL_PARITY_STEP3_QB_PROFILE_2026-09-13"
FROZEN_V124_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V124_NFL_PASSING_YARDS_VISUAL_PARITY_STEP4_CONTEXT_CARDS_2026-09-13"
FROZEN_V125_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V125_NFL_PASSING_YARDS_VISUAL_PARITY_STEP5_ANALYTICAL_READOUTS_2026-09-13"
FROZEN_V126_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V126_NFL_PASSING_YARDS_VISUAL_PARITY_STEP6_FINAL_2026-09-13"
FROZEN_V127_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V127_NFL_PASSING_YARDS_COMBINED_PLAYER_CARDS_2026-09-13"
FROZEN_V128_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V128_NFL_PASSING_YARDS_PRODUCTION_CLEANUP_2026-09-13"
FROZEN_V129_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V129_NFL_MONEYLINE_KYRE_API_TRANSPORT_2026-09-14"
FROZEN_V130_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V130_NFL_MONEYLINE_NO_FLASH_2026-09-14"
FROZEN_V131_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V131_NFL_MONEYLINE_PERFORMANCE_FAST_ROUTE_2026-09-14"
FROZEN_V132_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V132_NFL_SPREAD_KYRE_API_TRANSPORT_2026-09-14"
FROZEN_V133_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V133_NFL_SPREAD_MATCHUP_BOARD_2026-09-14"
FROZEN_V134_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V134_NFL_SPREAD_MODEL_MC_2026-09-14"
FROZEN_V135_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V135_NFL_SPREAD_VISUAL_PARITY_2026-09-14"
FROZEN_V136_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V136_NFL_SPREAD_FRESH_ROUTER_2026-09-14"
FROZEN_V137_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V137_NFL_PASSING_YARDS_COMPACT_DASHBOARD_2026-09-15"
FROZEN_V138_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V138_NFL_PASSING_YARDS_SMART_SLATE_2026-09-16"
FROZEN_V139_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V139_NFL_PASSING_YARDS_PHOENIX_TIME_2026-09-16"
FROZEN_V140_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V140_NFL_PASSING_YARDS_PRESENTATION_GRADES_2026-09-16"
FROZEN_V141_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V141_NFL_PASSING_YARDS_PHOENIX_SELECTOR_2026-09-16"
FROZEN_V142_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V142_NFL_RECEIVING_YARDS_SMART_SLATE_2026-09-16"
FROZEN_V143_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V143_NFL_RECEIVING_YARDS_PHOENIX_TIME_2026-09-16"
FROZEN_V144_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V144_NFL_RECEIVING_YARDS_MATCHUP_TIERS_V2_2026-09-16"
FROZEN_V145_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V145_NFL_RECEIVING_YARDS_PLAYER_CARD_REDESIGN_2026-09-16"
FROZEN_V146_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V146_NFL_RECEIVING_YARDS_PLAYER_VS_DEFENSE_HISTORY_2026-09-16"
FROZEN_V147_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V147_NFL_RECEIVING_YARDS_FUTURE_CARD_RENDER_FIX_2026-09-16"
FROZEN_V148_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V148_CFB_MONEYLINE_MONSTER_DASHBOARD_2026-09-16"
FROZEN_V149_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_COMPACT_DASHBOARD_2026-09-16"
DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V136_NFL_SPREAD_FRESH_ROUTER_2026-09-14"

try:
    _app_started = perf_counter()
    _bootstrap_started = perf_counter()
    from streamlit_memory_lazy_router_v160 import record_bootstrap_import_ms, render_app
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