"""Step 9A: frozen Step-8 distribution -> prop threshold pricing contract.

This layer is deliberately post-projection. It consumes a completed, hash-valid,
converged Step-8D joint P/R/A probability distribution and applies a caller-supplied
statistical line without changing the basketball projection or Monte Carlo draws.

It produces raw Over/Push/Under probabilities plus resolved non-push fair prices.
No sportsbook quote is accepted here, no vig is removed, no EV is calculated, and
no sportsbook/network/persistence/production path is activated.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping

from sports_api import wnba_step8_release_freeze as step8_freeze
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

SOURCE = "Kyre Sports API WNBA Step 9A certified Step-8 threshold pricing"
SCHEMA_VERSION = "wnba_step_9a_threshold_pricing_v1"
MODEL_VERSION = "wnba_step9a_post_step8_threshold_pricing_2026_regular_v1"
RELEASE_ID = "wnba_step9a_threshold_pricing_2026_regular_season_v1"
STEP9_THRESHOLD_PRICING_ENABLED_ENV = "WNBA_STEP9_THRESHOLD_PRICING_ENABLED"
MAX_PROP_LINE = 250.0
SUPPORTED_STATS = ("points", "rebounds", "assists", "pra")
STAT_ALIASES = {
    "points": "points",
    "point": "points",
    "pts": "points",
    "rebounds": "rebounds",
    "rebound": "rebounds",
    "reb": "rebounds",
    "rebs": "rebounds",
    "assists": "assists",
    "assist": "assists",
    "ast": "assists",
    "asts": "assists",
    "pra": "pra",
    "points+rebounds+assists": "pra",
    "points rebounds assists": "pra",
}
_STEP8_STAT_KEY = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "pra": "points_rebounds_assists",
}
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep9ThresholdPricingDisabledError(RuntimeError):
    """Raised when Step 9A is not explicitly enabled for the current process."""


class WNBAStep9ThresholdPricingNotReadyError(RuntimeError):
    """Raised when Step 8 evidence is valid but not betting-grade/converged."""


class WNBAStep9ThresholdPricingUpstreamError(RuntimeError):
    """Raised when the supplied frozen Step-8 payload is malformed or tampered."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step9_threshold_pricing_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP9_THRESHOLD_PRICING_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep9ThresholdPricingDisabledError(
            "Step 9A refuses to run while production switches are enabled: "
            + ", ".join(bad)
        )
    if not _truthy(source.get(STEP9_THRESHOLD_PRICING_ENABLED_ENV)):
        raise WNBAStep9ThresholdPricingDisabledError(
            f"Step 9A requires {STEP9_THRESHOLD_PRICING_ENABLED_ENV}=true."
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(
        len(text) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in text)
    )


def _stat(value: str) -> str:
    text = " ".join(str(value).strip().casefold().split())
    result = STAT_ALIASES.get(text)
    if result is None:
        raise ValueError(
            f"Unsupported WNBA prop stat {value!r}. Allowed canonical values: "
            + ", ".join(SUPPORTED_STATS)
            + "."
        )
    return result


def _line(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}."
        ) from exc
    if not math.isfinite(number) or not 0.0 <= number <= MAX_PROP_LINE:
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    return round(number, 6)


def _validate_identity(result: Mapping[str, Any]) -> tuple[str, int, str, str]:
    game_id = str(result.get("game_id") or "").strip()
    try:
        player_id = int(result.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received an invalid Step-8 player identity."
        ) from exc
    team_key = str(result.get("team_key") or "").strip()
    opponent_key = str(result.get("opponent_team_key") or "").strip()
    if len(game_id) != 10 or not game_id.isdigit() or player_id <= 0:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received an invalid Step-8 game/player identity."
        )
    if not team_key or not opponent_key or team_key == opponent_key:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received invalid Step-8 team/opponent identity."
        )
    return game_id, player_id, team_key, opponent_key


def _validate_step8_hash(result: Mapping[str, Any]) -> str:
    observed = str(result.get("result_content_sha256") or "").strip().lower()
    if not _valid_sha256(observed):
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A requires a valid Step-8 result_content_sha256."
        )
    hash_surface = dict(result)
    hash_surface.pop("generated_at_utc", None)
    hash_surface.pop("result_content_sha256", None)
    expected = _canonical_hash(hash_surface)
    if observed != expected:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A detected a Step-8 content-hash mismatch."
        )
    return observed


def _validate_probability_mass(
    result: Mapping[str, Any], stat_key: str
) -> list[dict[str, Any]]:
    distributions = result.get("distributions")
    distribution = distributions.get(stat_key) if isinstance(distributions, Mapping) else None
    rows = distribution.get("probability_mass") if isinstance(distribution, Mapping) else None
    if not isinstance(rows, list) or not rows:
        raise WNBAStep9ThresholdPricingUpstreamError(
            f"Step 9A missing Step-8 probability mass for {stat_key}."
        )
    seen: set[int] = set()
    total = 0.0
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise WNBAStep9ThresholdPricingUpstreamError(
                f"Step 9A found malformed Step-8 probability mass for {stat_key}."
            )
        value = row.get("value")
        probability = row.get("probability")
        if isinstance(value, bool):
            raise WNBAStep9ThresholdPricingUpstreamError(
                f"Step 9A found a non-integer outcome for {stat_key}."
            )
        try:
            value_float = float(value)
            probability_float = float(probability)
        except (TypeError, ValueError) as exc:
            raise WNBAStep9ThresholdPricingUpstreamError(
                f"Step 9A found nonnumeric Step-8 probability mass for {stat_key}."
            ) from exc
        if (
            not value_float.is_integer()
            or value_float < 0
            or not math.isfinite(probability_float)
            or not 0.0 <= probability_float <= 1.0
        ):
            raise WNBAStep9ThresholdPricingUpstreamError(
                f"Step 9A found invalid Step-8 probability mass for {stat_key}."
            )
        integer = int(value_float)
        if integer in seen:
            raise WNBAStep9ThresholdPricingUpstreamError(
                f"Step 9A found duplicate Step-8 outcome value for {stat_key}."
            )
        seen.add(integer)
        total += probability_float
        cleaned.append({"value": integer, "probability": probability_float})
    if abs(total - 1.0) > 2e-8:
        raise WNBAStep9ThresholdPricingUpstreamError(
            f"Step 9A Step-8 probability mass for {stat_key} does not sum to one."
        )
    return cleaned


def _validate_step8_result(result: Mapping[str, Any]) -> tuple[str, int, str, str, str]:
    if not isinstance(result, Mapping):
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A requires a Step-8 result object."
        )
    if result.get("data_type") != "joint_player_stat_probability_distribution":
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received the wrong Step-8 data type."
        )
    if result.get("schema_version") != STEP8D_SCHEMA_VERSION:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received an unsupported Step-8 schema version."
        )
    if result.get("model_version") != STEP8D_MODEL_VERSION:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received an unsupported Step-8 model version."
        )
    if STEP8D_MODEL_VERSION != step8_freeze.MODEL_VERSIONS["step8d"]:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A detected drift between the frozen Step-8 release and Step-8D model."
        )
    if step8_freeze.DEFAULT_ENABLED is not False or step8_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A requires the frozen Step-8 release to remain default-OFF."
        )

    simulation = result.get("simulation")
    convergence = result.get("convergence")
    if not isinstance(simulation, Mapping) or not isinstance(convergence, Mapping):
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A requires Step-8 simulation and convergence metadata."
        )
    simulations = simulation.get("simulations")
    if not isinstance(simulations, int) or isinstance(simulations, bool):
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A received invalid Step-8 simulation count metadata."
        )
    if simulations < step8_freeze.DEFAULT_SIMULATIONS:
        raise WNBAStep9ThresholdPricingNotReadyError(
            f"Step 9A requires at least {step8_freeze.DEFAULT_SIMULATIONS:,} Step-8 simulations."
        )
    if convergence.get("converged") is not True:
        raise WNBAStep9ThresholdPricingNotReadyError(
            "Step 9A requires a converged Step-8 Monte Carlo result."
        )

    game_id, player_id, team_key, opponent_key = _validate_identity(result)
    step8_hash = _validate_step8_hash(result)
    for stat_key in _STEP8_STAT_KEY.values():
        _validate_probability_mass(result, stat_key)
    return game_id, player_id, team_key, opponent_key, step8_hash


def _raw_probabilities(rows: list[dict[str, Any]], line: float) -> dict[str, float]:
    if float(line).is_integer():
        integer = int(line)
        under = sum(row["probability"] for row in rows if row["value"] < integer)
        push = sum(row["probability"] for row in rows if row["value"] == integer)
        over = sum(row["probability"] for row in rows if row["value"] > integer)
    else:
        under = sum(row["probability"] for row in rows if row["value"] < line)
        push = 0.0
        over = sum(row["probability"] for row in rows if row["value"] > line)
    total = under + push + over
    if abs(total - 1.0) > 2e-8:
        raise WNBAStep9ThresholdPricingUpstreamError(
            "Step 9A threshold probabilities do not sum to one."
        )
    return {
        "under": under,
        "push": push,
        "over": over,
    }


def _decimal_to_american(decimal_odds: float) -> int | None:
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        return None
    if abs(decimal_odds - 2.0) < 1e-12:
        return 100
    if decimal_odds > 2.0:
        return int(round((decimal_odds - 1.0) * 100.0))
    return int(round(-100.0 / (decimal_odds - 1.0)))


def _fair_price(probability: float) -> dict[str, Any]:
    if probability <= 0.0:
        return {
            "available": False,
            "fair_probability": 0.0,
            "fair_percentage": 0.0,
            "fair_decimal_odds": None,
            "fair_american_odds": None,
            "reason": "zero_resolved_probability",
        }
    if probability >= 1.0:
        return {
            "available": False,
            "fair_probability": 1.0,
            "fair_percentage": 100.0,
            "fair_decimal_odds": 1.0,
            "fair_american_odds": None,
            "reason": "certain_resolved_probability_has_no_finite_positive_profit_price",
        }
    decimal_odds = 1.0 / probability
    return {
        "available": True,
        "fair_probability": round(probability, 10),
        "fair_percentage": round(probability * 100.0, 6),
        "fair_decimal_odds": round(decimal_odds, 8),
        "fair_american_odds": _decimal_to_american(decimal_odds),
    }


def build_step9_threshold_pricing(
    result: Mapping[str, Any],
    *,
    stat: str,
    line: float,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Price one statistical threshold from a certified, converged Step-8 result."""
    _assert_safe_environment(env)
    canonical_stat = _stat(stat)
    prop_line = _line(line)
    game_id, player_id, team_key, opponent_key, step8_hash = _validate_step8_result(result)
    stat_key = _STEP8_STAT_KEY[canonical_stat]
    rows = _validate_probability_mass(result, stat_key)
    raw = _raw_probabilities(rows, prop_line)
    resolved = raw["over"] + raw["under"]
    if resolved <= 0.0:
        raise WNBAStep9ThresholdPricingNotReadyError(
            "Step 9A cannot create fair prices because all probability mass is on the push."
        )
    fair_over = raw["over"] / resolved
    fair_under = raw["under"] / resolved
    simulations = int((result.get("simulation") or {}).get("simulations"))

    response = {
        "data_type": "post_projection_prop_threshold_pricing",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": _utc_now_iso(),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "prop": {
            "stat": canonical_stat,
            "step8_distribution_key": stat_key,
            "line": prop_line,
            "line_does_not_change_basketball_projection": True,
        },
        "raw_probabilities": {
            "over": {
                "probability": round(raw["over"], 10),
                "percentage": round(raw["over"] * 100.0, 6),
            },
            "push": {
                "probability": round(raw["push"], 10),
                "percentage": round(raw["push"] * 100.0, 6),
            },
            "under": {
                "probability": round(raw["under"], 10),
                "percentage": round(raw["under"] * 100.0, 6),
            },
            "sum": round(sum(raw.values()), 10),
        },
        "resolved_non_push": {
            "probability": round(resolved, 10),
            "percentage": round(resolved * 100.0, 6),
            "over": _fair_price(fair_over),
            "under": _fair_price(fair_under),
            "fair_probability_sum": round(fair_over + fair_under, 10),
            "settlement_basis": "fair prices are conditional on a resolved non-push outcome",
        },
        "precision": {
            "simulations": simulations,
            "over_monte_carlo_standard_error": round(
                math.sqrt(max(raw["over"] * (1.0 - raw["over"]), 0.0) / simulations),
                10,
            ),
            "push_monte_carlo_standard_error": round(
                math.sqrt(max(raw["push"] * (1.0 - raw["push"]), 0.0) / simulations),
                10,
            ),
            "under_monte_carlo_standard_error": round(
                math.sqrt(max(raw["under"] * (1.0 - raw["under"]), 0.0) / simulations),
                10,
            ),
            "step8_converged": True,
        },
        "step8_lineage": {
            "release_id": step8_freeze.RELEASE_ID,
            "integration_version": step8_freeze.INTEGRATION_VERSION,
            "step8d_model_version": STEP8D_MODEL_VERSION,
            "result_content_sha256": step8_hash,
            "certified_step8d_sha": step8_freeze.CERTIFIED_STEP8D_SHA,
            "minimum_required_simulations": step8_freeze.DEFAULT_SIMULATIONS,
        },
        "guardrails": {
            "post_projection_only": True,
            "sportsbook_quote_consumed": False,
            "sportsbook_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = dict(response)
    hash_surface.pop("generated_at_utc", None)
    response["pricing_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return response
