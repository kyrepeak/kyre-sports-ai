"""KYRE Sports AI production entrypoint — frozen terminal owner + isolated CFB Top Picks V2 overlay."""
from time import perf_counter

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-cfb-top-picks-page1-stier-v2-20261022"
_BOOTSTRAP_STARTED = perf_counter()

# Preserve the certified universal tap-first terminal as the production owner.
from streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

# Importing the successor overlay mutates only the CFB Top Picks destination on
# the already-owned frozen runtime; it does not replace the terminal owner.
import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2 as _cfb_top_picks_v2  # noqa: E402,F401

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
