"""KYRE Sports AI production entrypoint — Universal Runtime V5 + CFB O/U V3 overlay."""
from time import perf_counter

_BOOTSTRAP_STARTED = perf_counter()

from streamlit_memory_lazy_router_universal_runtime_v5_cfb_ou_v3 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()