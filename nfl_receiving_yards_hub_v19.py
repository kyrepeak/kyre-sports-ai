"""NFL Receiving Yards V19 — compact deep-evidence presentation.

Presentation-only successor over frozen V18. V19 preserves the entire certified
Receiving Yards identity, relevance, history, market, and projection chain and
only compresses the per-player deep-evidence surface that remained too tall on
mobile/tablet.

No projection, probability, sportsbook, line, expected-value, or wager math is
changed. Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v15 as card_owner
import nfl_receiving_yards_hub_v18 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V19 • COMPACT DEEP EVIDENCE"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v18"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V15 = card_owner._player_card_v15

_COMPACT_CSS = r'''
<style>
/* V19 is deliberately scoped to the detailed per-player stack. */
.krecv19-compact{margin:0 0 8px!important;padding:0!important}

/* The quick-read V14 header already owns player identity. The older V2 identity
   card inside DEEP EVIDENCE is duplicate content and was the source of the giant
   headshot/team-logo block visible in the production screenshots. */
.krecv19-compact .krecv2-card{display:none!important}

/* Fail-safe: no image inside detailed evidence can become a poster-sized asset. */
.krecv19-compact img{max-width:64px!important;max-height:64px!important;width:auto!important;height:auto!important;object-fit:contain!important}

/* Tighten the surviving evidence without hiding any certified text/numbers. */
.krecv19-compact .krecv14-player{padding:8px 9px!important;margin:5px 0 8px!important;border-radius:13px!important}
.krecv19-compact .krecv14-quick{gap:7px!important;margin-bottom:5px!important}
.krecv19-compact .krecv14-deep{margin:4px 0!important;padding:0!important;line-height:1.15!important}
.krecv19-compact .krecv15-history{padding:6px 8px!important;margin:0 0 5px!important;border-radius:9px!important}
.krecv19-compact .krecv6-wrap{gap:6px!important;margin:5px 0!important;padding:7px 8px!important}
.krecv19-compact .krecv7-wrap{gap:6px!important;margin:5px 0!important;padding:7px 8px!important}
.krecv19-compact [class*="grid"]{gap:6px!important}
.krecv19-compact [class*="section"]{margin-top:5px!important;margin-bottom:5px!important}

@media(max-width:760px){
  .krecv19-compact{margin-bottom:6px!important}
  .krecv19-compact .krecv14-player{padding:7px 8px!important;margin:4px 0 6px!important}
  .krecv19-compact .krecv15-history{padding:5px 7px!important;margin-bottom:4px!important}
  .krecv19-compact .krecv6-wrap,.krecv19-compact .krecv7-wrap{padding:6px 7px!important;margin:4px 0!important}
}
</style>
'''


def _compact_player_card_v19(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    """Wrap the frozen V15+ detail stack; never mutate its analytical payload."""
    stack = _ORIGINAL_PLAYER_CARD_V15(player, team, opponent)
    return f'<div class="krecv19-compact">{stack}</div>'


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_COMPACT_CSS, unsafe_allow_html=True)
    original = card_owner._player_card_v15
    card_owner._player_card_v15 = _compact_player_card_v19
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        card_owner._player_card_v15 = original


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V19 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_compact_player_card_v19",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
