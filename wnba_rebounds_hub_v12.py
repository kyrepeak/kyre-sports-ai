"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.6. Steps 1-6 remain the verified V1.5.5 fast path and
Step 7 adds only the opponent missed-shot environment. Frozen Points/PRA/MLB
modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v16 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.6 • STEP 7 OPPONENT MISSED-SHOT ENVIRONMENT",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
