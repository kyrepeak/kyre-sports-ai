"""WNBA PRA V3.6.5 — Step-5 normalized headshot identity reliability patch.

Presentation-only wrapper over V3.6.3. Keeps the existing projection/slate
identity resolver as the primary path and supplies verified ESPN WNBA player IDs
only when that resolver returns no usable ID for a known player.

V3.6.5 fixes the V3.6.4 fallback-key mismatch by generating fallback keys with
the exact same _player_key() normalizer used by the Step-5 card renderer.

This changes no PRA projection, availability, minutes/usage, matchup,
sportsbook, qualification, Monte Carlo, final-ready or ranking logic.
"""
from __future__ import annotations

import wnba_pra_step5_identity_v363 as prior

MODEL_VERSION = "PRA V3.6.5 • STEP-5 NORMALIZED HEADSHOT FALLBACK • MODEL PRESERVED"

# Verified ESPN WNBA athlete IDs. Display-only fallbacks, used strictly when the
# native projection identity path has no usable PLAYER_ID.
_VERIFIED_ESPN_PLAYER_IDS = {
    "Caitlin Clark": 4433403,
    "Kelsey Mitchell": 3142191,
}

_ORIGINAL_IDENTITY_MAPS = prior._identity_maps


def _identity_maps_v365(day):
    """Preserve native identities; fill missing IDs using renderer-exact keys."""
    player_ids, teams = _ORIGINAL_IDENTITY_MAPS(day)
    player_ids = dict(player_ids or {})

    for display_name, espn_id in _VERIFIED_ESPN_PLAYER_IDS.items():
        # CRITICAL: Step-5 cards retrieve with prior._player_key(name), so the
        # fallback must be inserted under that exact normalization contract.
        key = prior._player_key(display_name)
        if key and not player_ids.get(key):
            player_ids[key] = espn_id

    return player_ids, teams


def install():
    """Install only the Step-5 display renderer plus normalized ID fallback."""
    prior._identity_maps = _identity_maps_v365
    prior.install()
    prior.v28._v365_step5_normalized_headshot_fallback_installed = True


def begin_render():
    """Reset display memo, then install the normalized reliability fallback."""
    prior._IDENTITY_MEMO.clear()
    install()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
