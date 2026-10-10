"""CFB Game Total — Games on This Day Step 1 card-layout cleanup.

Presentation-only additive successor for the frozen V163 visible game selector.
The existing selector continues to own event identity, links, selected state,
and matchup behavior. This layer only appends a narrowly scoped CSS override so
mobile matchup cards stack full-width instead of clipping in a horizontal row.

No model, projection, probability, API, sportsbook, schedule, or other-sport
behavior is changed.
"""
from __future__ import annotations

import importlib
from threading import RLock

MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 1 CARD LAYOUT V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0

_INSTALL_MARKER = "data-kyre-cfb-games-on-day-step1-layout=\"v1\""
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


def install_games_on_day_step1_layout() -> bool:
    """Append one idempotent CSS override to the frozen selector owner."""
    with _LOCK:
        owner = importlib.import_module("cfb_game_total_clean_page_v14")
        current_css = str(getattr(owner, "_V163_CSS", ""))
        if _INSTALL_MARKER in current_css:
            return True
        if not current_css:
            raise RuntimeError("CFB Game Total V163 selector CSS owner unavailable")
        owner._V163_CSS = current_css + STEP1_CSS
        return True


__all__ = [
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_CSS",
    "install_games_on_day_step1_layout",
]
