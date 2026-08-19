"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.7.1. Steps 1-8 retain the verified V1.7 model logic while
V1.7.1 adds only persistent fast-start checkpoint hydration for ordinary app
reboots. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v171 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.7.1 • PERSISTENT FAST START",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
