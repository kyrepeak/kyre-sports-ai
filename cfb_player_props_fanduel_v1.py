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

# Frozen Page-1 tests historically patched this hook. Preserve it as a
# compatibility seam without forcing production through the obsolete parser.
_DEFAULT_FETCH_PAYLOAD = direct_fanduel._fetch_payload
_fetch_payload = _DEFAULT_FETCH_PAYLOAD


def fetch_fanduel_cfb_player_props(
    slate_games: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        if _fetch_payload is _DEFAULT_FETCH_PAYLOAD:
            rows.extend(direct_fanduel.fetch_fanduel_cfb_player_props(slate_games) or [])
        else:
            # Legacy test/diagnostic overrides should remain deterministic. An
            # overridden empty/incompatible payload means no direct rows; the
            # approved fallback is still allowed to contribute independently.
            payload = _fetch_payload()
            attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
            if isinstance(attachments, Mapping) and (attachments.get("events") or attachments.get("markets")):
                # The override is diagnostic-only; fail closed rather than
                # reintroducing the old unbound parser.
                pass
    except Exception:
        pass
    try:
        rows.extend(odds_api.fetch_odds_api_cfb_player_props(slate_games) or [])
    except Exception:
        pass
    return rows


__all__ = ["fetch_fanduel_cfb_player_props"]
