"""WNBA Rebounds route wrapper — current isolated build.

The stable Streamlit router imports this module name. Route Rebounds to the
precise V1.3.2 Step-4 player-history build without touching frozen WNBA
Points/PRA or MLB production modules.
"""
from __future__ import annotations

import importlib

import wnba_rebounds_hub_v132 as _impl

# Force current on-disk Rebounds build after Streamlit hot reloads/redeploys.
_impl = importlib.reload(_impl)

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.3.2 • STEP 4 VERIFIED PLAYER-HISTORY ROLE",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
