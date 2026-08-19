"""WNBA Rebounds route wrapper — current isolated build.

The stable Streamlit router imports this module name. Route Rebounds to the
V1.5.4 resilient Step-6 build without touching frozen WNBA Points/PRA or MLB
modules.

Important: do NOT importlib.reload the implementation here. Reloading recreates
cached functions and defeats Streamlit's rerun cache, which was a major source
of slow page loads.
"""
from __future__ import annotations

import wnba_rebounds_hub_v154 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.5.4 • RESILIENT STEP 6",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
