"""CFB Game Total — Games on This Day Step 4 interaction/mobile completion.

Final presentation-only layer for the four-step Games on This Day workstream.
It preserves the frozen Step-1 layout, Step-2 links/selection/logos, and Step-3
status/rank/conference display while adding touch/focus ergonomics, bounded
mobile overflow protection, and an accessible card name containing Step-3
context. No network, model, projection, probability, or event identity changes.
"""
from __future__ import annotations

from html import escape, unescape
import importlib
import re
from threading import RLock
from typing import Any, Mapping

MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 4 INTERACTION MOBILE V1"
DIRECT_NETWORK_ENDPOINTS_ADDED = 0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_INSTALL_ATTR = "_cfb_games_on_day_step4_interaction_installed"
_ORIGINAL_ATTR = "_cfb_games_on_day_step4_original"
_LOCK = RLock()

STEP4_CSS = r"""
<style data-kyre-cfb-games-on-day-step4-interaction="v1">
.gt2-game-card{touch-action:manipulation;-webkit-tap-highlight-color:rgba(88,201,255,.16);box-sizing:border-box;max-width:100%;min-height:44px;cursor:pointer}
.gt2-game-card:focus-visible{outline:2px solid #9fdfff;outline-offset:3px;box-shadow:0 0 0 4px rgba(88,201,255,.14),0 10px 28px rgba(0,0,0,.28)!important}
.gt163-game-wrap{max-width:100%;overflow-x:clip}
.gt163-game-scroller{max-width:100%;min-width:0}
.gt2-game-disabled{cursor:default}
@media(max-width:760px){.gt2-game-card{width:100%;max-width:100%;min-width:0}.gt163-game-wrap,.gt163-game-scroller{width:100%;max-width:100%;min-width:0;overflow-x:clip}}
</style>
"""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _accessible_summary(game: Mapping[str, Any]) -> str:
    step3 = importlib.import_module("cfb_game_total_games_on_day_step3_details_v1")
    pieces: list[str] = []
    status = step3.status_label(game)
    if status:
        pieces.append(status)
    for side in ("away", "home"):
        name = _clean(step3._team_name(game, side))
        rank = _clean(step3._rank(game, side))
        conference = _clean(step3._conference(game, side))
        team_bits = [bit for bit in (rank, name, conference) if bit]
        if team_bits:
            pieces.append(" ".join(team_bits))
    return "; ".join(pieces)


def augment_interaction_html(base_html: str, game: Mapping[str, Any]) -> str:
    """Add Step-4 interaction/accessibility evidence without altering link state."""
    html = str(base_html or "")
    if not html or 'data-step4-interaction="v1"' in html:
        return html

    html = re.sub(
        r"(<(?:a|span)\b)",
        r'\1 data-step4-interaction="v1"',
        html,
        count=1,
    )
    summary = _accessible_summary(game)
    if not summary:
        return html

    match = re.search(r'aria-label="([^"]*)"', html)
    if match:
        existing = unescape(match.group(1)).strip()
        combined = existing + ("; " if existing else "") + summary
        replacement = 'aria-label="' + escape(combined, quote=True) + '"'
        html = html[: match.start()] + replacement + html[match.end() :]
    else:
        html = re.sub(
            r"(<(?:a|span)\b[^>]*)(>)",
            lambda m: m.group(1) + ' aria-label="' + escape(summary, quote=True) + '"' + m.group(2),
            html,
            count=1,
        )
    return html


def install_games_on_day_step4_interaction_mobile() -> bool:
    """Install Step 4 once after Step 3 without wrapping the frozen renderer."""
    with _LOCK:
        step3 = importlib.import_module("cfb_game_total_games_on_day_step3_details_v1")
        step2 = importlib.import_module("cfb_game_total_games_on_day_step2_visual_v1")
        step3.install_games_on_day_step3_details()

        current = step3.augment_game_card_html
        if getattr(current, _INSTALL_ATTR, False):
            if STEP4_CSS not in step2.STEP2_CSS:
                step2.STEP2_CSS += STEP4_CSS
            return True

        def augment_with_interaction(base_html: str, game: Mapping[str, Any]) -> str:
            return augment_interaction_html(current(base_html, game), game)

        setattr(augment_with_interaction, _INSTALL_ATTR, True)
        setattr(augment_with_interaction, _ORIGINAL_ATTR, current)
        step3.augment_game_card_html = augment_with_interaction
        if STEP4_CSS not in step2.STEP2_CSS:
            step2.STEP2_CSS += STEP4_CSS
        return True


__all__ = [
    "DIRECT_NETWORK_ENDPOINTS_ADDED",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_CSS",
    "augment_interaction_html",
    "install_games_on_day_step4_interaction_mobile",
]
