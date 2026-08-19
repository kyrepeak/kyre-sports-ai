"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.8.3. Steps 1-8 remain verified; V1.8.2 keeps the exact
Step-1 V2.5 opponent join repair; V1.8.3 adds only numerical stabilization for
verified zero same-position competition so a real 0.000 capture share is not
misclassified as missing data. Unknown positions remain CHECK and are never
guessed. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v183 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.8.3 • STEP 9 STRUCTURAL-ZERO STABILIZATION",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
