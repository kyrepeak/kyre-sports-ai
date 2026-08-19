"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.7. Steps 1-7 remain the verified V1.6/V1.5.5 fast path and
Step 8 adds only the opponent rebounding-allowed/capture environment. Frozen
Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v17 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.7 • STEP 8 OPPONENT REBOUNDING ALLOWED",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
