"""CFB Game Total — Games on This Day Step 1 card-layout cleanup.

Presentation-only additive successor for the frozen V163 visible game selector.
The existing selector continues to own event identity, links, selected state,
and matchup behavior. This layer appends one narrowly scoped mobile CSS override
and rebinds that override to the freshly imported V163 owner after the exact CFB
Game Total route performs its module purge/reimport cycle.

No model, projection, probability, API, sportsbook, schedule, or other-sport
behavior is changed.
"""
from __future__ import annotations

import importlib
from threading import RLock
from typing import Any

MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 1 CARD LAYOUT V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
TARGET_PAGE = "cfb_game_total_clean_page_v38"

_INSTALL_MARKER = "data-kyre-cfb-games-on-day-step1-layout=\"v1\""
_INSTALL_ATTR = "_cfb_games_on_day_step1_post_purge_installed"
_LOCK = RLock()

STEP1_CSS = r"""
<style data-kyre-cfb-games-on-day-step1-layout="v1">
/* Preserve the existing desktop selector. Step 1 fixes the cramped mobile row only. */
@media(max-width:760px){
  .gt163-game-wrap{
    padding:10px;
    border-radius:16px;
  }
  .gt163-game-title{
    margin:0 2px 9px;
  }
  .gt163-game-scroller{
    display:grid;
    grid-template-columns:1fr;
    gap:9px;
    overflow-x:visible;
    overflow-y:visible;
    padding:2px 1px 3px;
    scroll-snap-type:none;
  }
  .gt163-game-link,.gt163-game-disabled{
    width:100%;
    min-width:0;
    max-width:none;
    min-height:54px;
    padding:10px 12px;
    border-radius:12px;
    white-space:normal;
    overflow:visible;
    text-overflow:clip;
    line-height:1.35;
    box-sizing:border-box;
  }
  .gt163-game-link{
    align-items:center;
  }
  .gt163-game-link.selected{
    border-color:rgba(69,240,173,.92);
    box-shadow:0 0 0 1px rgba(69,240,173,.12),0 8px 22px rgba(0,0,0,.22);
  }
}
</style>
"""


def _append_step1_css(owner: Any) -> bool:
    current_css = str(getattr(owner, "_V163_CSS", ""))
    if not current_css:
        raise RuntimeError("CFB Game Total V163 selector CSS owner unavailable")
    if _INSTALL_MARKER in current_css:
        return False
    owner._V163_CSS = current_css + STEP1_CSS
    return True


def install_games_on_day_step1_layout() -> bool:
    """Install Step-1 CSS now and rebind it after each exact-route purge."""
    with _LOCK:
        # Immediate compatibility for a V14 owner that is already imported.
        owner = importlib.import_module("cfb_game_total_clean_page_v14")
        _append_step1_css(owner)

        root = importlib.import_module("streamlit_memory_lazy_router_v1")
        render_owner = importlib.import_module("streamlit_memory_lazy_router_v160")
        route_owner = importlib.import_module("streamlit_memory_lazy_router_v181")
        current = render_owner._render_exact_game_total_surface
        if getattr(current, _INSTALL_ATTR, False):
            return True
        original = current

        def repaired_render_exact_game_total_surface(*args: Any, **kwargs: Any):
            if not route_owner._game_total_route_active():
                return original(*args, **kwargs)

            original_import = root._import
            restores: list[tuple[Any, str]] = []

            def import_with_step1(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    fresh_owner = importlib.import_module("cfb_game_total_clean_page_v14")
                    current_css = str(getattr(fresh_owner, "_V163_CSS", ""))
                    if not current_css:
                        raise RuntimeError("Fresh CFB Game Total V163 selector CSS owner unavailable")
                    if _INSTALL_MARKER not in current_css:
                        fresh_owner._V163_CSS = current_css + STEP1_CSS
                        restores.append((fresh_owner, current_css))
                return page

            root._import = import_with_step1
            try:
                return original(*args, **kwargs)
            finally:
                root._import = original_import
                for fresh_owner, original_css in reversed(restores):
                    fresh_owner._V163_CSS = original_css

        setattr(repaired_render_exact_game_total_surface, _INSTALL_ATTR, True)
        setattr(repaired_render_exact_game_total_surface, "_cfb_games_on_day_step1_original", original)
        render_owner._render_exact_game_total_surface = repaired_render_exact_game_total_surface
        return True


__all__ = [
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_CSS",
    "TARGET_PAGE",
    "install_games_on_day_step1_layout",
]
