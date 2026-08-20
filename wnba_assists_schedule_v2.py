"""WNBA Assists Step 2 schedule repair.

Uses the current official WNBA public schedule CDN endpoint. This module is a
thin compatibility layer over Step-2 V1 so no downstream Assists logic changes.
"""
from __future__ import annotations

import wnba_assists_schedule_v1 as _v1

# The current WNBA public schedule feed is the unsuffixed ScheduleLeagueV2 CDN.
# The prior Step-2 module used the _1 variant, which returned HTTP 200 but no
# 2026 WNBA same-day rows for the selected slate.
_v1.WNBA_SCHEDULE_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"

load_verified_wnba_slate = _v1.load_verified_wnba_slate
WNBA_TEAMS_2026 = _v1.WNBA_TEAMS_2026
WNBA_SCHEDULE_URL = _v1.WNBA_SCHEDULE_URL
ESPN_SCOREBOARD_URL = _v1.ESPN_SCOREBOARD_URL

__all__ = [
    "load_verified_wnba_slate",
    "WNBA_TEAMS_2026",
    "WNBA_SCHEDULE_URL",
    "ESPN_SCOREBOARD_URL",
]
