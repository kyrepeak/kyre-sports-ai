"""NFL Rushing Yards V15 — Phoenix, Arizona kickoff-time display.

V15 is additive over certified V14. It changes only the visible scheduled NFL
kickoff time on Rushing Yards game cards from Eastern display text to Phoenix,
Arizona local time using IANA timezone conversion (America/New_York ->
America/Phoenix).

The verified ESPN schedule/event identity remains unchanged. Projection math,
market semantics, matchup tiers, rankings, exact-ID behavior, Passing Yards,
and sportsbook influence are untouched. Sportsbook projection influence remains
exactly 0.0%.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from zoneinfo import ZoneInfo

import nfl_rushing_yards_hub_v1 as context_page
import nfl_rushing_yards_hub_v14 as prior

MODEL_VERSION = "NFL RUSHING YARDS V15 • PHOENIX GAME TIMES"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v14"
DISPLAY_ONLY = True
TIMEZONE_DISPLAY_ONLY = True
PHOENIX_TZ_NAME = "America/Phoenix"
PHOENIX_TZ_LABEL = "MST"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ET = ZoneInfo("America/New_York")
_PHOENIX = ZoneInfo(PHOENIX_TZ_NAME)
_ORIGINAL_GAME_CARD_V1 = context_page._game_card


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _clock_label(value: datetime) -> str:
    hour = value.strftime("%I").lstrip("0") or "0"
    return f"{hour}:{value.strftime('%M')} {value.strftime('%p')} {PHOENIX_TZ_LABEL}"


def _phoenix_kickoff(row: Any) -> dict[str, str] | None:
    """Return Phoenix display labels from the verified ET slate row.

    The frozen NFL slate currently stores the authoritative ESPN kickoff as an
    ET calendar date plus a formatted ET clock. V15 reconstructs that aware ET
    datetime, converts it with zoneinfo, and returns display-only Phoenix labels.
    """
    try:
        game_date = _safe(row.get("game_date"))
        tip_et = _safe(row.get("tip_et"))
    except Exception:
        return None
    if not game_date or not tip_et or tip_et.upper().startswith("TBD"):
        return None

    clock = re.sub(r"\s+(?:ET|EST|EDT)\s*$", "", tip_et, flags=re.IGNORECASE).strip()
    try:
        eastern = datetime.strptime(f"{game_date} {clock}", "%Y-%m-%d %I:%M %p").replace(tzinfo=_ET)
        phoenix = eastern.astimezone(_PHOENIX)
    except Exception:
        return None

    label = _clock_label(phoenix)
    return {
        "clock": label,
        "clock_with_location": f"{label} • Phoenix",
        "status": f"{phoenix.month}/{phoenix.day} - {label}",
        "date": phoenix.strftime("%Y-%m-%d"),
        "timezone": PHOENIX_TZ_NAME,
    }


def _phoenix_game_card_v15(row: Any) -> str:
    """Render the frozen V1 game card with Phoenix-only display substitutions."""
    labels = _phoenix_kickoff(row)
    if labels is None:
        return _ORIGINAL_GAME_CARD_V1(row)

    try:
        display_row = row.copy()
    except Exception:
        display_row = dict(row)

    display_row["tip_et"] = labels["clock_with_location"]
    state = _safe(display_row.get("state"), "pre").lower()
    if state == "pre":
        display_row["status"] = labels["status"]
    return _ORIGINAL_GAME_CARD_V1(display_row)


def render_nfl_rushing_yards_hub() -> None:
    original_game_card = context_page._game_card
    context_page._game_card = _phoenix_game_card_v15
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        context_page._game_card = original_game_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V15 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PHOENIX_TZ_LABEL",
    "PHOENIX_TZ_NAME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TIMEZONE_DISPLAY_ONLY",
    "_phoenix_game_card_v15",
    "_phoenix_kickoff",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
