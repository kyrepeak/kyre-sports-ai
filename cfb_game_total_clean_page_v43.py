"""CFB Game Total clean page V43 — native game-card ownership Step 6.

Additive successor to frozen V42. Step 5 remains the only selected-day data
owner. Step 6 promotes the already-certified Games on This Day presentation
chain as the native Page-1 game-card surface without creating a second loader,
provider path, model path, projection path, probability path, or Page-2 path.

Step 8 production certification proved that V14's historical default-selection
sync published the first game's event ID during the initial Page-1 render. That
made the selected-event router advance to Page 2 before a user tapped a card.
This owner now scopes one compatibility override to the Page-1 render: the
first game may remain the internal default selection, but Page 1 never writes
an event query on its own. User-tapped card hrefs remain the sole Page-1 source
of exact-event navigation.
"""
from __future__ import annotations

import cfb_game_total_clean_page_v14 as selector_owner
import cfb_game_total_clean_page_v42 as prior
from cfb_game_total_games_on_day_step1_layout_v1 import install_games_on_day_step1_layout
from cfb_game_total_games_on_day_step2_visual_v1 import install_games_on_day_step2_visual
from cfb_game_total_games_on_day_step3_details_v1 import install_games_on_day_step3_details
from cfb_game_total_games_on_day_step4_interaction_mobile_v1 import install_games_on_day_step4_interaction_mobile

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V43 • GAME CARDS STEP 6"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v42"
ACTIVE_MARKER = "CFB GAME TOTAL • GAME CARDS STEP 6 ACTIVE"
GAME_CARDS_MARKER = "CFB_GAME_TOTAL_GAME_CARDS_STEP6_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_CARD_UI = True
NETWORK_CALLS_ADDED = 0
NEW_PROVIDER_PATHS_ADDED = 0
CARDS_CONSUME_SELECTED_DAY_SNAPSHOT = True
FROZEN_CARD_PRESENTATION_REUSED = True
POST_PURGE_CARD_REBIND = True
PAGE1_AUTO_EVENT_QUERY_WRITE = False
FROZEN_CARD_CHAIN = (
    "cfb_game_total_games_on_day_step1_layout_v1",
    "cfb_game_total_games_on_day_step2_visual_v1",
    "cfb_game_total_games_on_day_step3_details_v1",
    "cfb_game_total_games_on_day_step4_interaction_mobile_v1",
)


def _sync_page1_matchup_without_auto_event(selected_day, games):
    """Keep the frozen default index without publishing a selected event URL."""
    if not games:
        return 0
    query_event_id = selector_owner._query_event_id()
    selected_index = selector_owner._selected_game_index(games, query_event_id)
    if selector_owner._selector_sync_event_id():
        selector_owner._clear_selector_sync()
    selector_owner.st.session_state[
        f"{selector_owner.MATCHUP_STATE_KEY_PREFIX}{selected_day.isoformat()}"
    ] = selected_index
    return selected_index


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Rebind frozen cards and prevent initial Page-1 selection from becoming navigation."""
    original_sync = selector_owner._sync_frozen_matchup_state
    selector_owner._sync_frozen_matchup_state = _sync_page1_matchup_without_auto_event
    try:
        install_games_on_day_step1_layout()
        install_games_on_day_step2_visual()
        install_games_on_day_step3_details()
        install_games_on_day_step4_interaction_mobile()
        return prior.render_game_total_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        selector_owner._sync_frozen_matchup_state = original_sync


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V43 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "CARDS_CONSUME_SELECTED_DAY_SNAPSHOT",
    "FROZEN_CARD_CHAIN",
    "FROZEN_CARD_PRESENTATION_REUSED",
    "FROZEN_PRESENTATION",
    "GAME_CARDS_MARKER",
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
    "PAGE1_AUTO_EVENT_QUERY_WRITE",
    "POST_PURGE_CARD_REBIND",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_sync_page1_matchup_without_auto_event",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
