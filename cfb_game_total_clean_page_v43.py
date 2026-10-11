"""CFB Game Total clean page V43 — native game-card ownership Step 6.

Additive successor to frozen V42. Step 5 remains the only selected-day data
owner. Step 6 promotes the already-certified Games on This Day presentation
chain as the native Page-1 game-card surface without creating a second loader,
provider path, model path, projection path, probability path, or Page-2 path.

The exact-route renderer purges clean-page modules before importing V43, so V43
rebinds the full frozen Step-1/2/3/4 presentation chain after that purge and
then consumes the unchanged V42 selected-day snapshot through the prior render
path.
"""
from __future__ import annotations

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
FROZEN_CARD_CHAIN = (
    "cfb_game_total_games_on_day_step1_layout_v1",
    "cfb_game_total_games_on_day_step2_visual_v1",
    "cfb_game_total_games_on_day_step3_details_v1",
    "cfb_game_total_games_on_day_step4_interaction_mobile_v1",
)


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Rebind the full frozen card chain after purge, then render V42 data."""
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
    "POST_PURGE_CARD_REBIND",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
