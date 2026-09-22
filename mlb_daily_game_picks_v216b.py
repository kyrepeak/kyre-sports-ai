"""MLB Daily Game Picks V2.1.6b — cache-breaking hotfix entrypoint.

Forces Streamlit/Python to reload the V2.1.6 renderer from disk so an already-running
Streamlit process cannot keep serving the pre-hotfix module from sys.modules.
Presentation/workflow only; production model math and simulation depths are unchanged.
"""
from __future__ import annotations

from importlib import reload

import mlb_daily_game_picks_v216 as _v216

# Streamlit reruns can retain imported modules in memory. Explicitly reload the
# renderer so the latest V2.1.6b implementation is executed even in a warm process.
_v216 = reload(_v216)

render_daily_game_picks = _v216.render_daily_game_picks
controller = _v216.controller
VERSION = "MLB Daily Game Picks V2.1.6b • CACHE-BREAK HOTFIX"
