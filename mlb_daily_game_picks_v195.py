"""MLB Daily Game Picks V1.9.5 bridge — adds H+R+RBI V1.7.1.

Preserves Moneyline V1.9.2 and Pitcher K V1.8.2, then replaces only the older
H+R+RBI V1.7 render layer with the new V1.7.1 full-slate/resumable connector.
Production math is unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v194 as base
import mlb_daily_game_picks_v17 as old_hrrbi
import mlb_daily_game_picks_v171 as new_hrrbi

old_hrrbi.render_daily_game_picks = new_hrrbi.render_daily_game_picks

VERSION = "MLB Daily Game Picks V1.9.5 • H+R+RBI V1.7.1 FULL-SLATE CONNECTOR"
render_daily_game_picks = base.render_daily_game_picks
