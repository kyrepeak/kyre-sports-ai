"""WNBA Rebounds route wrapper — current isolated production build.

Route directly to V3.0. The verified Steps 1–20 model/market chain remains
preserved through V2.9. V3.0 adds only a post-model Production Readiness Guard:
analysis timestamps, slate-date audit, upcoming-game eligibility, exact quote
freshness/staleness protection, duplicate guards, runtime final-card snapshot
history, line/price movement auditing and a market-only refresh button.

No Step 1–20 projection, probability, EV, qualification or ranking math changes.
Cold-start reliability and subscription-safe SportsGameOdds behavior remain
intact. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v30 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V3.0 • PRODUCTION READINESS GUARD • STEPS 1–20 PRESERVED",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
