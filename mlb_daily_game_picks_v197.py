"""MLB Daily Game Picks V1.9.7 bridge — resilient Home Run lineup intake.

Preserves Moneyline V1.9.2, Pitcher K V1.8.2, H+R+RBI V1.7.1, and Home Run
V1.6.1 production orchestration, then installs the V1.6.2 HR lineup-intake retry
patch. Calibrated HR V1.1 probability math remains unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v196 as base
import mlb_daily_game_picks_v161 as old_hr
import mlb_daily_game_picks_v162 as new_hr

# V1.9.6's chain resolves the V1.6.1 module object at render time.
# Replace only that render target with the V1.6.2-patched renderer.
old_hr.render_daily_game_picks = new_hr.render_daily_game_picks

VERSION = "MLB Daily Game Picks V1.9.7 • RESILIENT HOME RUN LINEUP INTAKE"
render_daily_game_picks = base.render_daily_game_picks
