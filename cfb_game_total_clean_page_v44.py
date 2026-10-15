"""CFB Game Total clean page V44 — date-selection RuntimeError repair.

Additive successor to frozen V43. V42 remains the selected-day snapshot owner and
V43 remains the native game-card owner. This compatibility layer changes only
one failure mode: if a frozen downstream caller presents a stale slate date
during the same Page-1 render, it receives the already-authoritative selected-day
snapshot instead of surfacing a RuntimeError.

The selected Phoenix day still performs exactly one underlying game load. No new
provider path, endpoint, model, projection, probability, sportsbook influence,
card presentation, market ownership, other-sport behavior, or Page-2 behavior is
added or changed.
"""
from __future__ import annotations

from threading import RLock

import cfb_game_total_clean_page_v42 as snapshot_owner
import cfb_game_total_clean_page_v43 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V44 • DATE SELECTION RUNTIME REPAIR STEP 2"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v43"
ACTIVE_MARKER = "CFB GAME TOTAL • DATE SELECTION RUNTIME REPAIR STEP 2 ACTIVE"
DATE_RUNTIME_REPAIR_MARKER = "CFB_GAME_TOTAL_DATE_RUNTIME_REPAIR_STEP2_ACTIVE"
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
STALE_DOWNSTREAM_DAY_USES_PINNED_SNAPSHOT = True
_RUNTIME_REPAIR_LOCK = RLock()


def _render_snapshot_without_stale_date_runtimeerror(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
):
    """Render frozen V41 with one selected-day snapshot for every downstream read."""
    with snapshot_owner._DATA_LOCK:
        selected_day = snapshot_owner.prior._selected_day()
        original_loader = snapshot_owner.games_owner._load_games
        snapshot = tuple(dict(game) for game in original_loader(selected_day))

        def snapshot_loader(requested_day):
            if requested_day != selected_day:
                requested_day = selected_day
            return [dict(game) for game in snapshot]

        snapshot_owner.games_owner._load_games = snapshot_loader
        try:
            return snapshot_owner.prior.render_game_total_hub(
                section_header,
                status_info,
                team_logo,
                h,
            )
        finally:
            snapshot_owner.games_owner._load_games = original_loader


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Temporarily replace only V42's stale-date failure seam, then restore it."""
    with _RUNTIME_REPAIR_LOCK:
        original_v42_render = snapshot_owner.render_game_total_hub
        snapshot_owner.render_game_total_hub = _render_snapshot_without_stale_date_runtimeerror
        try:
            return prior.render_game_total_hub(
                section_header,
                status_info,
                team_logo,
                h,
            )
        finally:
            snapshot_owner.render_game_total_hub = original_v42_render


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V44 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "DATE_RUNTIME_REPAIR_MARKER",
    "FROZEN_PRESENTATION",
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
    "STALE_DOWNSTREAM_DAY_USES_PINNED_SNAPSHOT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_render_snapshot_without_stale_date_runtimeerror",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
