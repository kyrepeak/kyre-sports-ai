"""KYRE Sports AI production entrypoint — frozen terminal owner + isolated CFB Top Picks Page 2 analytics successor."""
from time import perf_counter

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-cfb-top-picks-page2-analytics-lab-v1-20261022"
_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

# Frozen Page 1 V4 remains the predecessor; Page 2 is successor-only.
import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v4 as _cfb_top_picks_v4  # noqa: E402,F401
import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v1 as _cfb_top_picks_page2_v1  # noqa: E402,F401

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
