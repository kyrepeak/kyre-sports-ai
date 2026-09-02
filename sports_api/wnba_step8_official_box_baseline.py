"""Step 8B official recent-box statistical baseline.

Consumes only a certified Step-8A handoff for scope/identity, then reloads the
exact five official WNBA.com box scores already identified by the handoff's
certified player-advanced component. This layer exists because Step-4U event
features are deliberately feature-eligible PBP counts and must not be mislabeled
as complete official player P/R/A history.

No projection, minutes forecast, teammate redistribution, matchup adjustment,
Monte Carlo, sportsbook probability, or persistence is created here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from statistics import mean, median, pstdev
from typing import Any, Mapping

from sports_api.wnba_step7g_first_party_history import (
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_game_box_score_dataset,
)
from sports_api.wnba_step8_projection_handoff import (
    HANDOFF_RELEASE_ID,
    SCHEMA_VERSION as STEP8A_SCHEMA_VERSION,
)

SOURCE = "Kyre Sports API WNBA Step 8B official recent box baseline"
SCHEMA_VERSION = "wnba_step_8b_box_baseline_v1"
BASELINE_RELEASE_ID = "wnba_step8b_official_recent_box_baseline_2026_regular_v1"
EXPECTED_GAME_COUNT = 5
CERTIFIED_SEASON = 2026
CERTIFIED_SEASON_TYPE = "Regular Season"
REGULAR_GAME_PREFIX = "10226"


class WNBAStep8OfficialBoxBaselineNotFoundError(LookupError):
    """Raised when an exact official recent-game baseline cannot be constructed."""


class WNBAStep8OfficialBoxBaselineUpstreamError(RuntimeError):
    """Raised when certified handoff/official box evidence disagrees or is malformed."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WNBAStep8OfficialBoxBaselineUpstreamError(f"{label} is missing or malformed.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise WNBAStep8OfficialBoxBaselineUpstreamError(f"{label} is missing or malformed.")
    return value


def _validate_handoff(handoff: Mapping[str, Any]) -> tuple[int, str, dict[str, Any], dict[str, Any]]:
    if not isinstance(handoff, Mapping):
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B requires a Step-8A handoff object.")
    if handoff.get("data_type") != "certified_pre_projection_model_handoff":
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B received the wrong Step-8A handoff type.")
    if handoff.get("schema_version") != STEP8A_SCHEMA_VERSION:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B received an unsupported Step-8A schema.")
    if handoff.get("handoff_release_id") != HANDOFF_RELEASE_ID:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B received an unexpected Step-8A release ID.")
    if handoff.get("projection_execution_authorized") is not True:
        raise WNBAStep8OfficialBoxBaselineNotFoundError("Step 8A does not authorize model-layer execution.")
    if handoff.get("production_activation_allowed") is not False:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8A unexpectedly allows production activation.")

    snapshot = _require_dict(handoff.get("snapshot"), "Step 8A included snapshot")
    reference = _require_dict(handoff.get("snapshot_reference"), "Step 8A snapshot reference")
    player_id = _to_int(snapshot.get("player_id"))
    game_id = _clean(snapshot.get("game_id"))
    if player_id is None or player_id <= 0 or game_id is None:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8A snapshot has invalid game/player identity.")
    if reference.get("player_id") != player_id or _clean(reference.get("game_id")) != game_id:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8A snapshot reference disagrees with included snapshot.")
    if snapshot.get("season") != CERTIFIED_SEASON or snapshot.get("season_type") != CERTIFIED_SEASON_TYPE:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B only accepts the certified 2026 Regular Season handoff.")
    if snapshot.get("recent_window_games") != EXPECTED_GAME_COUNT:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B requires the certified five-game recent window.")
    return player_id, game_id, snapshot, reference


def _advanced_scope(
    snapshot: dict[str, Any],
    player_id: int,
) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, Any]]:
    inputs = _require_dict(snapshot.get("inputs"), "Step 8A snapshot inputs")
    advanced = _require_dict(inputs.get("player_advanced"), "Step 8A player advanced input")
    if advanced.get("data_type") != "official_advanced_player_stats":
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B player advanced input has wrong data type.")
    if advanced.get("season") != CERTIFIED_SEASON or advanced.get("season_type") != CERTIFIED_SEASON_TYPE:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B player advanced scope is wrong.")
    if advanced.get("last_n_games") != EXPECTED_GAME_COUNT:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B player advanced input is not the five-game window.")
    filters = _require_dict(advanced.get("filters"), "Step 8B player advanced filters")
    if _to_int(filters.get("player_id")) != player_id:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B player advanced filter has wrong player ID.")
    if advanced.get("verification", {}).get("all_selected_games_final") is not True:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced input did not verify all games final.")
    if advanced.get("verification", {}).get("all_selected_game_ids_certified_regular_season") is not True:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced input did not certify regular-season game IDs.")
    if advanced.get("verification", {}).get("box_schedule_identity_cross_checked") is not True:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced input lacks box/schedule identity verification.")
    if advanced.get("verification", {}).get("third_party_sources_used") is not False:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced input unexpectedly used a third party.")

    ids = _require_list(advanced.get("selected_game_ids"), "Step 8B advanced selected_game_ids")
    game_ids = [str(value).strip() for value in ids]
    if len(game_ids) != EXPECTED_GAME_COUNT or len(set(game_ids)) != EXPECTED_GAME_COUNT:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B requires five unique selected official game IDs.")
    if not all(len(gid) == 10 and gid.isdigit() and gid.startswith(REGULAR_GAME_PREFIX) for gid in game_ids):
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B selected game IDs include a non-certified family.")

    evidence_rows = _require_list(advanced.get("identity_evidence"), "Step 8B advanced identity_evidence")
    by_game: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced identity evidence contains malformed row.")
        gid = _clean(row.get("game_id"))
        if gid is None or gid in by_game:
            raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced identity evidence has missing/duplicate game ID.")
        by_game[gid] = row
    if set(by_game) != set(game_ids):
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced identity evidence does not exactly cover selected games.")

    players = _require_list(advanced.get("players"), "Step 8B advanced players")
    if len(players) != 1 or not isinstance(players[0], dict):
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced input must contain exactly one player row.")
    player_row = players[0]
    if _to_int(player_row.get("player_id")) != player_id:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced player row has wrong player ID.")
    return game_ids, by_game, player_row


def _find_box_player(box: dict[str, Any], player_id: int, game_id: str) -> tuple[dict[str, Any], str]:
    matches: list[tuple[dict[str, Any], str]] = []
    for side in ("away", "home"):
        team = _require_dict(box.get(side), f"Step 8B box {game_id} {side}")
        players = _require_list(team.get("players"), f"Step 8B box {game_id} {side}.players")
        for player in players:
            if isinstance(player, dict) and _to_int(player.get("player_id")) == player_id:
                matches.append((player, side))
    if len(matches) != 1:
        raise WNBAStep8OfficialBoxBaselineNotFoundError(
            f"Step 8B player {player_id} resolved {len(matches)} times in official box {game_id}."
        )
    return matches[0]


def _numeric_stat(stats: dict[str, Any], key: str, game_id: str, *, integer: bool = True) -> float:
    value = _to_int(stats.get(key)) if integer else _to_float(stats.get(key))
    if value is None or value < 0:
        raise WNBAStep8OfficialBoxBaselineUpstreamError(
            f"Step 8B official box {game_id} has invalid player stat {key!r}."
        )
    return float(value)


def _game_row(
    box: dict[str, Any],
    player_id: int,
    game_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if _clean(box.get("game_id")) != game_id:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B official box returned wrong game ID.")
    verification = _require_dict(box.get("verification"), f"Step 8B box {game_id}.verification")
    for key in ("requested_game_id_matches_source", "teams_mapped_to_registry", "home_away_distinct", "player_ids_unique"):
        if verification.get(key) is not True:
            raise WNBAStep8OfficialBoxBaselineUpstreamError(
                f"Step 8B official box {game_id} failed verification {key!r}."
            )

    player, side = _find_box_player(box, player_id, game_id)
    stats = _require_dict(player.get("stats"), f"Step 8B box {game_id} focal player stats")
    if player.get("appeared") is not True:
        raise WNBAStep8OfficialBoxBaselineNotFoundError(
            f"Step 8B focal player did not appear in official box {game_id}."
        )
    team_key = _clean(player.get("team_key"))
    official_team_id = _to_int(player.get("official_team_id"))
    if team_key is None or official_team_id is None:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B official box player identity is incomplete.")
    if evidence.get("player_resolved_once") is not True or evidence.get("box_schedule_identity_match") is not True:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced identity evidence is not certified for selected game.")
    if _to_int(evidence.get("player_id")) != player_id:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B advanced identity evidence has wrong player ID.")
    if _clean(evidence.get("player_team_key")) != team_key:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B official box team disagrees with handoff identity evidence.")
    if _to_int(evidence.get("player_official_team_id")) != official_team_id:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B official team ID disagrees with handoff identity evidence.")
    if _clean(evidence.get("player_side")) != side:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B official box side disagrees with handoff identity evidence.")

    minutes = _numeric_stat(stats, "minutes", game_id, integer=False)
    if minutes <= 0.0 or minutes > 60.0:
        raise WNBAStep8OfficialBoxBaselineUpstreamError(f"Step 8B official minutes are implausible in {game_id}: {minutes}.")
    points = _numeric_stat(stats, "points", game_id)
    rebounds = _numeric_stat(stats, "rebounds", game_id)
    assists = _numeric_stat(stats, "assists", game_id)
    return {
        "game_id": game_id,
        "player_id": player_id,
        "player_name": player.get("full_name"),
        "team_key": team_key,
        "official_team_id": official_team_id,
        "side": side,
        "minutes": round(minutes, 4),
        "points": int(points),
        "rebounds": int(rebounds),
        "assists": int(assists),
        "points_rebounds_assists": int(points + rebounds + assists),
        "field_goals_attempted": int(_numeric_stat(stats, "field_goals_attempted", game_id)),
        "free_throws_attempted": int(_numeric_stat(stats, "free_throws_attempted", game_id)),
        "turnovers": int(_numeric_stat(stats, "turnovers", game_id)),
        "appeared": True,
        "handoff_identity_match": True,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    minutes = [float(row["minutes"]) for row in rows]
    points = [float(row["points"]) for row in rows]
    rebounds = [float(row["rebounds"]) for row in rows]
    assists = [float(row["assists"]) for row in rows]
    pra = [float(row["points_rebounds_assists"]) for row in rows]
    total_minutes = sum(minutes)
    if total_minutes <= 0:
        raise WNBAStep8OfficialBoxBaselineUpstreamError("Step 8B total official minutes are zero.")

    def stats(values: list[float]) -> dict[str, float]:
        avg = mean(values)
        return {
            "mean": round(avg, 6),
            "median": round(median(values), 6),
            "minimum": round(min(values), 6),
            "maximum": round(max(values), 6),
            "population_stddev": round(pstdev(values) if len(values) > 1 else 0.0, 6),
        }

    return {
        "game_count": len(rows),
        "minutes": stats(minutes),
        "points": stats(points),
        "rebounds": stats(rebounds),
        "assists": stats(assists),
        "points_rebounds_assists": stats(pra),
        "totals": {
            "minutes": round(total_minutes, 6),
            "points": int(sum(points)),
            "rebounds": int(sum(rebounds)),
            "assists": int(sum(assists)),
            "points_rebounds_assists": int(sum(pra)),
        },
        "official_per_minute_rates": {
            "points": round(sum(points) / total_minutes, 8),
            "rebounds": round(sum(rebounds) / total_minutes, 8),
            "assists": round(sum(assists) / total_minutes, 8),
            "points_rebounds_assists": round(sum(pra) / total_minutes, 8),
        },
    }


def build_step8_official_box_baseline(handoff: Mapping[str, Any]) -> dict[str, Any]:
    player_id, requested_game_id, snapshot, reference = _validate_handoff(handoff)
    game_ids, evidence_by_game, advanced_player = _advanced_scope(snapshot, player_id)
    rows: list[dict[str, Any]] = []
    for game_id in game_ids:
        try:
            box = get_first_party_game_box_score_dataset(game_id, CERTIFIED_SEASON)
        except WNBAStep7GFirstPartyNotFoundError as exc:
            raise WNBAStep8OfficialBoxBaselineNotFoundError(str(exc)) from exc
        except WNBAStep7GFirstPartyUpstreamError as exc:
            raise WNBAStep8OfficialBoxBaselineUpstreamError(str(exc)) from exc
        rows.append(_game_row(box, player_id, game_id, evidence_by_game[game_id]))

    if len(rows) != EXPECTED_GAME_COUNT:
        raise WNBAStep8OfficialBoxBaselineNotFoundError("Step 8B did not reconstruct exactly five official box games.")
    summary = _summary(rows)
    advanced_minutes = _to_float(advanced_player.get("minutes"))
    if advanced_minutes is None or abs(advanced_minutes - summary["minutes"]["mean"]) > 0.001:
        raise WNBAStep8OfficialBoxBaselineUpstreamError(
            "Step 8B official box average minutes disagree with the certified advanced input."
        )
    latest_team_key = _clean(rows[0].get("team_key"))
    focal_team_key = _clean(snapshot.get("focal_identity", {}).get("team_key"))
    if latest_team_key != focal_team_key:
        raise WNBAStep8OfficialBoxBaselineUpstreamError(
            "Step 8B most recent official box team disagrees with current focal team identity."
        )

    hash_content = {
        "schema_version": SCHEMA_VERSION,
        "baseline_release_id": BASELINE_RELEASE_ID,
        "step8a_handoff_content_sha256": handoff.get("handoff_content_sha256"),
        "step4w_snapshot_content_sha256": reference.get("content_sha256"),
        "requested_game_id": requested_game_id,
        "player_id": player_id,
        "selected_game_ids": game_ids,
        "games": rows,
        "summary": summary,
    }
    digest = _canonical_hash(hash_content)
    return {
        "source": SOURCE,
        "data_type": "official_recent_player_box_stat_baseline",
        "schema_version": SCHEMA_VERSION,
        "baseline_release_id": BASELINE_RELEASE_ID,
        "baseline_id": f"wnba-8b-box-{player_id}-{digest[:16]}",
        "baseline_content_sha256": digest,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": CERTIFIED_SEASON,
        "season_type": CERTIFIED_SEASON_TYPE,
        "requested_game_id": requested_game_id,
        "player_id": player_id,
        "current_team_key": focal_team_key,
        "selected_game_ids": game_ids,
        "games": rows,
        "summary": summary,
        "provenance": {
            "step8a_handoff_id": handoff.get("handoff_id"),
            "step8a_handoff_content_sha256": handoff.get("handoff_content_sha256"),
            "step4w_snapshot_id": reference.get("snapshot_id"),
            "step4w_snapshot_content_sha256": reference.get("content_sha256"),
            "game_ids_from_certified_handoff_player_advanced": True,
            "boxes_reloaded_from_official_wnba_com": True,
        },
        "semantics": {
            "points_rebounds_assists_are_complete_official_box_counts": True,
            "pbp_feature_counts_are_not_used_as_official_box_totals": True,
            "recent_window_is_exactly_five_certified_completed_regular_games": True,
            "multi_team_recent_history_is_preserved_if_present": True,
        },
        "guardrails": {
            "baseline_is_observed_history_not_projection": True,
            "no_projected_minutes_created": True,
            "no_teammate_opportunity_redistribution_created": True,
            "no_matchup_adjustment_created": True,
            "no_monte_carlo_created": True,
            "no_sportsbook_data_created": True,
            "no_betting_probability_created": True,
            "no_persistence_created": True,
        },
        "verification": {
            "step8a_handoff_identity_verified": True,
            "advanced_selected_game_ids_used_exactly": True,
            "all_game_ids_unique_certified_regular_family": True,
            "player_resolved_exactly_once_per_box": True,
            "box_player_team_identity_matches_handoff_evidence": True,
            "advanced_and_box_average_minutes_match": True,
            "most_recent_team_matches_current_focal_team": True,
            "third_party_sources_used": False,
            "no_projection_created": True,
        },
    }
