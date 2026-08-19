"""WNBA Rebounds route wrapper — current isolated build.

Route directly to the V1.5.5 nonblocking Step-6 build. This bypasses the legacy
NBA/WNBA tracking timeout chain on normal Streamlit page loads while preserving
verified Steps 1-5 and leaving frozen Points/PRA/MLB modules untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v155 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.5.5 • DIRECT NONBLOCKING STEP 6",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
