"""WNBA Assists V19 same-day tip parser hotfix.

Preserves the complete Step-19 implementation and changes only the final pregame
recheck. Step 13 already verifies each accepted row against the exact current ET
slate using a timezone-aware ``tip_iso_et``. The downstream Step-18 payload,
however, carries the human display field ``TIP_ET`` (for example ``8:00 PM ET``)
without the date. V19's generic pandas parser can reject that display-only value,
which incorrectly labels every still-upcoming same-day game as started.

This wrapper teaches the Step-19 recheck to interpret a time-only ``TIP_ET`` as a
time on the current Eastern slate date. Past times still fail closed. Full ISO or
other date-bearing timestamps continue through the original timezone-aware path.
No projection, market, simulation, EV, ranking, or qualification math is changed.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import wnba_assists_hub_v19 as v19

_ET = ZoneInfo("America/New_York")


def _tip_is_upcoming_same_day(value) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False

    now = datetime.now(_ET)

    # Date-bearing timestamps: preserve the original strict timezone-aware logic.
    has_date = any(ch.isdigit() for ch in raw) and (
        "-" in raw or "/" in raw or "T" in raw.upper()
    )
    if has_date:
        try:
            ts = pd.to_datetime(raw, errors="raise")
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize(_ET)
            else:
                ts = ts.tz_convert(_ET)
            return bool(ts.to_pydatetime() > now)
        except Exception:
            return False

    # Step 13's display-only field is normally like "8:00 PM ET". Because Step
    # 18 is rebuilt from the current Step-13 render, its calendar date is the
    # current verified Eastern slate date; only the clock time needs restoring.
    cleaned = raw.upper().replace("EASTERN TIME", "").replace("ET", "").strip()
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            parsed_time = datetime.strptime(cleaned, fmt).time()
            tip = datetime.combine(now.date(), parsed_time, tzinfo=_ET)
            return bool(tip > now)
        except Exception:
            continue

    return False


# Patch only the V19 pregame helper used by _build_step19_edge_ev.
v19._tip_is_upcoming = _tip_is_upcoming_same_day

MODEL_VERSION = v19.MODEL_VERSION + " • SAME-DAY TIP HOTFIX"


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return v19.render_wnba_assists_hub(section_header, status_info, team_logo, h)
