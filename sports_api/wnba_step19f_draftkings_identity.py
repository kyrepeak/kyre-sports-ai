"""WNBA Step 19F: strict sportsbook live-surface compatibility.

This layer normalizes a small set of provider presentation differences observed
on the certified public WNBA surfaces without relaxing any frozen Step11/Step12
identity, readiness, projection, persistence, or wagering guardrail.

Certified live differences handled here:

* DraftKings displays ``PHO Mercury`` while the official/internal registry uses
  ``PHX`` / ``Phoenix Mercury``.
* FanDuel event times are UTC instants although the WNBA page is requested in
  ``America/New_York``; slate membership therefore uses the Eastern date.
* FanDuel's event-page endpoint selects player tabs with stable slugs such as
  ``player-points`` rather than the numeric layout card id.
* FanDuel exposes Over/Under in ``runner.result.type`` with the threshold in
  ``runner.handicap`` on the live player-prop surface.
* FanDuel player tabs also contain alternate one-way markets. Step11C's scope
  remains exact-line two-way Over/Under props, so only markets carrying a
  complete parseable O/U pair and an explicit player-market surface are treated
  as identity-bearing player props.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel

SOURCE = "Kyre Sports API WNBA Step19F strict sportsbook live-surface compatibility"
MODEL_VERSION = "wnba_step19f_sportsbook_live_surface_v5"
EASTERN = ZoneInfo("America/New_York")

_PROVIDER_TEAM_ALIASES = {
    "pho mercury": "Phoenix Mercury",
}

_FANDUEL_PLAYER_TAB_SLUGS = {
    "player points": "player-points",
    "player assists": "player-assists",
    "player rebounds": "player-rebounds",
    "player combos": "player-combos",
}

# Live standard FanDuel two-way player totals use market types such as
# PLAYER_G_TOTAL_POINTS_WNBA. The position/slot token varies, while the exact
# total-stat surface remains stable. Alternate milestone markets do not match
# this shape and still fail closed unless they independently satisfy the frozen
# declaration contract.
_FANDUEL_STANDARD_PLAYER_TOTAL_TYPE_RE = re.compile(
    r"^PLAYER_[A-Z0-9]+_TOTAL_[A-Z0-9_()+]+_WNBA$",
    flags=re.I,
)

_ORIGINAL_DK_TEAM_IDENTITY_KEY = draftkings._team_identity_key
_ORIGINAL_FD_EVENT_DATE = fanduel._event_date
_ORIGINAL_FD_RELEVANT_TAB_IDS = fanduel._relevant_tab_ids
_ORIGINAL_FD_RUNNER_SIDE_LINE = fanduel._runner_side_line
_ORIGINAL_FD_DECLARES_PLAYER_MARKET = fanduel._declares_player_market
_INSTALLED = False


def team_identity_key_step19f(value: Any) -> str:
    raw_key = draftkings._name_key(value)
    canonical_name = _PROVIDER_TEAM_ALIASES.get(raw_key)
    if canonical_name is not None:
        return _ORIGINAL_DK_TEAM_IDENTITY_KEY(canonical_name)
    return _ORIGINAL_DK_TEAM_IDENTITY_KEY(value)


def fanduel_event_date_step19f(event: Any) -> str | None:
    if not isinstance(event, Mapping):
        return None
    raw = event.get("openDate") or event.get("startTime") or event.get("startEventDate")
    if raw is None:
        return None
    try:
        instant = fanduel._utc(raw, "FanDuel event time")
    except ValueError:
        return None
    return instant.astimezone(EASTERN).date().isoformat()


def fanduel_relevant_tab_ids_step19f(document: Mapping[str, Any]) -> list[str]:
    """Return the exact FanDuel player-tab slugs accepted by event-page."""
    layout = document.get("layout") or {}
    if not isinstance(layout, Mapping):
        return []
    rows = fanduel._iter_mapping_or_list(layout.get("tabs"))
    slugs: list[str] = []
    for tab in rows:
        title = fanduel._clean(tab.get("title") or tab.get("name") or tab.get("displayName")).casefold()
        slug = _FANDUEL_PLAYER_TAB_SLUGS.get(title)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs[: fanduel.MAX_RELEVANT_TABS_PER_EVENT]


def fanduel_runner_side_line_step19f(runner: Mapping[str, Any]) -> tuple[str, float] | None:
    """Read the frozen shapes first, then the certified nested-result shape."""
    existing = _ORIGINAL_FD_RUNNER_SIDE_LINE(runner)
    if existing is not None:
        return existing

    result = runner.get("result")
    if not isinstance(result, Mapping):
        return None
    side = fanduel._clean(result.get("type")).casefold()
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


def _fanduel_has_explicit_player_surface(
    market: Mapping[str, Any],
    runners: Sequence[Mapping[str, Any]],
) -> bool:
    if _ORIGINAL_FD_DECLARES_PLAYER_MARKET(market, runners):
        return True
    market_type = fanduel._clean(market.get("marketType") or market.get("type"))
    if _FANDUEL_STANDARD_PLAYER_TOTAL_TYPE_RE.fullmatch(market_type):
        return True
    return any(runner.get("isPlayerSelection") is True for runner in runners)


def fanduel_declares_player_market_step19f(
    market: Mapping[str, Any],
    runners: Sequence[Mapping[str, Any]],
) -> bool:
    """Declare identity only for explicit two-way threshold player markets."""
    lines: dict[float, set[str]] = defaultdict(set)
    for runner in runners:
        parsed = fanduel_runner_side_line_step19f(runner)
        if parsed is None:
            continue
        side, line = parsed
        lines[line].add(side)
    complete_pair = any(sides == {"over", "under"} for sides in lines.values())
    if not complete_pair:
        return False
    return _fanduel_has_explicit_player_surface(market, runners)


def install_step19f_draftkings_identity() -> dict[str, Any]:
    """Install the complete Step19F compatibility set idempotently."""
    global _INSTALLED
    if draftkings._team_identity_key is not team_identity_key_step19f:
        draftkings._team_identity_key = team_identity_key_step19f
    if fanduel._event_date is not fanduel_event_date_step19f:
        fanduel._event_date = fanduel_event_date_step19f
    if fanduel._relevant_tab_ids is not fanduel_relevant_tab_ids_step19f:
        fanduel._relevant_tab_ids = fanduel_relevant_tab_ids_step19f
    if fanduel._runner_side_line is not fanduel_runner_side_line_step19f:
        fanduel._runner_side_line = fanduel_runner_side_line_step19f
    if fanduel._declares_player_market is not fanduel_declares_player_market_step19f:
        fanduel._declares_player_market = fanduel_declares_player_market_step19f
    _INSTALLED = True
    return INSTALLATION


INSTALLATION = {
    "source": SOURCE,
    "model_version": MODEL_VERSION,
    "installed": lambda: _INSTALLED,
    "strict_alias_count": len(_PROVIDER_TEAM_ALIASES),
    "fanduel_slate_timezone": "America/New_York",
    "fanduel_player_tab_slugs": tuple(_FANDUEL_PLAYER_TAB_SLUGS.values()),
    "fanduel_nested_result_type_supported": True,
    "fanduel_two_way_scope_preserved": True,
    "official_schedule_reconciliation_modified": False,
    "game_uniqueness_relaxed": False,
    "slate_date_bounds_relaxed": False,
    "player_identity_relaxed": False,
    "projection_logic_modified": False,
    "readiness_relaxed": False,
    "wagering_enabled": False,
}


__all__ = [
    "EASTERN",
    "INSTALLATION",
    "MODEL_VERSION",
    "SOURCE",
    "fanduel_declares_player_market_step19f",
    "fanduel_event_date_step19f",
    "fanduel_relevant_tab_ids_step19f",
    "fanduel_runner_side_line_step19f",
    "install_step19f_draftkings_identity",
    "team_identity_key_step19f",
]
