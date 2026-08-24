"""WNBA Spread V1.6.2 compatibility boundary -> V1.6.3 Card Step 3.

The frozen application still imports wnba_spread_hub_v162. The verified V1.6.2
Steps 1-2 implementation is preserved byte-for-byte in
wnba_spread_hub_v162_core.py; this small shim forwards only the public
presentation boundary to V1.6.3. The V1.6.1 production model remains untouched.
"""
from __future__ import annotations

import wnba_spread_hub_v163 as presentation

base = presentation.base
MODEL_VERSION = presentation.MODEL_VERSION


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return presentation.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(presentation, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
