"""KYRE Sports AI production entrypoint — universal navigation speed terminal."""
from time import perf_counter

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-universal-streamlit-navigation-speed-v1-20261022"
_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
