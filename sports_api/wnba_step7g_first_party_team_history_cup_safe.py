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

The overlay also gives the WNBA.com box-page transport a small bounded retry for
transient upstream failures such as HTTP 502/503 responses. Only the already
classified first-party upstream exception is retried. Not-found responses,
malformed schemas, identity conflicts, score conflicts, and Step 4J validation
errors are never softened or retried here.

No frozen Step 4J/4N source file is modified. No production switch is enabled.
"""
from __future__ import annotations

from time import sleep
from typing import Any

from sports_api import wnba_step7g_first_party_team_history as base

CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON: dict[int, frozenset[str]] = {
    2026: frozenset({"1052600001"}),
}
CERTIFIED_NON_REGULAR_REASON_BY_GAME_ID: dict[str, str] = {
    "1052600001": "2026 WNBA Commissioner's Cup Championship; extra non-regular-season game",
}
BOX_TRANSPORT_MAX_ATTEMPTS = 3
BOX_TRANSPORT_RETRY_DELAYS_SECONDS = (0.75, 1.5)

_ORIGINAL_REGULAR_SEASON_MARKER = base._regular_season_marker
_ORIGINAL_BOX_LOADER = base.get_first_party_game_box_score_dataset


def _cup_safe_regular_season_marker(game: dict[str, Any], season: int) -> bool:
    game_id = base._clean(game.get("game_id")) if isinstance(game, dict) else None
    if game_id in CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON.get(season, frozenset()):
        return False
    return _ORIGINAL_REGULAR_SEASON_MARKER(game, season)


def _retrying_box_loader(game_id: str, season: int) -> dict[str, Any]:
    for attempt in range(1, BOX_TRANSPORT_MAX_ATTEMPTS + 1):
        try:
            return _ORIGINAL_BOX_LOADER(game_id, season)
        except base.WNBAStep7GFirstPartyUpstreamError:
            if attempt >= BOX_TRANSPORT_MAX_ATTEMPTS:
                raise
            sleep(BOX_TRANSPORT_RETRY_DELAYS_SECONDS[attempt - 1])
    raise AssertionError("unreachable retry loop")


def install_exact_cup_exclusion() -> None:
    """Install the exact-ID and transient-transport overlay in this process.

    The guards refuse to overwrite unknown third-party patches. Repeated calls
    are idempotent. The expensive Step 4J team-history cache is invalidated only
    when this call actually changes an adapter seam; a no-op reinstall preserves
    still-valid cached official data.
    """
    current_marker = base._regular_season_marker
    if current_marker not in {
        _ORIGINAL_REGULAR_SEASON_MARKER,
        _cup_safe_regular_season_marker,
    }:
        raise base.frozen.WNBATeamHistoryUpstreamError(
            "Step 7G Cup-safe overlay refuses to replace an unknown Step 4J marker override."
        )

    current_loader = base.get_first_party_game_box_score_dataset
    if current_loader not in {_ORIGINAL_BOX_LOADER, _retrying_box_loader}:
        raise base.frozen.WNBATeamHistoryUpstreamError(
            "Step 7G Cup-safe overlay refuses to replace an unknown box-score loader override."
        )

    marker_changed = current_marker is _ORIGINAL_REGULAR_SEASON_MARKER
    loader_changed = current_loader is _ORIGINAL_BOX_LOADER
    base._regular_season_marker = _cup_safe_regular_season_marker
    base.get_first_party_game_box_score_dataset = _retrying_box_loader
    if marker_changed or loader_changed:
        # A real seam transition can change which rows/transport are valid, so
        # existing derived history must be discarded. Repeated idempotent
        # installs must not throw away a valid TTL-bounded official-data cache.
        base._CACHE.clear()


def restore_base_marker_for_tests() -> None:
    """Restore original adapter seams; intended only for isolated tests."""
    current_marker = base._regular_season_marker
    if current_marker is _cup_safe_regular_season_marker:
        base._regular_season_marker = _ORIGINAL_REGULAR_SEASON_MARKER
    elif current_marker is not _ORIGINAL_REGULAR_SEASON_MARKER:
        raise base.frozen.WNBATeamHistoryUpstreamError(
            "Step 7G Cup-safe overlay found an unexpected marker while restoring tests."
        )

    current_loader = base.get_first_party_game_box_score_dataset
    if current_loader is _retrying_box_loader:
        base.get_first_party_game_box_score_dataset = _ORIGINAL_BOX_LOADER
    elif current_loader is not _ORIGINAL_BOX_LOADER:
        raise base.frozen.WNBATeamHistoryUpstreamError(
            "Step 7G Cup-safe overlay found an unexpected box loader while restoring tests."
        )
    base._CACHE.clear()


def get_first_party_team_game_log_dataset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call the certified Step 4J adapter with exact-ID/retry hardening installed."""
    install_exact_cup_exclusion()
    return base.get_first_party_team_game_log_dataset(*args, **kwargs)
