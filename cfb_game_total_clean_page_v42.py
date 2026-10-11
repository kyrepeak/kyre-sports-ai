"""CFB Game Total clean page V42 — games-on-day data Step 5.

Additive successor to frozen V41. This layer makes the Phoenix-selected day own
one authoritative games snapshot for the complete Page-1 render. It reuses the
existing frozen V14 game loader exactly once, then serves immutable-by-source
copies of that snapshot to the frozen downstream chain.

No provider, endpoint, model, projection, probability, sportsbook influence,
event-identity rule, card presentation, other-sport behavior, or Page-2 behavior
is added or changed.
"""
from __future__ import annotations

from threading import RLock

import cfb_game_total_clean_page_v14 as games_owner
import cfb_game_total_clean_page_v41 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V42 • GAMES ON DAY DATA STEP 5"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v41"
ACTIVE_MARKER = "CFB GAME TOTAL • GAMES ON DAY DATA STEP 5 ACTIVE"
GAMES_ON_DAY_DATA_MARKER = "CFB_GAME_TOTAL_GAMES_ON_DAY_DATA_STEP5_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_CARD_UI = False
NETWORK_CALLS_ADDED = 0
NEW_PROVIDER_PATHS_ADDED = 0
SELECTED_DAY_SNAPSHOT_OWNS_GAME_LOADING = True

_DATA_LOCK = RLock()


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Pin one selected-day game snapshot, render frozen V41, then restore."""
    with _DATA_LOCK:
        selected_day = prior._selected_day()
        original_loader = games_owner._load_games
        snapshot = tuple(dict(game) for game in original_loader(selected_day))

        def snapshot_loader(requested_day):
            if requested_day != selected_day:
                raise RuntimeError(
                    "Step 5 selected-day snapshot rejected a different slate date: "
                    f"expected {selected_day}, got {requested_day}"
                )
            return [dict(game) for game in snapshot]

        games_owner._load_games = snapshot_loader
        try:
            return prior.render_game_total_hub(
                section_header,
                status_info,
                team_logo,
                h,
            )
        finally:
            games_owner._load_games = original_loader


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V42 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "GAMES_ON_DAY_DATA_MARKER",
    "MARKET",
    "MAY_MODIFY_CARD_UI",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "NEW_PROVIDER_PATHS_ADDED",
    "SELECTED_DAY_SNAPSHOT_OWNS_GAME_LOADING",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
