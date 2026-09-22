"""Step 5D: empirical WNBA player outcome distribution and dependence engine.

Builds a backtest-safe observed distribution from official WNBA player game logs
for one player and one target game. The exact Step 4W snapshot behind Step 5C
provides target-game identity/date; only complete played games strictly before
the target date and on the target team are eligible.

Step 5D describes observed Points/Rebounds/Assists/PRA outcomes, empirical tails,
variance, covariance, correlation, and minutes relationships. It does not change
the frozen Step 5C projection, run Monte Carlo, use sportsbook data, or create a
predictive betting probability.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import ceil, sqrt
from typing import Any

from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)
from sports_api.wnba_projection_scenarios import (
    MODEL_VERSION as SCENARIO_MODEL_VERSION,
    WNBAProjectionScenarioModelInputError,
    WNBAProjectionScenarioNotReadyError,
    WNBAProjectionScenarioUpstreamError,
    project_scenarios_from_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5D empirical outcome distribution engine"
MODEL_VERSION = "wnba_step_5d_empirical_distribution_v1"
MODEL_FAMILY = "backtest_safe_empirical_player_outcome_distribution"
MAX_RECENT_GAMES = 20
MIN_DISTRIBUTION_GAMES = 1
MAX_DISTRIBUTION_GAMES = 50
STAT_KEYS = ("points", "rebounds", "assists")
DEPENDENCE_KEYS = ("points", "rebounds", "assists", "pra")
MIN_SAMPLE_VARIANCE_GAMES = 2
MIN_DEPENDENCE_GAMES = 3


class WNBAEmpiricalDistributionNotReadyError(RuntimeError):
    pass


class WNBAEmpiricalDistributionNotFoundError(LookupError):
    pass


class WNBAEmpiricalDistributionUpstreamError(RuntimeError):
    pass


class WNBAEmpiricalDistributionModelInputError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RECENT_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _distribution_last_n(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_DISTRIBUTION_GAMES <= value <= MAX_DISTRIBUTION_GAMES
    ):
        raise ValueError("WNBA distribution_last_n_games must be an integer from 1 through 50.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _max_snapshot_age(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1440:
        raise ValueError("WNBA max_snapshot_age_minutes must be an integer from 1 through 1440.")
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _target_identity(
    readiness: dict[str, Any],
    scenarios: dict[str, Any],
) -> tuple[dict[str, Any], int, str, str, str, str]:
    if not isinstance(readiness, dict):
        raise ValueError("WNBA Step 5D readiness report must be an object.")
    state = _clean(readiness.get("readiness"))
    if state == "NOT_READY" or readiness.get("can_start_projection") is False:
        raise WNBAEmpiricalDistributionNotReadyError(
            "Step 4X marked the player/game input package NOT_READY."
        )
    if state not in {"READY", "READY_WITH_WARNINGS"} or readiness.get("can_start_projection") is not True:
        raise WNBAEmpiricalDistributionUpstreamError("Step 4X readiness state is invalid.")

    snapshot = readiness.get("snapshot")
    if readiness.get("snapshot_included") is not True or not isinstance(snapshot, dict):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 5D requires Step 4X to include the frozen Step 4W snapshot."
        )
    if not isinstance(scenarios, dict) or scenarios.get("model_version") != SCENARIO_MODEL_VERSION:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 5D received an unexpected Step 5C model version."
        )

    player_id = _to_int(snapshot.get("player_id"))
    game_id = _clean(snapshot.get("game_id"))
    focal = snapshot.get("focal_identity")
    game_identity = snapshot.get("game_identity")
    if (
        player_id is None
        or player_id <= 0
        or game_id is None
        or not isinstance(focal, dict)
        or not isinstance(game_identity, dict)
    ):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 4W target player/game identity is malformed."
        )
    team_key = _clean(focal.get("team_key"))
    opponent_key = _clean(focal.get("opponent_team_key"))
    side = _clean(focal.get("side"))
    target_date = _clean(game_identity.get("date"))
    if not team_key or not opponent_key or side not in {"away", "home"} or not target_date:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 4W focal team/opponent/date identity is incomplete."
        )
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as exc:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 4W target game date is not ISO YYYY-MM-DD."
        ) from exc

    if (
        _to_int(scenarios.get("player_id")) != player_id
        or _clean(scenarios.get("game_id")) != game_id
        or _clean(scenarios.get("team_key")) != team_key
        or _clean(scenarios.get("opponent_team_key")) != opponent_key
        or _clean(scenarios.get("side")) != side
    ):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 5C scenario identity disagrees with the frozen Step 4W snapshot."
        )

    readiness_ref = readiness.get("snapshot_reference")
    scenario_ref = scenarios.get("snapshot_reference")
    if not isinstance(readiness_ref, dict) or not isinstance(scenario_ref, dict):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 4X/5C snapshot reference is missing."
        )
    for key in ("snapshot_id", "content_sha256", "game_id", "player_id", "recent_window_games"):
        if readiness_ref.get(key) != scenario_ref.get(key):
            raise WNBAEmpiricalDistributionUpstreamError(
                f"Step 5C snapshot reference disagrees with Step 4X for {key}."
            )
    return snapshot, player_id, game_id, team_key, opponent_key, target_date


def _validate_game_log_dataset(
    dataset: dict[str, Any],
    player_id: int,
    season: int,
    season_type: str,
) -> list[dict[str, Any]]:
    if not isinstance(dataset, dict):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game log returned a non-object payload."
        )
    if _to_int(dataset.get("player_id")) != player_id:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game log returned the wrong player ID."
        )
    if _to_int(dataset.get("season")) != season:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game log returned the wrong season."
        )
    if _clean(dataset.get("season_type")) != season_type:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game log returned the wrong season type."
        )
    games = dataset.get("games")
    if not isinstance(games, list):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game log contains malformed games."
        )
    verification = dataset.get("verification")
    if isinstance(verification, dict):
        if verification.get("returned_player_ids_match_request") is False:
            raise WNBAEmpiricalDistributionUpstreamError(
                "Official WNBA player game log failed player identity verification."
            )
        if verification.get("all_game_ids_valid") is False:
            raise WNBAEmpiricalDistributionUpstreamError(
                "Official WNBA player game log failed game-ID validation."
            )
        if verification.get("all_game_ids_unique") is False:
            raise WNBAEmpiricalDistributionUpstreamError(
                "Official WNBA player game log contains duplicate game IDs."
            )
        if verification.get("all_matchup_teams_mapped_to_registry") is False:
            raise WNBAEmpiricalDistributionUpstreamError(
                "Official WNBA player game log contains unmapped matchup teams."
            )

    ids = [
        _clean(row.get("game_id"))
        for row in games
        if isinstance(row, dict) and _clean(row.get("game_id")) is not None
    ]
    duplicate_ids = sorted({game_id for game_id in ids if ids.count(game_id) > 1})
    if duplicate_ids:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game log contains duplicate game IDs."
        )
    return games


def _normalized_observation(game: dict[str, Any], player_id: int) -> dict[str, Any] | None:
    if not isinstance(game, dict):
        return None
    if _to_int(game.get("player_id")) not in {None, player_id}:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Official WNBA player game-log row has the wrong player ID."
        )
    game_id = _clean(game.get("game_id"))
    game_date = _clean(game.get("game_date"))
    matchup = game.get("matchup")
    if (
        not game_id
        or len(game_id) != 10
        or not game_id.isdigit()
        or not game_date
        or not isinstance(matchup, dict)
    ):
        return None
    try:
        datetime.strptime(game_date, "%Y-%m-%d")
    except ValueError:
        return None
    team_key = _clean(matchup.get("team_key"))
    opponent_key = _clean(matchup.get("opponent_team_key"))
    location = _clean(matchup.get("location"))
    minutes = _to_float(game.get("minutes"))
    points = _to_int(game.get("points"))
    rebounds = _to_int(game.get("rebounds"))
    assists = _to_int(game.get("assists"))
    if (
        not team_key
        or not opponent_key
        or team_key == opponent_key
        or minutes is None
        or minutes <= 0
        or points is None
        or rebounds is None
        or assists is None
        or min(points, rebounds, assists) < 0
    ):
        return None
    return {
        "game_id": game_id,
        "game_date": game_date,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "location": location,
        "minutes": round(minutes, 4),
        "points": points,
        "rebounds": rebounds,
        "assists": assists,
        "pra": points + rebounds + assists,
        "result": _clean(game.get("result")),
    }


def _select_observations(
    games: list[dict[str, Any]],
    *,
    player_id: int,
    target_game_id: str,
    target_date: str,
    target_team_key: str,
    distribution_last_n_games: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    excluded_same_or_future: list[str] = []
    excluded_target_game: list[str] = []
    excluded_prior_team: list[str] = []
    excluded_incomplete: list[str | None] = []

    for raw in games:
        game_id = _clean(raw.get("game_id")) if isinstance(raw, dict) else None
        normalized = _normalized_observation(raw, player_id)
        if normalized is None:
            excluded_incomplete.append(game_id)
            continue
        if normalized["game_id"] == target_game_id:
            excluded_target_game.append(normalized["game_id"])
            continue
        if normalized["game_date"] >= target_date:
            excluded_same_or_future.append(normalized["game_id"])
            continue
        if normalized["team_key"] != target_team_key:
            excluded_prior_team.append(normalized["game_id"])
            continue
        eligible.append(normalized)

    eligible.sort(key=lambda row: (row["game_date"], row["game_id"]), reverse=True)
    selected = eligible[:distribution_last_n_games]
    if not selected:
        raise WNBAEmpiricalDistributionNotFoundError(
            "No complete target-team WNBA player game-log observations exist strictly before the target game date."
        )
    return selected, {
        "source_game_log_row_count": len(games),
        "eligible_pregame_target_team_game_count": len(eligible),
        "requested_distribution_last_n_games": distribution_last_n_games,
        "selected_game_count": len(selected),
        "selected_game_ids": [row["game_id"] for row in selected],
        "selected_oldest_game_date": selected[-1]["game_date"],
        "selected_newest_game_date": selected[0]["game_date"],
        "excluded_target_game_ids": excluded_target_game,
        "excluded_same_date_or_future_game_ids": excluded_same_or_future,
        "excluded_prior_team_game_ids": excluded_prior_team,
        "excluded_incomplete_or_nonappearance_game_ids": excluded_incomplete,
        "strictly_before_target_date": True,
        "target_team_only": True,
        "same_date_rows_excluded_to_avoid_ordering_ambiguity": True,
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _nearest_rank(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if probability <= 0:
        return ordered[0]
    if probability >= 1:
        return ordered[-1]
    return ordered[max(1, ceil(probability * len(ordered))) - 1]


def _modes(values: list[float]) -> list[float]:
    counts: dict[float, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    highest = max(counts.values())
    return sorted(value for value, count in counts.items() if count == highest)


def _variance(values: list[float], *, sample: bool) -> float | None:
    n = len(values)
    if n == 0 or (sample and n < 2):
        return None
    mean = _mean(values)
    denominator = n - 1 if sample else n
    return sum((value - mean) ** 2 for value in values) / denominator


def _distribution_table(values: list[int]) -> list[dict[str, Any]]:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = len(values)
    ordered = sorted(counts)
    cumulative = 0
    rows = []
    for value in ordered:
        count = counts[value]
        cumulative += count
        tail = sum(counts[item] for item in ordered if item >= value)
        rows.append(
            {
                "value": value,
                "count": count,
                "frequency": round(count / total, 8),
                "empirical_cdf_at_or_below": round(cumulative / total, 8),
                "empirical_tail_at_or_above": round(tail / total, 8),
            }
        )
    return rows


def _stat_summary(values: list[int]) -> dict[str, Any]:
    floats = [float(value) for value in values]
    population_variance = _variance(floats, sample=False)
    sample_variance = _variance(floats, sample=True)
    return {
        "game_count": len(values),
        "mean": round(_mean(floats), 6),
        "median": round(_median(floats), 6),
        "modes": _modes(floats),
        "minimum": min(values),
        "maximum": max(values),
        "population_variance": round(population_variance, 8) if population_variance is not None else None,
        "population_stddev": round(sqrt(population_variance), 8) if population_variance is not None else None,
        "sample_variance": round(sample_variance, 8) if sample_variance is not None else None,
        "sample_stddev": round(sqrt(sample_variance), 8) if sample_variance is not None else None,
        "empirical_quantiles": {
            "p10": _nearest_rank(floats, 0.10),
            "p25": _nearest_rank(floats, 0.25),
            "p50": _nearest_rank(floats, 0.50),
            "p75": _nearest_rank(floats, 0.75),
            "p90": _nearest_rank(floats, 0.90),
            "method": "nearest_rank_empirical",
        },
        "observed_distribution": _distribution_table(values),
    }


def _covariance(x: list[float], y: list[float], *, sample: bool) -> float | None:
    if len(x) != len(y) or not x or (sample and len(x) < 2):
        return None
    mx, my = _mean(x), _mean(y)
    denominator = len(x) - 1 if sample else len(x)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / denominator


def _correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    vx = _variance(x, sample=True)
    vy = _variance(y, sample=True)
    if vx is None or vy is None or vx <= 0 or vy <= 0:
        return None
    cov = _covariance(x, y, sample=True)
    return None if cov is None else cov / sqrt(vx * vy)


def _matrix(
    vectors: dict[str, list[float]], *, correlation: bool
) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for left in DEPENDENCE_KEYS:
        out[left] = {}
        for right in DEPENDENCE_KEYS:
            value = (
                _correlation(vectors[left], vectors[right])
                if correlation
                else _covariance(vectors[left], vectors[right], sample=True)
            )
            out[left][right] = round(value, 8) if value is not None else None
    return out


def _dependence(observations: list[dict[str, Any]]) -> dict[str, Any]:
    vectors = {
        key: [float(row[key]) for row in observations]
        for key in DEPENDENCE_KEYS
    }
    minutes = [float(row["minutes"]) for row in observations]
    sample_covariance = _matrix(vectors, correlation=False)
    correlations = _matrix(vectors, correlation=True)
    minutes_correlations = {}
    for key in DEPENDENCE_KEYS:
        value = _correlation(minutes, vectors[key])
        minutes_correlations[key] = round(value, 8) if value is not None else None
    zero_variance = (
        [
            key
            for key in DEPENDENCE_KEYS
            if (_variance(vectors[key], sample=True) or 0.0) <= 0.0
        ]
        if len(observations) >= 2
        else list(DEPENDENCE_KEYS)
    )
    return {
        "game_count": len(observations),
        "sample_covariance_matrix": sample_covariance,
        "pearson_correlation_matrix": correlations,
        "minutes_pearson_correlation_with_stats": minutes_correlations,
        "p_r_a_monte_carlo_basis": {
            "stats": list(STAT_KEYS),
            "sample_covariance_matrix": {
                left: {right: sample_covariance[left][right] for right in STAT_KEYS}
                for left in STAT_KEYS
            },
            "pearson_correlation_matrix": {
                left: {right: correlations[left][right] for right in STAT_KEYS}
                for left in STAT_KEYS
            },
        },
        "zero_sample_variance_stats": zero_variance,
        "dependence_estimation_available": len(observations) >= MIN_DEPENDENCE_GAMES,
        "minimum_games_for_step_5d_dependence_readiness": MIN_DEPENDENCE_GAMES,
        "semantics": (
            "Covariance/correlation are descriptive sample statistics from complete observed pregame rows. "
            "PRA is an exact sum of P+R+A, so the four-variable covariance structure is algebraically dependent."
        ),
    }


def build_empirical_outcome_distribution(
    readiness: dict[str, Any],
    scenarios: dict[str, Any],
    game_log: dict[str, Any],
    *,
    season: int,
    season_type: str,
    distribution_last_n_games: int,
) -> dict[str, Any]:
    distribution_last_n_games = _distribution_last_n(distribution_last_n_games)
    snapshot, player_id, game_id, team_key, opponent_key, target_date = _target_identity(
        readiness, scenarios
    )
    games = _validate_game_log_dataset(game_log, player_id, season, season_type)
    observations, window = _select_observations(
        games,
        player_id=player_id,
        target_game_id=game_id,
        target_date=target_date,
        target_team_key=team_key,
        distribution_last_n_games=distribution_last_n_games,
    )

    summaries = {
        key: _stat_summary([int(row[key]) for row in observations])
        for key in DEPENDENCE_KEYS
    }
    dependence = _dependence(observations)
    sample_ready = len(observations) >= MIN_SAMPLE_VARIANCE_GAMES
    dependence_ready = (
        len(observations) >= MIN_DEPENDENCE_GAMES
        and not dependence["zero_sample_variance_stats"]
    )

    scenario_base = _dig(scenarios, "scenarios", "base")
    if not isinstance(scenario_base, dict):
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 5C scenario payload is missing the BASE scenario."
        )
    base_values: dict[str, float] = {}
    for key in DEPENDENCE_KEYS:
        value = _to_float(scenario_base.get(key))
        if value is None or value < 0:
            raise WNBAEmpiricalDistributionUpstreamError(
                f"Step 5C BASE scenario has invalid {key}."
            )
        base_values[key] = value
    if abs(base_values["pra"] - sum(base_values[key] for key in STAT_KEYS)) > 0.001:
        raise WNBAEmpiricalDistributionUpstreamError(
            "Step 5C BASE PRA does not equal BASE points + rebounds + assists."
        )

    model_config = {
        "model_version": MODEL_VERSION,
        "scenario_model_version": SCENARIO_MODEL_VERSION,
        "distribution_last_n_games": distribution_last_n_games,
        "target_team_only": True,
        "strictly_before_target_date": True,
        "exclude_same_date": True,
        "complete_case_only": True,
        "quantile_method": "nearest_rank_empirical",
        "sample_variance_denominator": "n-1",
        "minimum_sample_variance_games": MIN_SAMPLE_VARIANCE_GAMES,
        "minimum_dependence_games": MIN_DEPENDENCE_GAMES,
    }
    fingerprint_payload = {
        "snapshot_content_sha256": snapshot.get("content_sha256"),
        "scenario_fingerprint_sha256": scenarios.get("scenario_fingerprint_sha256"),
        "game_log_source": game_log.get("source"),
        "model_config": model_config,
        "observations": observations,
        "summaries": summaries,
        "dependence": dependence,
    }
    distribution_hash = _canonical_hash(fingerprint_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_backtest_safe_empirical_player_outcome_distribution",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "distribution_id": f"wnba-5d-{game_id}-{player_id}-{distribution_hash[:16]}",
        "distribution_fingerprint_sha256": distribution_hash,
        "season": season,
        "season_type": season_type,
        "game_id": game_id,
        "target_game_date": target_date,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "snapshot_reference": deepcopy(readiness.get("snapshot_reference")),
        "step_5c_scenario_reference": {
            "model_version": scenarios.get("model_version"),
            "scenario_id": scenarios.get("scenario_id"),
            "scenario_fingerprint_sha256": scenarios.get("scenario_fingerprint_sha256"),
        },
        "step_5c_base_projection": {
            key: scenario_base.get(key)
            for key in ("minutes", "points", "rebounds", "assists", "pra")
        },
        "official_game_log_reference": {
            "source": game_log.get("source"),
            "source_url": game_log.get("source_url"),
            "source_endpoint": game_log.get("source_endpoint"),
            "retrieved_at_utc": game_log.get("retrieved_at_utc"),
            "cache_hit": game_log.get("cache_hit"),
            "cache_ttl_seconds": game_log.get("cache_ttl_seconds"),
        },
        "distribution_window": window,
        "observations": observations,
        "summary_by_stat": summaries,
        "dependence": dependence,
        "data_quality": {
            "selected_complete_game_count": len(observations),
            "sample_variance_available": sample_ready,
            "dependence_sample_size_sufficient": len(observations) >= MIN_DEPENDENCE_GAMES,
            "dependence_ready_without_zero_variance": dependence_ready,
            "zero_sample_variance_stats": deepcopy(dependence["zero_sample_variance_stats"]),
            "complete_case_only": True,
            "no_missing_stat_imputation": True,
            "target_team_only": True,
            "future_leakage_guard_applied": True,
        },
        "model_config": model_config,
        "semantics": {
            "observed_empirical_frequencies_are_not_predictive_probabilities": True,
            "sample_variance_is_descriptive_not_forecast_variance": True,
            "covariance_is_observed_sample_dependence_not_causal_relationship": True,
            "step_5c_central_projection_unchanged": True,
            "distribution_is_conditioned_only_by_date_and_target_team_not_by_sportsbook": True,
            "retrieval_timestamp_is_metadata_not_distribution_fingerprint_content": True,
        },
        "guardrails": {
            "step_4x_not_ready_blocks_5d": True,
            "target_game_and_same_date_rows_excluded": True,
            "future_game_rows_excluded": True,
            "prior_team_rows_excluded": True,
            "zero_or_missing_minutes_rows_excluded": True,
            "missing_p_r_a_rows_excluded": True,
            "no_stat_imputation_created": True,
            "no_projection_adjustment_created": True,
            "no_predictive_probability_created": True,
            "no_sportsbook_data_used": True,
            "no_betting_edge_created": True,
            "no_monte_carlo_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "step_4x_readiness_state_checked": True,
            "step_5c_model_version_checked": True,
            "step_5c_and_step_4w_identity_match": True,
            "step_5c_and_step_4x_snapshot_reference_match": True,
            "official_game_log_player_identity_checked": True,
            "official_game_log_season_and_type_checked": True,
            "all_selected_rows_strictly_predate_target_date": True,
            "all_selected_rows_match_target_team": True,
            "pra_recomputed_as_points_plus_rebounds_plus_assists": True,
            "step_5c_base_pra_component_sum_checked": True,
            "distribution_fingerprint_created": True,
        },
    }


def get_player_game_empirical_outcome_distribution(
    player_id: int,
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    distribution_last_n_games: int = 10,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    distribution_last_n_games = _distribution_last_n(distribution_last_n_games)
    require_current_availability = _bool(
        require_current_availability, "require_current_availability"
    )
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)

    try:
        readiness = get_player_game_model_input_readiness(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            require_current_availability=require_current_availability,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=False,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            include_snapshot=True,
        )
    except WNBAModelInputReadinessNotFoundError as exc:
        raise WNBAEmpiricalDistributionNotFoundError(str(exc)) from exc
    except WNBAModelInputReadinessUpstreamError as exc:
        raise WNBAEmpiricalDistributionUpstreamError(str(exc)) from exc

    try:
        scenarios = project_scenarios_from_readiness(readiness)
    except WNBAProjectionScenarioNotReadyError as exc:
        raise WNBAEmpiricalDistributionNotReadyError(str(exc)) from exc
    except WNBAProjectionScenarioModelInputError as exc:
        raise WNBAEmpiricalDistributionModelInputError(str(exc)) from exc
    except WNBAProjectionScenarioUpstreamError as exc:
        raise WNBAEmpiricalDistributionUpstreamError(str(exc)) from exc

    try:
        game_log = get_player_game_log_dataset(
            player_id,
            season,
            season_type=season_type,
        )
    except WNBAHistoryNotFoundError as exc:
        raise WNBAEmpiricalDistributionNotFoundError(str(exc)) from exc
    except WNBAHistoryUpstreamError as exc:
        raise WNBAEmpiricalDistributionUpstreamError(str(exc)) from exc

    return build_empirical_outcome_distribution(
        readiness,
        scenarios,
        game_log,
        season=season,
        season_type=season_type,
        distribution_last_n_games=distribution_last_n_games,
    )
