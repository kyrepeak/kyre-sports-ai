"""WNBA Live Games V4.2 — Step 4 official-date historical backfill repair.

Preserves the V4.1 renderer and Steps 1-3 exactly. This wrapper swaps only the
Step-4 historical provider to V1.3, which discovers ESPN historical event ids
from official WNBA schedule dates instead of ESPN's team-schedule endpoint.
"""
from __future__ import annotations

import wnba_live_hub_v41 as v41
import wnba_live_second_half_v13 as hist13

MODEL_VERSION = "WNBA LIVE GAMES V4.2 • STEP 4 OFFICIAL-DATE HISTORY"


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    old_hist = v41.hist12
    old_model = v41.MODEL_VERSION
    v41.hist12 = hist13
    v41.MODEL_VERSION = MODEL_VERSION
    try:
        v41.render_wnba_live_hub(section_header, status_info, team_logo, h)
    finally:
        v41.hist12 = old_hist
        v41.MODEL_VERSION = old_model
