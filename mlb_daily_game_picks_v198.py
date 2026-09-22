"""MLB Daily Game Picks V1.9.8 bridge — adds 1+ Hit V1.5.1 full-slate coverage.

Preserves Moneyline V1.9.2, Pitcher K V1.8.2, H+R+RBI V1.7.1, Home Run
V1.6.2 resilient intake, and replaces only the older one-shot 1+ Hit V1.5 render
layer with V1.5.1 resumable full-slate coverage validation. V2.1 hit probability
and calibration math remain unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v197 as base
import mlb_daily_game_picks_v15 as old_hit
import mlb_daily_game_picks_v151 as new_hit

old_hit.render_daily_game_picks = new_hit.render_daily_game_picks

VERSION = "MLB Daily Game Picks V1.9.8 • 1+ HIT V1.5.1 FULL-SLATE CONNECTOR"
render_daily_game_picks = base.render_daily_game_picks
