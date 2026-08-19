"""WNBA Rebounds route wrapper — current isolated production build.

Route directly to V3.1.1. The verified Steps 1–20 model/market chain, V3.0
Production Readiness Guard and V3.1 responsive Top-5 visual cards remain
unchanged. V3.1.1 is presentation-only: player initials are removed from the
headshot circle so the face remains unobstructed, and the #1 card gets a subtle
BEST PICK emphasis.

No Step 1–20 projection, probability, EV, qualification or ranking math changes.
No production-readiness rules change. Cold-start reliability and subscription-safe
SportsGameOdds behavior remain intact. Frozen Points/PRA/MLB modules remain
untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v311 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V3.1.1 • CLEAN PLAYER FACES + TOP-PICK POLISH • MODEL PRESERVED",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
