"""MLB Daily Game Picks V1.9.6 bridge — adds Home Run V1.6.1.

Preserves Moneyline V1.9.2, Pitcher K V1.8.2, and H+R+RBI V1.7.1, then replaces
only the older Home Run V1.6 render layer with the new V1.6.1 full-slate/resumable
connector. Calibrated HR V1.1 production probability math is unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v195 as base
import mlb_daily_game_picks_v16 as old_hr
import mlb_daily_game_picks_v161 as new_hr

old_hr.render_daily_game_picks = new_hr.render_daily_game_picks

VERSION = "MLB Daily Game Picks V1.9.6 • HOME RUN V1.6.1 FULL-SLATE CONNECTOR"
render_daily_game_picks = base.render_daily_game_picks
