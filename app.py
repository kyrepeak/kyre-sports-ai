"""KYRE Sports AI production entrypoint — Universal Runtime V5 + isolated CFB Top Picks V2 successor overlay."""
from time import perf_counter

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-cfb-top-picks-page1-stier-v2-20261022"
_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()