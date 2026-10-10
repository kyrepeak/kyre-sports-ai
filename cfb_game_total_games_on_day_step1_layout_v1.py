"""CFB Game Total — Games on This Day Step 1 card-layout cleanup.

Presentation-only additive successor for the frozen V163 selector and the live
Page-1 Step-4 Games-on-This-Day owner. Event identity, selected matchup state,
schedule data, and model behavior remain owned by the existing frozen pipeline.
This layer only appends narrowly scoped CSS so the active mobile cards render
full-width without horizontal clipping.

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

_INSTALL_MARKER = 'data-kyre-cfb-games-on-day-step1-layout="v1"'
_ACTIVE_OWNER_MODULE = "cfb_game_total_page1_visual_cleanup_step4_activation_v1"
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

ACTIVE_OWNER_CSS = r"""
<style data-kyre-cfb-games-on-day-step1-layout="v1">
/* Step 4 owns the production Games-on-This-Day surface; bind Step 1 there too. */
@media(max-width:760px){
  .gtvc4-day{
    padding:10px;
    border-radius:16px;
  }
  .gtvc4-daygrid{
    display:grid;
    grid-template-columns:1fr;
    gap:9px;
    overflow-x:visible;
    overflow-y:visible;
  }
  .gtvc4-game{
    width:100%;
    min-width:0;
    max-width:none;
    padding:11px 12px;
    border-radius:12px;
    box-sizing:border-box;
    background:linear-gradient(145deg,#0a2030,#0a1825);
    box-shadow:0 8px 20px rgba(0,0,0,.18);
  }
  .gtvc4-game-top{
    gap:10px;
  }
  .gtvc4-matchup{
    white-space:normal;
    overflow:visible;
    text-overflow:clip;
    line-height:1.3;
  }
}
</style>
"""


def _append_css(owner: object, attr: str, css: str, label: str) -> None:
    current_css = str(getattr(owner, attr, ""))
    if not current_css:
        raise RuntimeError(label + " CSS owner unavailable")
    if _INSTALL_MARKER not in current_css:
        setattr(owner, attr, current_css + css)


def install_games_on_day_step1_layout() -> bool:
    """Bind one idempotent mobile override to both legacy and active owners."""
    with _LOCK:
        legacy_owner = importlib.import_module("cfb_game_total_clean_page_v14")
        _append_css(legacy_owner, "_V163_CSS", STEP1_CSS, "CFB Game Total V163 selector")

        active_owner = importlib.import_module(_ACTIVE_OWNER_MODULE)
        _append_css(active_owner, "STEP4_CSS", ACTIVE_OWNER_CSS, "CFB Game Total Step-4 Games-on-This-Day")
        return True


__all__ = [
    "ACTIVE_OWNER_CSS",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_CSS",
    "install_games_on_day_step1_layout",
]
