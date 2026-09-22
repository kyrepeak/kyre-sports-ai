"""WNBA Rebounds route wrapper — current isolated production build.

Route directly to V3.1.2. The verified Steps 1–20 model/market chain, V3.0
Production Readiness Guard and V3.1.1 visual cards remain unchanged. V3.1.2
repairs only the Step-18 input reconciliation: provider quote rows that have a
valid same-book no-vig pair but no exact VERIFIED current-player Player+Team
identity remain visible in the Step-14 audit but are not allowed to enter the
Step-18 probability gate and deadlock every valid player.

No Step 1–20 projection, PMF, Monte Carlo, probability, fair-odds, EV,
qualification or ranking math changes. No production-readiness thresholds change.
"""
from __future__ import annotations

import wnba_rebounds_hub_v312 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V3.1.2 • STEP-18 VERIFIED-PLAYER MARKET RECONCILIATION",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
