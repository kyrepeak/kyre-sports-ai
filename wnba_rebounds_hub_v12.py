"""WNBA Rebounds route wrapper — current isolated build.

The stable Streamlit router imports this module name. Route Rebounds to the
V1.5.1 Step-6 speed/timezone-safe build without touching frozen WNBA Points/PRA
or MLB production modules.
"""
from __future__ import annotations

import importlib

import wnba_rebounds_hub_v151 as _impl

# Force current on-disk Rebounds build after Streamlit hot reloads/redeploys.
_impl = importlib.reload(_impl)

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.5.1 • STEP 6 FAST SNAPSHOT + TZ SAFE",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
