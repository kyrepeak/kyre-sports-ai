"""CFB Game Total Clean Page V12 — V161 official ESPN identity repair.

Additive successor to V11. V12 changes only the identity extractors used by
V11's already-verified sportsbook display path so the runtime keys produced by
the frozen Game Total evidence adapter are recognized:
- espn_event_id
- away_espn_team_id / home_espn_team_id

All V11 day navigation, freshness checks, FanDuel market semantics, presentation,
and frozen V160/V159 model behavior remain unchanged.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_game_total_clean_page_v11 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V12 • V161 OFFICIAL ESPN IDENTITY"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v11"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = prior.ACTIVE_MARKER
V161_REQUIRED_MARKERS = prior.V161_REQUIRED_MARKERS


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _game_id(display_game: Mapping[str, Any]) -> str:
    for key in ("espn_event_id", "event_id", "game_id", "id"):
        text = _clean(display_game.get(key))
        if text:
            return text
    return ""


def _team_id(display_game: Mapping[str, Any], side: str) -> str:
    nested = display_game.get(side)
    if isinstance(nested, Mapping):
        for key in ("espn_team_id", "team_id", "id"):
            text = _clean(nested.get(key))
            if text:
                return text
    for key in (
        f"{side}_espn_team_id",
        f"{side}_team_id",
        f"{side}_id",
    ):
        text = _clean(display_game.get(key))
        if text:
            return text
    return ""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    original_game_id = prior._game_id
    original_team_id = prior._team_id
    prior._game_id = _game_id
    prior._team_id = _team_id
    try:
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        prior._game_id = original_game_id
        prior._team_id = original_team_id


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V161 Game Total V12 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "V161_REQUIRED_MARKERS",
    "render_cfb_hub",
    "render_game_total_hub",
]
