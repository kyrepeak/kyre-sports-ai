"""Step 19A live-provider compatibility shims for frozen WNBA provider seams.

This module is intentionally additive. It does not edit frozen Step 11 provider or
scheduler source files. Instead it installs narrowly-scoped compatibility helpers
for current anonymous sportsbook payloads while preserving strict official
identity reconciliation and two-book safety requirements.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any
from zoneinfo import ZoneInfo

import sports_api.wnba_step11_draftkings_provider as _dk
import sports_api.wnba_step11_fanduel_provider as _fd

MODEL_VERSION = "wnba_step19a_live_provider_compat_v3"
_ET = ZoneInfo("America/New_York")

_ORIGINAL_DK_TEAM_IDENTITY_KEY = _dk._team_identity_key
_ORIGINAL_FD_TEAM_IDENTITY_KEY = _fd._team_identity_key
_ORIGINAL_FD_EVENT_DATE = _fd._event_date
_ORIGINAL_FD_RELEVANT_TAB_IDS = _fd._relevant_tab_ids
_ORIGINAL_FD_RUNNER_SIDE_LINE = _fd._runner_side_line
_ORIGINAL_FD_DECLARES_PLAYER_MARKET = _fd._declares_player_market

_FANDUEL_PLAYER_TAB_SLUGS = {
    "player points": "player-points",
    "player assists": "player-assists",
    "player rebounds": "player-rebounds",
    "player combos": "player-combos",
    "player props": "player-props",
}


def _phoenix_alias(value: Any, original):
    key = _dk._name_key(value)
    if key == "pho mercury":
        return original("Phoenix Mercury")
    return original(value)


def draftkings_team_identity_key(value: Any) -> str:
    return _phoenix_alias(value, _ORIGINAL_DK_TEAM_IDENTITY_KEY)


def fanduel_team_identity_key(value: Any) -> str:
    key = _fd._name_key(value)
    if key == "pho mercury":
        return _ORIGINAL_FD_TEAM_IDENTITY_KEY("Phoenix Mercury")
    return _ORIGINAL_FD_TEAM_IDENTITY_KEY(value)


def fanduel_event_date_eastern(event: Mapping[str, Any]) -> str | None:
    raw = event.get("openDate") or event.get("startTime") or event.get("startEventDate")
    if raw is None:
        return None
    try:
        return _fd._utc(raw, "FanDuel event time").astimezone(_ET).date().isoformat()
    except ValueError:
        return None


def fanduel_relevant_tab_slugs(document: Mapping[str, Any]) -> list[str]:
    layout = document.get("layout") or {}
    if not isinstance(layout, Mapping):
        return []
    rows = _fd._iter_mapping_or_list(layout.get("tabs"))
    slugs: list[str] = []
    for tab in rows:
        title = _fd._clean(tab.get("title") or tab.get("name") or tab.get("displayName")).casefold()
        slug = _FANDUEL_PLAYER_TAB_SLUGS.get(title)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs[: _fd.MAX_RELEVANT_TABS_PER_EVENT]


def fanduel_runner_side_line_current(runner: Mapping[str, Any]) -> tuple[str, float] | None:
    legacy = _ORIGINAL_FD_RUNNER_SIDE_LINE(runner)
    if legacy is not None:
        return legacy

    result = runner.get("result") or {}
    side = ""
    if isinstance(result, Mapping):
        side = _fd._clean(result.get("type")).casefold()
    if side not in {"over", "under"}:
        return None

    raw_line = runner.get("handicap") if runner.get("handicap") is not None else runner.get("line")
    try:
        line = float(raw_line)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(line):
        return None
    return side, round(line, 6)


def fanduel_declares_player_market_current(
    market: Mapping[str, Any],
    runners: Sequence[Mapping[str, Any]],
) -> bool:
    if _ORIGINAL_FD_DECLARES_PLAYER_MARKET(market, runners):
        return True
    market_type = _fd._clean(market.get("marketType") or market.get("type")).upper()
    if not market_type.startswith("PLAYER_"):
        return False
    parsed = [fanduel_runner_side_line_current(runner) for runner in runners]
    parsed = [item for item in parsed if item is not None]
    if len(parsed) != 2:
        return False
    sides = {side for side, _line in parsed}
    lines = {line for _side, line in parsed}
    return sides == {"over", "under"} and len(lines) == 1


def install_step19a_live_provider_compat() -> dict[str, Any]:
    _dk._team_identity_key = draftkings_team_identity_key
    _fd._team_identity_key = fanduel_team_identity_key
    _fd._event_date = fanduel_event_date_eastern
    _fd._relevant_tab_ids = fanduel_relevant_tab_slugs
    _fd._runner_side_line = fanduel_runner_side_line_current
    _fd._declares_player_market = fanduel_declares_player_market_current
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "draftkings_phoenix_alias_installed": True,
        "fanduel_eastern_slate_date_installed": True,
        "fanduel_player_tab_slug_transport_installed": True,
        "fanduel_nested_result_side_parser_installed": True,
        "fanduel_two_way_player_market_evidence_installed": True,
        "frozen_step11a_source_modified": False,
        "frozen_step11c_source_modified": False,
        "frozen_step11d_source_modified": False,
    }


INSTALLATION = install_step19a_live_provider_compat()

__all__ = [
    "INSTALLATION",
    "MODEL_VERSION",
    "draftkings_team_identity_key",
    "fanduel_declares_player_market_current",
    "fanduel_event_date_eastern",
    "fanduel_relevant_tab_slugs",
    "fanduel_runner_side_line_current",
    "fanduel_team_identity_key",
    "install_step19a_live_provider_compat",
]
