"""WNBA Assists V2.1 — Step 2 schedule endpoint repair only.

Preserves the entire V2 Step-2 UI/build order and swaps only its schedule loader
to the repaired current WNBA CDN endpoint. No roster, injury, sportsbook,
projection, Monte Carlo or other production model is added here.
"""
from __future__ import annotations

import wnba_assists_hub_v2 as _hub
from wnba_assists_schedule_v2 import load_verified_wnba_slate

# The V2 renderer resolves this name from its own module globals at runtime.
_hub.load_verified_wnba_slate = load_verified_wnba_slate

MODEL_VERSION = "WNBA ASSISTS V2.1 • STEP 2 SCHEDULE ENDPOINT REPAIR"
render_wnba_assists_hub = _hub.render_wnba_assists_hub

__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
