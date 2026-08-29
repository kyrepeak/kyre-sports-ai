"""Step 19D resilience for transient WNBA.com historical page transport failures.

This module does two deliberately narrow things:

1. It gives WNBA.com first-party page *transport* failures a bounded retry.
   Successfully returned malformed content still fails closed and is never retried
   into acceptance.
2. During recent historical rotation aggregation only, a game whose certified
   WNBA.com reconstruction remains unavailable because of a page-request transport
   failure is reported through the existing ``missing_rotation_game_ids`` contract.
   Other rotation integrity errors still fail closed, and if every selected game is
   unavailable the existing not-found result is preserved.

No current-game availability/injury gate is relaxed and no projection is fabricated.
"""
from __future__ import annotations

from copy import deepcopy
import time
from typing import Any

from sports_api import wnba_player_opportunity_context as opportunity
from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_step7g_first_party_history as first_party

MODEL_VERSION = "wnba_step19d_history_transport_resilience_v1"
PAGE_REQUEST_ATTEMPTS = 3
PAGE_RETRY_DELAYS_SECONDS = (0.20, 0.50)

_ORIGINAL_PAGE_REQUEST = first_party._request_page_props
_ORIGINAL_RECENT_ROTATION = rotation.get_player_recent_rotation_context

_PAGE_REQUEST_PREFIX = "Official WNBA.com page request failed for "
_ROTATION_FALLBACK_PREFIX = (
    "Official WNBA Stats gamerotation transport failed and the certified "
    "first-party fallback also failed: "
)


def _is_page_transport_error(exc: BaseException) -> bool:
    message = " ".join(str(exc).split())
    return message.startswith(_PAGE_REQUEST_PREFIX)


def _is_historical_game_page_transport_error(exc: BaseException) -> bool:
    message = " ".join(str(exc).split())
    return (
        message.startswith(_ROTATION_FALLBACK_PREFIX + _PAGE_REQUEST_PREFIX)
        and "https://www.wnba.com/game/" in message
    )


def _request_page_props_with_bounded_retry(
    url: str,
    *,
    ttl_seconds: int,
) -> tuple[dict[str, Any], str, bool, int]:
    """Retry only request-layer WNBA.com failures; parsing/integrity stays fail-closed."""
    last_error: BaseException | None = None
    for attempt in range(1, PAGE_REQUEST_ATTEMPTS + 1):
        try:
            return _ORIGINAL_PAGE_REQUEST(url, ttl_seconds=ttl_seconds)
        except first_party.WNBAStep7GFirstPartyNotFoundError:
            raise
        except first_party.WNBAStep7GFirstPartyUpstreamError as exc:
            if not _is_page_transport_error(exc):
                raise
            last_error = exc
            if attempt >= PAGE_REQUEST_ATTEMPTS:
                raise
            time.sleep(PAGE_RETRY_DELAYS_SECONDS[attempt - 1])
    assert last_error is not None
    raise last_error


def get_player_recent_rotation_context_step19d(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    """Preserve frozen recent-rotation semantics while isolating one old transport miss."""
    rotation.get_wnba_teams(season)
    player_id = rotation._player_id(player_id)
    season_type = rotation._choice(
        season_type, rotation.ALLOWED_SEASON_TYPES, "season_type"
    )
    last_n_games = rotation._recent_game_count(last_n_games)
    rotation_stat = rotation._choice(
        rotation_stat, rotation.ALLOWED_ROTATION_STATS, "rotation_stat"
    )
    try:
        history = rotation.get_player_game_log_dataset(
            player_id, season, season_type=season_type
        )
    except rotation.WNBAHistoryUpstreamError as exc:
        raise rotation.WNBARotationUpstreamError(str(exc)) from exc
    games = history.get("games")
    if not isinstance(games, list):
        raise rotation.WNBARotationUpstreamError(
            "WNBA player game log returned a malformed games field."
        )
    selected = games[:last_n_games]
    if not selected:
        raise rotation.WNBARotationNotFoundError(
            f"No WNBA games were found for player {player_id} in {season}."
        )

    rows: list[dict[str, Any]] = []
    all_stints: list[dict[str, Any]] = []
    missing: list[str] = []
    team_keys: list[str] = []
    for history_game in selected:
        gid = rotation._clean(history_game.get("game_id"))
        if not gid:
            continue
        try:
            game = rotation.get_game_rotation(
                gid, season, rotation_stat=rotation_stat
            )
        except rotation.WNBARotationNotFoundError:
            missing.append(gid)
            continue
        except rotation.WNBARotationUpstreamError as exc:
            if not _is_historical_game_page_transport_error(exc):
                raise
            # The frozen recent-history contract already represents unavailable
            # historical rotation games as missing, never as fabricated stints.
            missing.append(gid)
            continue
        player = rotation._find_player(game, player_id)
        if player is None:
            missing.append(gid)
            continue
        all_stints.extend(player["stints"])
        if player["team_key"] not in team_keys:
            team_keys.append(player["team_key"])
        rows.append(
            {
                "game_id": gid,
                "game_date": history_game.get("game_date"),
                "matchup": history_game.get("matchup"),
                "player_rotation": player,
            }
        )
    if not rows:
        raise rotation.WNBARotationNotFoundError(
            "Official rotation data was unavailable for the selected recent games "
            f"for player {player_id}."
        )

    total_seconds = sum(item["duration_seconds"] for item in all_stints)
    usage = [
        (item["usage_percentage_during_stint"], item["duration_seconds"])
        for item in all_stints
        if item["usage_percentage_during_stint"] is not None
        and item["duration_seconds"] > 0
    ]
    usage_den = sum(seconds for _, seconds in usage)
    points = [
        item["player_points_during_stint"]
        for item in all_stints
        if item["player_points_during_stint"] is not None
    ]
    diffs = [
        item["team_point_differential_during_stint"]
        for item in all_stints
        if item["team_point_differential_during_stint"] is not None
    ]
    starts = sum(1 for item in rows if item["player_rotation"]["started_game"])
    return {
        "source": rotation.WNBA_HISTORY_SOURCE,
        "source_url": rotation.WNBA_HISTORY_SOURCE_URL,
        "source_endpoint": rotation.ROTATION_ENDPOINT,
        "data_type": "official_recent_player_rotation_context",
        "league_id": rotation.WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "team_keys_observed": team_keys,
        "requested_last_n_games": last_n_games,
        "selected_game_count": len(selected),
        "rotation_game_count": len(rows),
        "missing_rotation_game_ids": missing,
        "aggregate": {
            "stint_count": len(all_stints),
            "tracked_seconds": round(total_seconds, 1),
            "tracked_minutes": round(total_seconds / 60.0, 4),
            "tracked_minutes_per_rotation_game": round(
                total_seconds / 60.0 / len(rows), 4
            ),
            "average_stint_seconds": (
                round(total_seconds / len(all_stints), 1) if all_stints else None
            ),
            "starts_in_rotation_games": starts,
            "start_share": round(starts / len(rows), 6),
            "player_points_during_stints": round(sum(points), 4) if points else None,
            "team_point_differential_during_stints": (
                round(sum(diffs), 4) if diffs else None
            ),
            "time_weighted_usage_percentage": (
                round(
                    sum(value * seconds for value, seconds in usage) / usage_den,
                    6,
                )
                if usage_den
                else None
            ),
        },
        "games": rows,
        "verification": {
            "selected_games_come_from_official_player_game_log": True,
            "missing_rotation_games_are_reported_not_fabricated": True,
            "multi_team_history_preserved": len(team_keys) > 1,
            "rotation_context_is_descriptive_not_predictive": True,
            "no_projected_minutes_created": True,
            "no_rotation_grade_created": True,
        },
    }


def install_step19d_history_transport_resilience() -> dict[str, Any]:
    first_party._request_page_props = _request_page_props_with_bounded_retry
    rotation.get_player_recent_rotation_context = get_player_recent_rotation_context_step19d
    # Step 4V imported the function directly, so update that already-bound seam too.
    opportunity.get_player_recent_rotation_context = get_player_recent_rotation_context_step19d
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "page_request_attempts": PAGE_REQUEST_ATTEMPTS,
        "historical_transport_failure_uses_existing_missing_contract": True,
        "all_historical_games_missing_still_fails_closed": True,
        "malformed_successful_payloads_still_fail_closed": True,
        "current_availability_gates_relaxed": False,
        "projection_fabrication_allowed": False,
    }


INSTALLATION = install_step19d_history_transport_resilience()

__all__ = [
    "INSTALLATION",
    "MODEL_VERSION",
    "PAGE_REQUEST_ATTEMPTS",
    "get_player_recent_rotation_context_step19d",
    "install_step19d_history_transport_resilience",
]
