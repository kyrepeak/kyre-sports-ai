"""KYRE Sports AI production entrypoint — Universal Runtime V5 + isolated NFL Daily Picks V4 overlay."""
from time import perf_counter

_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
