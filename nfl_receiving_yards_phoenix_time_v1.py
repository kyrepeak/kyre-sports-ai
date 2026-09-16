"""Display-only Phoenix-time formatter for Receiving Yards research labels."""
from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any
from zoneinfo import ZoneInfo

EASTERN_TZ_NAME = "America/New_York"
PHOENIX_TZ_NAME = "America/Phoenix"
PHOENIX_TZ_LABEL = "MST"

_EASTERN = ZoneInfo(EASTERN_TZ_NAME)
_PHOENIX = ZoneInfo(PHOENIX_TZ_NAME)
_TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s+(?:AM|PM))\s+(?:ET|EST|EDT)\b", re.IGNORECASE)


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def format_research_matchup_label(value: Any, game_date: Any) -> str:
    """Convert only the visible ET clock inside a research-matchup label."""
    text = str(value if value is not None else "")
    match = _TIME_RE.search(text)
    day = _coerce_date(game_date)
    if match is None or day is None:
        return text

    try:
        clock = match.group(1).upper()
        eastern = datetime.strptime(
            f"{day.isoformat()} {clock}", "%Y-%m-%d %I:%M %p"
        ).replace(tzinfo=_EASTERN)
        phoenix = eastern.astimezone(_PHOENIX)
    except Exception:
        return text

    hour = phoenix.strftime("%I").lstrip("0") or "0"
    replacement = f"{hour}:{phoenix.strftime('%M')} {phoenix.strftime('%p')} {PHOENIX_TZ_LABEL}"
    return f"{text[:match.start()]}{replacement}{text[match.end():]}"


__all__ = [
    "EASTERN_TZ_NAME",
    "PHOENIX_TZ_LABEL",
    "PHOENIX_TZ_NAME",
    "format_research_matchup_label",
]
