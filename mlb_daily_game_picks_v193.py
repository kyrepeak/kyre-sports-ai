"""MLB Daily Game Picks V1.9.3 bridge — Moneyline V1.9.2 + Pitcher K V1.8.2.

Keeps the proven V1.9.2 full-slate Moneyline connector and swaps only the older
Pitcher K V1.8.1 render layer for the new V1.8.2 full-slate/resumable connector.
Production probability and Monte Carlo math remain unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v192 as base
import mlb_daily_game_picks_v181 as old_pitcher_k
import mlb_daily_game_picks_v182 as new_pitcher_k

# V1.9.x calls the V1.8.1 module object at render time. Replacing that module's
# render function upgrades only Pitcher K while preserving the already-working
# Moneyline V1.9.2 connector and all lower-market connectors.
old_pitcher_k.render_daily_game_picks = new_pitcher_k.render_daily_game_picks

VERSION = "MLB Daily Game Picks V1.9.3 • MONEYLINE V1.9.2 + PITCHER K V1.8.2"
render_daily_game_picks = base.render_daily_game_picks
