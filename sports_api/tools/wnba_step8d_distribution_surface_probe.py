"""OFF-only Step-8D joint-distribution design probe.

Consumes the certified Step-8A handoff, Step-8B official-box baseline, and
live-certified Step-8C adjusted projection. It exposes the exact five official
recent P/R/A rows plus simple population dispersion/covariance/correlation
statistics needed to choose a joint Monte Carlo family.

No simulation, sportsbook line, betting probability, persistence, or production
activation is created by this probe.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step8_context_adjustment import build_step8_context_adjusted_projection
from sports_api.wnba_step8_official_box_baseline import build_step8_official_box_baseline
from sports_api.wnba_step8_projection_handoff import get_player_game_step8_projection_handoff

REPORT_PATH = Path("step8d-distribution-surface-probe.json")
_STATS = ("points", "rebounds", "assists", "points_rebounds_assists")
_JOINT_STATS = ("points", "rebounds", "assists")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Step 8D distribution probe refuses production switches: " + ", ".join(bad))
    for key in (
        "WNBA_STEP7G_FIRST_PARTY_ENABLED",
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED",
        "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED",
    ):
        if not _truthy(os.getenv(key)):
            raise RuntimeError(f"Step 8D distribution probe requires isolated flag {key}=true.")


def _num(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Step 8D distribution probe expected numeric {label}.")
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"Step 8D distribution probe expected finite {label}.")
    return result


def _variance(values: list[float]) -> float:
    center = mean(values)
    return sum((value - center) ** 2 for value in values) / len(values)


def _covariance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise RuntimeError("Step 8D covariance received mismatched/empty samples.")
    lmean = mean(left)
    rmean = mean(right)
    return sum((l - lmean) * (r - rmean) for l, r in zip(left, right)) / len(left)


def _correlation(left: list[float], right: list[float]) -> float | None:
    lstd = pstdev(left)
    rstd = pstdev(right)
    if lstd <= 0.0 or rstd <= 0.0:
        return None
    return _covariance(left, right) / (lstd * rstd)


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])

    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    baseline = build_step8_official_box_baseline(handoff)
    adjusted = build_step8_context_adjusted_projection(handoff, baseline)

    games = baseline.get("games")
    if not isinstance(games, list) or len(games) != 5:
        raise RuntimeError("Step 8D distribution probe requires exactly five certified official box rows.")
    rows = []
    vectors: dict[str, list[float]] = {key: [] for key in ("minutes", *_STATS)}
    for row in games:
        if not isinstance(row, dict):
            raise RuntimeError("Step 8D distribution probe found malformed baseline game row.")
        sanitized = {
            "game_id": row.get("game_id"),
            "minutes": _num(row.get("minutes"), "game minutes"),
            "points": _num(row.get("points"), "game points"),
            "rebounds": _num(row.get("rebounds"), "game rebounds"),
            "assists": _num(row.get("assists"), "game assists"),
            "points_rebounds_assists": _num(row.get("points_rebounds_assists"), "game PRA"),
        }
        if abs(
            sanitized["points"] + sanitized["rebounds"] + sanitized["assists"]
            - sanitized["points_rebounds_assists"]
        ) > 1e-9:
            raise RuntimeError("Step 8D distribution probe found a game row with inconsistent PRA.")
        rows.append(sanitized)
        for key in vectors:
            vectors[key].append(sanitized[key])

    dispersion = {}
    for key, values in vectors.items():
        avg = mean(values)
        var = _variance(values)
        dispersion[key] = {
            "mean": round(avg, 6),
            "median": round(median(values), 6),
            "population_variance": round(var, 6),
            "population_stddev": round(math.sqrt(var), 6),
            "minimum": min(values),
            "maximum": max(values),
            "variance_to_mean": round(var / avg, 6) if avg > 0 else None,
            "variance_minus_mean": round(var - avg, 6),
        }

    covariance = {
        left: {
            right: round(_covariance(vectors[left], vectors[right]), 6)
            for right in _JOINT_STATS
        }
        for left in _JOINT_STATS
    }
    correlation = {
        left: {
            right: (
                round(value, 6)
                if (value := _correlation(vectors[left], vectors[right])) is not None
                else None
            )
            for right in _JOINT_STATS
        }
        for left in _JOINT_STATS
    }
    minute_correlation = {
        stat: (
            round(value, 6)
            if (value := _correlation(vectors["minutes"], vectors[stat])) is not None
            else None
        )
        for stat in _JOINT_STATS
    }

    target = adjusted.get("projection")
    if not isinstance(target, dict):
        raise RuntimeError("Step 8D distribution probe is missing Step 8C target projection.")
    adjusted_target = {
        key: _num(target.get(key), f"Step 8C target {key}")
        for key in ("minutes", *_STATS)
    }
    mean_scale = {
        stat: round(adjusted_target[stat] / dispersion[stat]["mean"], 8)
        if dispersion[stat]["mean"] > 0
        else None
        for stat in _STATS
    }

    report = {
        "data_type": "wnba_step8d_distribution_surface_probe_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "step8c_target": {
            "projection_id": adjusted.get("projection_id"),
            "projection_content_sha256": adjusted.get("projection_content_sha256"),
            "model_version": adjusted.get("model_version"),
            **adjusted_target,
        },
        "official_recent_rows": rows,
        "dispersion": dispersion,
        "joint_population_covariance": covariance,
        "joint_pearson_correlation": correlation,
        "minutes_to_stat_correlation": minute_correlation,
        "adjusted_mean_scale_vs_official_recent_mean": mean_scale,
        "design_notes": {
            "sample_game_count": len(rows),
            "covariance_is_population_covariance_over_certified_five_game_window": True,
            "small_sample_covariance_should_be_regularized_before_simulation": True,
            "p_r_a_should_not_be_assumed_independent": True,
            "official_integer_box_counts_are_distribution_evidence": True,
            "step8c_adjusted_projection_is_target_mean_not_a_distribution": True,
        },
        "safety": {
            "simulation_created": False,
            "sportsbook_called": False,
            "betting_probability_created": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8D_DISTRIBUTION_SURFACE_PROBED_NO_SIMULATION_CREATED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
