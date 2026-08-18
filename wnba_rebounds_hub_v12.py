"""WNBA Rebounds route wrapper — current isolated build.

The stable Streamlit router still imports this module name. Route the Rebounds
page to the newest isolated V1.3 implementation without touching frozen
WNBA Points/PRA or MLB production modules.
"""
from __future__ import annotations

import importlib

import wnba_rebounds_hub_v13 as _impl

# Force current on-disk Rebounds build after Streamlit hot reloads/redeploys.
_impl = importlib.reload(_impl)

MODEL_VERSION = getattr(_impl, "MODEL_VERSION", "WNBA REBOUNDS V1.3 • STEP 4 OREB/DREB ROLE")


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
