"""WNBA Assists V19 same-day tip parser hotfix V2.

Preserves the complete Step-19 implementation and changes only the final pregame
recheck. Step 13 already verifies accepted rows against the exact current ET
slate. Downstream Step 18 carries the human display field ``TIP_ET`` (for example
``8:00 PM ET``) without a calendar date.

The first hotfix still had one parser bug: it treated any raw value containing
``T`` as date-bearing. The timezone suffix ``ET`` itself contains the letter T,
so display values such as ``8:00 PM ET`` were incorrectly routed into the
full-datetime parser and then failed closed as "started".

V2 detects a date only from an actual numeric calendar-date pattern. Time-only
ET/EST/EDT values are explicitly attached to the current Eastern slate date.
Past times still fail closed. Full ISO/date-bearing timestamps retain strict
timezone-aware parsing. No projection, market, simulation, probability, EV,
ranking, or qualification math is changed.
"""
from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

import pandas as pd

import wnba_assists_hub_v19 as v19

_ET = ZoneInfo("America/New_York")
_DATE_PATTERN = re.compile(r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})")
_TRAILING_EASTERN = re.compile(r"\s+(?:ET|EST|EDT|EASTERN\s+TIME)\s*$", re.IGNORECASE)


def _parse_date_bearing_tip(raw: str, now: datetime) -> bool:
    """Parse a value that contains a real calendar date, preserving timezone."""
    candidate = str(raw or "").strip()
    if not candidate:
        return False

    # A display timestamp can include a literal ET/EST/EDT suffix that pandas
    # does not consistently interpret. Strip only that suffix; numeric/ISO
    # offsets remain untouched and therefore authoritative.
    candidate = _TRAILING_EASTERN.sub("", candidate).strip()
    try:
        ts = pd.to_datetime(candidate, errors="raise")
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(_ET)
        else:
            ts = ts.tz_convert(_ET)
        return bool(ts.to_pydatetime() > now)
    except Exception:
        return False


def _parse_same_day_clock_tip(raw: str, now: datetime) -> bool:
    """Attach a display-only Eastern clock time to today's verified ET slate."""
    cleaned = str(raw or "").strip()
    cleaned = _TRAILING_EASTERN.sub("", cleaned).strip()
    if not cleaned:
        return False

    for fmt in ("%I:%M %p", "%I:%M:%S %p", "%I %p", "%H:%M", "%H:%M:%S"):
        try:
            parsed_time = datetime.strptime(cleaned, fmt).time()
            tip = datetime.combine(now.date(), parsed_time, tzinfo=_ET)
            return bool(tip > now)
        except Exception:
            continue
    return False


def _tip_is_upcoming_same_day(value) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False

    now = datetime.now(_ET)

    # IMPORTANT: do not use `"T" in raw` to identify ISO timestamps because
    # time-only values such as "8:00 PM ET" also contain T via the ET suffix.
    if _DATE_PATTERN.search(raw):
        return _parse_date_bearing_tip(raw, now)

    return _parse_same_day_clock_tip(raw, now)


# Patch only the V19 pregame helper used by _build_step19_edge_ev.
v19._tip_is_upcoming = _tip_is_upcoming_same_day

MODEL_VERSION = v19.MODEL_VERSION + " • SAME-DAY TIP HOTFIX V2"


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return v19.render_wnba_assists_hub(section_header, status_info, team_logo, h)
