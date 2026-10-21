from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v2_runtime_mounts_client_controller_before_selected_destination_load():
    source = _source("universal_atomic_navigation_runtime_v2.py")
    assert "transition_controller_markup" in source
    assert "_mount_transition_controller(runtime.active)" in source
    assert source.index("_mount_transition_controller(runtime.active)") < source.index("core.load_destination(adapter)")
    assert "destination_slot = st.empty()" in source
    assert "_run_bounded_prefetch" not in source
    assert "choose_prefetch" not in source


def test_current_terminal_chain_inherits_v2_without_app_or_nba_reimplementation():
    v3 = _source("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py")
    v4 = _source("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4.py")
    nba = _source("streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py")
    app = _source("app.py")

    assert "from universal_atomic_navigation_runtime_v2 import render_atomic_app" in v3
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 as prior" in v4
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4 as prior" in nba
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1" in app
    assert "universal_atomic_navigation_runtime_v2" not in app
    assert "universal_atomic_navigation_runtime_v2" not in nba


def test_v1_owners_remain_present_as_frozen_parent_contract():
    helper = _source("universal_atomic_navigation_v1.py")
    runtime = _source("universal_atomic_navigation_runtime_v1.py")
    assert "MONSTER UNIVERSAL ATOMIC NAVIGATION V1" in helper
    assert "MONSTER UNIVERSAL ATOMIC NAVIGATION RUNTIME V1" in runtime
    assert "def transition_markup" in helper
    assert "def render_atomic_app" in runtime
