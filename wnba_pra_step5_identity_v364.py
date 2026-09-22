"""WNBA PRA V3.6.4 — Step-5 headshot identity reliability patch.

Presentation-only wrapper over V3.6.3. Keeps the existing projection/slate
identity resolver as the primary path and supplies verified ESPN WNBA player IDs
only when that resolver returns no usable ID for a known player.

This changes no PRA projection, availability, minutes/usage, matchup,
sportsbook, qualification, Monte Carlo, final-ready or ranking logic.
"""
from __future__ import annotations

import wnba_pra_step5_identity_v363 as prior

MODEL_VERSION = "PRA V3.6.4 • STEP-5 HEADSHOT FALLBACK • MODEL PRESERVED"

# Verified ESPN WNBA athlete IDs. These are display-only fallbacks used strictly
# when the normal projection identity path has no usable PLAYER_ID.
_VERIFIED_ESPN_PLAYER_IDS = {
    "caitlinclark": 4433403,
    "kelseymitchell": 3142191,
}

_ORIGINAL_IDENTITY_MAPS = prior._identity_maps


def _identity_maps_v364(day):
    """Preserve native identities; fill only missing verified display IDs."""
    player_ids, teams = _ORIGINAL_IDENTITY_MAPS(day)
    player_ids = dict(player_ids or {})

    for normalized_name, espn_id in _VERIFIED_ESPN_PLAYER_IDS.items():
        if not player_ids.get(normalized_name):
            player_ids[normalized_name] = espn_id

    return player_ids, teams


def install():
    """Install the V3.6.3 renderer with the V3.6.4 identity fallback."""
    prior._identity_maps = _identity_maps_v364
    prior.install()
    prior.v28._v364_step5_headshot_fallback_installed = True


def begin_render():
    """Reset display memo, then install the reliability fallback."""
    prior._IDENTITY_MEMO.clear()
    install()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
