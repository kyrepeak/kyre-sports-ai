"""MLB Daily Game Picks V1.9.2 fresh-import bridge.

Forces Streamlit to reload the updated V1.9.2 Moneyline connector instead of
reusing an already-imported V1.9.1 module from Python's in-process module cache.
Production model math is unchanged.
"""
from __future__ import annotations

import importlib
import mlb_daily_game_picks_v19 as _v19

base = importlib.reload(_v19)
VERSION = "MLB Daily Game Picks V1.9.2 • FRESH IMPORT"
render_daily_game_picks = base.render_daily_game_picks
