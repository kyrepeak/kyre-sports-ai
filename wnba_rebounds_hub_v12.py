"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.8.1 safe Step 9. Steps 1-8 retain the verified V1.7/V1.7.1
model logic; V1.8 provides Step 9 position matchup context; V1.8.1 temporarily
bypasses persistent disk/session hydration to prevent legacy widget-state crashes.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v181 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.8.1 • SAFE STEP 9",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
