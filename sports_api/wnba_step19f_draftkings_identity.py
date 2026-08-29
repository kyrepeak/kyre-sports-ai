"""WNBA Step 19F: strict DraftKings event-team identity compatibility.

DraftKings' public sportscontent feed sometimes uses a sportsbook display
abbreviation that differs from the WNBA registry abbreviation.  The known live
2026 example is ``PHO Mercury`` while the official/internal registry uses
``PHX`` / ``Phoenix Mercury``.

This layer adds only explicitly certified, unambiguous provider aliases before
Step 11A's existing official schedule reconciliation.  It does not weaken game
uniqueness, player identity, slate-date bounds, provider readiness, or any
wagering/production safety guard.
"""
from __future__ import annotations

from typing import Any

from sports_api import wnba_step11_draftkings_provider as draftkings

SOURCE = "Kyre Sports API WNBA Step19F strict DraftKings team-alias compatibility"
MODEL_VERSION = "wnba_step19f_draftkings_team_alias_v1"

# Exact aliases observed on the anonymous DraftKings WNBA feed whose city code
# differs from this project's official 2026 team registry abbreviation.
_PROVIDER_TEAM_ALIASES = {
    "pho mercury": "Phoenix Mercury",
}

_ORIGINAL_TEAM_IDENTITY_KEY = draftkings._team_identity_key
_INSTALLED = False


def team_identity_key_step19f(value: Any) -> str:
    raw_key = draftkings._name_key(value)
    canonical_name = _PROVIDER_TEAM_ALIASES.get(raw_key)
    if canonical_name is not None:
        return _ORIGINAL_TEAM_IDENTITY_KEY(canonical_name)
    return _ORIGINAL_TEAM_IDENTITY_KEY(value)


def install_step19f_draftkings_identity() -> dict[str, Any]:
    global _INSTALLED
    # Idempotent so import/reload paths cannot wrap the resolver repeatedly.
    if draftkings._team_identity_key is not team_identity_key_step19f:
        draftkings._team_identity_key = team_identity_key_step19f
    _INSTALLED = True
    return INSTALLATION


INSTALLATION = {
    "source": SOURCE,
    "model_version": MODEL_VERSION,
    "installed": lambda: _INSTALLED,
    "strict_alias_count": len(_PROVIDER_TEAM_ALIASES),
    "official_schedule_reconciliation_modified": False,
    "game_uniqueness_relaxed": False,
    "slate_date_bounds_relaxed": False,
    "player_identity_relaxed": False,
    "projection_logic_modified": False,
    "wagering_enabled": False,
}


__all__ = [
    "INSTALLATION",
    "MODEL_VERSION",
    "SOURCE",
    "install_step19f_draftkings_identity",
    "team_identity_key_step19f",
]
