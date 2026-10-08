"""CFB Game Total clean page V35 — Page 1 V2 Step 2 multi-source data engine.

Additive successor to frozen/preserved V34 presentation. V35 changes only the
copied display-data handoff: after V24's certified environment enrichment, it
adds verified multi-source Page-1 evidence. Frozen model/projection behavior is
never mutated.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Mapping

import cfb_game_total_clean_page_v24 as data_owner
import cfb_game_total_clean_page_v34 as prior
import cfb_game_total_page1_multisource_v1 as page1_data

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V35 • PAGE1 V2 STEP2 MULTI-SOURCE DATA"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v34"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE1 V2 STEP2 MULTI-SOURCE DATA ACTIVE"
STEP2_MULTISOURCE_MARKER = "CFB_GAME_TOTAL_PAGE1_V2_STEP2_MULTISOURCE_DATA_ACTIVE"

_HANDOFF_LOCK = RLock()
_FROZEN_V24_RECONCILE = data_owner._reconcile_display_bundle_v24


def _reconcile_display_bundle_v35(
    game: Mapping[str, Any],
    selected_day: Any,
    step1_away: Mapping[str, Any],
    step1_home: Mapping[str, Any],
):
    display_game, away, home, diag = _FROZEN_V24_RECONCILE(
        game,
        selected_day,
        step1_away,
        step1_home,
    )
    return page1_data.enrich_display_bundle(
        display_game,
        selected_day,
        away,
        home,
        diag,
    )


def _render_with_page1_multisource(callback, *args, **kwargs):
    with _HANDOFF_LOCK:
        original = data_owner._reconcile_display_bundle_v24
        data_owner._reconcile_display_bundle_v24 = _reconcile_display_bundle_v35
        try:
            return callback(*args, **kwargs)
        finally:
            data_owner._reconcile_display_bundle_v24 = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_with_page1_multisource(
        prior.render_game_total_hub,
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
        raise ValueError(f"Page V35 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_MULTISOURCE_MARKER",
    "_reconcile_display_bundle_v35",
    "_render_with_page1_multisource",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
