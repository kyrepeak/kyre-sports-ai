from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v134 as router


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def _app_source() -> str:
    return APP.read_text(encoding="utf-8")


def test_app_activates_only_router_v134_for_current_bootstrap() -> None:
    source = _app_source()

    assert (
        'FROZEN_V133_DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V133_NFL_SPREAD_MATCHUP_BOARD_2026-09-14"'
    ) in source
    assert (
        'DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V134_NFL_SPREAD_MODEL_MC_2026-09-14"'
    ) in source
    assert (
        "from streamlit_memory_lazy_router_v134 import "
        "record_bootstrap_import_ms, render_app"
    ) in source

    active_import = (
        "from streamlit_memory_lazy_router_v134 import "
        "record_bootstrap_import_ms, render_app"
    )
    assert source.count(active_import) == 1


def test_v134_router_contract_keeps_v133_as_rollback_owner() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v133"
    assert router.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v3"
    assert router.PROJECTION_MODEL_ENABLED is True
    assert router.MONTE_CARLO_ENABLED is True
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STAKE_SIZING_ENABLED is False
    assert router.WAGER_ACTIONS_ENABLED is False


def test_app_keeps_runtime_diagnostics_and_error_radar_intact() -> None:
    source = _app_source()

    assert "PerformanceTrace(surface=\"streamlit\", path=\"app.py\")" in source
    assert "diagnose_trace(_monster_trace, total_ms=_app_total_ms)" in source
    assert 'st.session_state["monster_performance_profiler_v1_last"]' in source
    assert "capture_runtime_exception(" in source
    assert 'properties={"deployment_heartbeat": DEPLOYMENT_HEARTBEAT}' in source
