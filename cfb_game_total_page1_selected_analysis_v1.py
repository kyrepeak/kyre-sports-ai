"""CFB Game Total Page 1 — selected-game analysis semantics V1.

Presentation-only wrapper over the frozen same-page selected-game analysis.
It preserves every existing analysis surface and value while correcting the
human-facing page order: selected game analysis is Page 1 of 2 and its Back to
Slate control returns to the Page-2 slate.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Any

import cfb_game_total_page2_same_page_shell_repair_v1 as prior
import cfb_game_total_page2_step2_matchup_hero_phx_v1 as hero
import cfb_game_total_page2_step8_final_runtime_v1 as runtime

MODEL_VERSION = "CFB GAME TOTAL PAGE1 SELECTED ANALYSIS V1"
MARKET = prior.MARKET
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE1_SELECTED_ANALYSIS_V1_ACTIVE"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_LOCK = RLock()


def _page1_hero(delegate):
    def wrapped(*args: Any, **kwargs: Any) -> str:
        html = str(delegate(*args, **kwargs))
        return (
            html.replace("Page 2 of 2", "Page 1 of 2")
            .replace('aria-label="Page 2 selected college football matchup"',
                     'aria-label="Page 1 selected college football matchup"')
        )
    return wrapped


def _page1_header(delegate):
    def wrapped(*args: Any, **kwargs: Any) -> str:
        html = str(delegate(*args, **kwargs))
        return html.replace("← Back to Slate", "← Back to Slate • Page 2")
    return wrapped


@contextmanager
def install_page1_selected_analysis_labels():
    with _LOCK:
        original_hero = hero.build_page2_matchup_hero_html
        original_header = runtime.build_page2_header_html
        hero.build_page2_matchup_hero_html = _page1_hero(original_hero)
        runtime.build_page2_header_html = _page1_header(original_header)
        try:
            yield
        finally:
            runtime.build_page2_header_html = original_header
            hero.build_page2_matchup_hero_html = original_hero


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    with install_page1_selected_analysis_labels():
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Selected Page 1 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell() -> Any:
    with install_page1_selected_analysis_labels():
        return prior.render_selected_in_shared_shell()


__all__ = [
    "ACTIVE_MARKER",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "install_page1_selected_analysis_labels",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_selected_in_shared_shell",
]
