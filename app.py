"""KYRE Sports AI production entrypoint — NFL Rushing Page 1 density R1."""
from time import perf_counter

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-nfl-rushing-page1-density-r1-20261025"
_BOOTSTRAP_STARTED = perf_counter()

# Frozen ancestry markers retained for regression/documentation only:
# streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1
# streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v3
# streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1
# streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1
# streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1
# streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_repair_r1
# streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1
# streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1
from streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
