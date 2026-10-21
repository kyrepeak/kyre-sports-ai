"""KYRE Sports AI production entrypoint — Universal Runtime V5 + isolated NBA PRA Page 1 overlay over frozen NFL Daily Picks V4."""
from time import perf_counter

# API2 NBA PRA Page 1 — inert Streamlit entrypoint heartbeat for stale-import recovery.
API2_NBA_PRA_PAGE1_STREAMLIT_ENTRYPOINT_HEARTBEAT_V1 = "2026-10-21-R1"

_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
