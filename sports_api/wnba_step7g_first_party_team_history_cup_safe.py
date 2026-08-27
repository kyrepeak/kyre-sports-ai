"""Exact 2026 Commissioner's Cup exclusion overlay for Step 7G Step 4J.

The first-party Step 4J adapter intentionally fails closed on completed game-ID
families that have not been certified as Regular Season or known non-regular
competition. The 2026 Commissioner's Cup Championship uses game ID
``1052600001`` and is an extra championship game that does not count in the
regular-season standings.

This overlay changes only that exact game ID. It deliberately does NOT treat the
whole ``105`` family as non-regular. Any other ``105...`` completed game still
falls through to the base adapter's fail-closed unknown-family behavior unless
it is independently certified later.

No frozen Step 4J/4N source file is modified. No production switch is enabled.
"""
from __future__ import annotations

from typing import Any

from sports_api import wnba_step7g_first_party_team_history as base

CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON: dict[int, frozenset[str]] = {
    2026: frozenset({"1052600001"}),
}
CERTIFIED_NON_REGULAR_REASON_BY_GAME_ID: dict[str, str] = {
    "1052600001": "2026 WNBA Commissioner's Cup Championship; extra non-regular-season game",
}

_ORIGINAL_REGULAR_SEASON_MARKER = base._regular_season_marker


def _cup_safe_regular_season_marker(game: dict[str, Any], season: int) -> bool:
    game_id = base._clean(game.get("game_id")) if isinstance(game, dict) else None
    if game_id in CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON.get(season, frozenset()):
        return False
    return _ORIGINAL_REGULAR_SEASON_MARKER(game, season)


def install_exact_cup_exclusion() -> None:
    """Install the exact-ID overlay into the isolated Step 7G adapter process.

    The guard refuses to overwrite an unknown third-party patch. Repeated calls
    are idempotent.
    """
    current = base._regular_season_marker
    if current is _cup_safe_regular_season_marker:
        return
    if current is not _ORIGINAL_REGULAR_SEASON_MARKER:
        raise base.frozen.WNBATeamHistoryUpstreamError(
            "Step 7G Cup-safe overlay refuses to replace an unknown Step 4J marker override."
        )
    base._regular_season_marker = _cup_safe_regular_season_marker
    base._CACHE.clear()


def restore_base_marker_for_tests() -> None:
    """Restore the original adapter marker; intended only for isolated tests."""
    current = base._regular_season_marker
    if current is _cup_safe_regular_season_marker:
        base._regular_season_marker = _ORIGINAL_REGULAR_SEASON_MARKER
        base._CACHE.clear()
        return
    if current is not _ORIGINAL_REGULAR_SEASON_MARKER:
        raise base.frozen.WNBATeamHistoryUpstreamError(
            "Step 7G Cup-safe overlay found an unexpected marker while restoring tests."
        )


def get_first_party_team_game_log_dataset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call the certified Step 4J adapter with the exact Cup exclusion installed."""
    install_exact_cup_exclusion()
    return base.get_first_party_team_game_log_dataset(*args, **kwargs)
