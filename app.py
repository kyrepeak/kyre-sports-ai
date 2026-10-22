"""KYRE Sports AI production entrypoint — frozen terminal owner + isolated CFB Top Picks V4 overlay."""
from time import perf_counter

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-cfb-top-picks-page1-cleanup-v4-20261022"
_BOOTSTRAP_STARTED = perf_counter()

# Preserve the certified universal tap-first terminal as the production owner.
from streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

# Frozen successor lineage remains explicit for regression ownership:
# streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2
# streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3
# V4 imports the V3 overlay, which chains V2 internally, then changes only the
# CFB Top Picks destination to the cleanup renderer.
import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v4 as _cfb_top_picks_v4  # noqa: E402,F401

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
