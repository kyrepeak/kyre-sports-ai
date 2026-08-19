"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.8.2. Steps 1-8 remain verified; V1.8.1 keeps safe mode for
Streamlit state, and V1.8.2 repairs Step 9 by deriving opponents from the full
verified slate and reconciling cached Step-7/8 context on that same slate.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v182 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.8.2 • STEP 9 FULL-SLATE OPPONENT JOIN REPAIR",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
