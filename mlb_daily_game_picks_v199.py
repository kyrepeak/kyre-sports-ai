"""MLB Daily Game Picks V1.9.9 bridge — adds bounded 1+ Hit V1.5.2.

Preserves Moneyline V1.9.2, Pitcher K V1.8.2, H+R+RBI V1.7.1, and Home Run
V1.6.2, then replaces only the 1+ Hit V1.5.1 render layer with V1.5.2 bounded
game-batched orchestration. V2.1 hit probability and calibration math remain unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v198 as base
import mlb_daily_game_picks_v151 as old_hit
import mlb_daily_game_picks_v152 as new_hit

old_hit.render_daily_game_picks = new_hit.render_daily_game_picks

VERSION = "MLB Daily Game Picks V1.9.9 • 1+ HIT V1.5.2 BOUNDED GAME-BATCHED CONNECTOR"
render_daily_game_picks = base.render_daily_game_picks
