"""KYRE Sports AI production entrypoint — Universal Runtime V5 + NFL Spread V10 visual overlay."""
from time import perf_counter

_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_nfl_spread_v10 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()