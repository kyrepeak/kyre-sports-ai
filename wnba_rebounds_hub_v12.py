"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.2.2. Steps 1-13 remain preserved through the verified
V2.2.1 chain. V2.2.2 hardens the shared ESPN team-stat environment used by
Steps 7/8/9/10 so transient cold-start transport failures cannot be cached for
six hours: requests retry, failed aggregate frames are cleared/retried, and a
verified <=6h same-season persistent fallback can survive reboot. V2.2.1's
subscription-safe SportsGameOdds Step-13 behavior remains intact.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v222 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.2.2 • RESILIENT COLD-START TEAM ENVIRONMENT",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
