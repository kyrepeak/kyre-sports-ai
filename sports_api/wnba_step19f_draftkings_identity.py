"""WNBA Step 19F: strict sportsbook event identity compatibility.

Two live provider identity differences are normalized here without relaxing any
of the frozen Step11/Step12 safety gates:

* DraftKings uses ``PHO Mercury`` while the official/internal registry uses
  ``PHX`` / ``Phoenix Mercury``.
* FanDuel event timestamps are UTC instants even though its WNBA page is
  requested with ``timezone=America/New_York``.  Slate membership therefore
  must use the New York calendar date, not the raw UTC calendar date.

The layer changes only provider display identity/date interpretation. Official
schedule uniqueness, player identity, slate bounds, projections, persistence,
and wagering controls remain unchanged.
"""
from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel

SOURCE = "Kyre Sports API WNBA Step19F strict sportsbook event identity compatibility"
MODEL_VERSION = "wnba_step19f_sportsbook_event_identity_v2"
EASTERN = ZoneInfo("America/New_York")

_PROVIDER_TEAM_ALIASES = {
    "pho mercury": "Phoenix Mercury",
}

_ORIGINAL_DK_TEAM_IDENTITY_KEY = draftkings._team_identity_key
_ORIGINAL_FD_EVENT_DATE = fanduel._event_date
_INSTALLED = False


def team_identity_key_step19f(value: Any) -> str:
    raw_key = draftkings._name_key(value)
    canonical_name = _PROVIDER_TEAM_ALIASES.get(raw_key)
    if canonical_name is not None:
        return _ORIGINAL_DK_TEAM_IDENTITY_KEY(canonical_name)
    return _ORIGINAL_DK_TEAM_IDENTITY_KEY(value)


def fanduel_event_date_step19f(event: Any) -> str | None:
    if not isinstance(event, dict) and not hasattr(event, "get"):
        return None
    raw = event.get("openDate") or event.get("startTime") or event.get("startEventDate")
    if raw is None:
        return None
    try:
        instant = fanduel._utc(raw, "FanDuel event time")
    except ValueError:
        return None
    return instant.astimezone(EASTERN).date().isoformat()


def install_step19f_draftkings_identity() -> dict[str, Any]:
    """Install the complete Step19F provider compatibility set idempotently."""
    global _INSTALLED
    if draftkings._team_identity_key is not team_identity_key_step19f:
        draftkings._team_identity_key = team_identity_key_step19f
    if fanduel._event_date is not fanduel_event_date_step19f:
        fanduel._event_date = fanduel_event_date_step19f
    _INSTALLED = True
    return INSTALLATION


INSTALLATION = {
    "source": SOURCE,
    "model_version": MODEL_VERSION,
    "installed": lambda: _INSTALLED,
    "strict_alias_count": len(_PROVIDER_TEAM_ALIASES),
    "fanduel_slate_timezone": "America/New_York",
    "official_schedule_reconciliation_modified": False,
    "game_uniqueness_relaxed": False,
    "slate_date_bounds_relaxed": False,
    "player_identity_relaxed": False,
    "projection_logic_modified": False,
    "wagering_enabled": False,
}


__all__ = [
    "EASTERN",
    "INSTALLATION",
    "MODEL_VERSION",
    "SOURCE",
    "fanduel_event_date_step19f",
    "install_step19f_draftkings_identity",
    "team_identity_key_step19f",
]
