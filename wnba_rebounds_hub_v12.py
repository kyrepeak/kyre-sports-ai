"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.8.4. Steps 1-4 remain unchanged. V1.8.4 stabilizes the
Step-5 cold-start gate by reusing already-verified Step-4 PLAYER_ID rebound
history only when the fast Step-5 player-pool reconciliation is sparse. It adds
zero new network requests and preserves the V1.8.2/V1.8.3 Step-9 repairs.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v184 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.8.4 • STEP 5 COLD-START COVERAGE STABILIZATION",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
