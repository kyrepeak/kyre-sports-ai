"""Display-only Phoenix kickoff conversion for NFL Passing Yards.

Converts the verified NFL slate's Eastern calendar date + formatted Eastern
kickoff clock into Phoenix, Arizona local time with IANA zoneinfo. This module
owns no schedule fetch, projection, probability, market, edge, or model logic.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from zoneinfo import ZoneInfo

PHOENIX_TZ_NAME = "America/Phoenix"
PHOENIX_TZ_LABEL = "MST"

_ET = ZoneInfo("America/New_York")
_PHOENIX = ZoneInfo(PHOENIX_TZ_NAME)


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _clock_label(value: datetime) -> str:
    hour = value.strftime("%I").lstrip("0") or "0"
    return f"{hour}:{value.strftime('%M')} {value.strftime('%p')} {PHOENIX_TZ_LABEL}"


def phoenix_kickoff(game_date: Any, tip_et: Any) -> dict[str, str] | None:
    """Return Phoenix display labels from a verified ET date + kickoff clock."""
    day = _safe(game_date)
    clock_et = _safe(tip_et)
    if not day or not clock_et or clock_et.upper().startswith("TBD"):
        return None

    clock = re.sub(r"\s+(?:ET|EST|EDT)\s*$", "", clock_et, flags=re.IGNORECASE).strip()
    try:
        eastern = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %I:%M %p").replace(tzinfo=_ET)
        phoenix = eastern.astimezone(_PHOENIX)
    except Exception:
        return None

    label = _clock_label(phoenix)
    return {
        "clock": label,
        "clock_with_location": f"{label} • Phoenix",
        "date": phoenix.strftime("%Y-%m-%d"),
        "timezone": PHOENIX_TZ_NAME,
    }


__all__ = ["PHOENIX_TZ_LABEL", "PHOENIX_TZ_NAME", "phoenix_kickoff"]
