"""CFB player-prop sportsbook compatibility bridge.

Page 2 historically imports this module as its secondary transport. Keep that
public contract stable while repairing coverage with field-specific sources:

1) direct FanDuel player props with exact verified-game binding;
2) the app's existing Odds-API.io player-prop gap-fill.

SportsGameOdds remains an independent multi-book source in the Page-2 market
owner. Each transport fails soft; one failed source never erases good rows from
the other. No synthetic line is created and missing values remain missing.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import cfb_player_props_fanduel_bound_v2 as direct_fanduel
import cfb_player_props_odds_api_v1 as odds_api


def fetch_fanduel_cfb_player_props(
    slate_games: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        rows.extend(direct_fanduel.fetch_fanduel_cfb_player_props(slate_games) or [])
    except Exception:
        pass
    try:
        rows.extend(odds_api.fetch_odds_api_cfb_player_props(slate_games) or [])
    except Exception:
        pass
    return rows


__all__ = ["fetch_fanduel_cfb_player_props"]
