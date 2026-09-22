"""Step 5.10 deterministic bounded canary controller for the MLB price gate.

This module chooses a stable game-level cohort for a controlled rollout of the
certified Step 5.9 price gate. Production defaults stay OFF and 0%. Even when
requested, the cohort is hard-capped at 25% of the current slate and never splits
markets within the same official MLB game ID.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable

DATA_TYPE = "mlb_price_gate_canary_cohort_v1"
SCHEMA_VERSION = 1
MAX_CANARY_PERCENT = 25.0
COHORT_SALT = "mlb-step5-10-canary-v1"


class MLBPriceGateCanaryError(ValueError):
    pass


def _game_id(value: Any) -> int:
    if isinstance(value, bool):
        raise MLBPriceGateCanaryError("official game ID must be a positive integer")
    try:
        out = int(value)
    except Exception as exc:
        raise MLBPriceGateCanaryError("official game ID must be a positive integer") from exc
    if out <= 0 or str(out) != str(value).strip():
        # Accept integer objects and canonical digit strings only; reject 1.5 -> 1.
        if not (isinstance(value, int) and value > 0):
            raise MLBPriceGateCanaryError("official game ID must be a positive integer")
    return out


def bounded_canary_percent(value: Any) -> tuple[float, bool]:
    if isinstance(value, bool):
        raise MLBPriceGateCanaryError("canary percent must be numeric")
    try:
        requested = float(value)
    except Exception as exc:
        raise MLBPriceGateCanaryError("canary percent must be numeric") from exc
    if not math.isfinite(requested):
        raise MLBPriceGateCanaryError("canary percent must be finite")
    effective = min(MAX_CANARY_PERCENT, max(0.0, requested))
    return effective, not math.isclose(effective, requested, rel_tol=0.0, abs_tol=0.0)


def _stable_score(game_id: int) -> int:
    digest = hashlib.sha256(f"{COHORT_SALT}:{game_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def select_canary_game_ids(
    game_ids: Iterable[Any],
    *,
    enabled: bool,
    requested_percent: Any,
) -> dict[str, Any]:
    if not isinstance(enabled, bool):
        raise MLBPriceGateCanaryError("enabled must be boolean")
    try:
        raw_ids = list(game_ids)
    except Exception as exc:
        raise MLBPriceGateCanaryError("game_ids must be iterable") from exc

    normalized = sorted({_game_id(value) for value in raw_ids})
    effective_percent, percent_bounded = bounded_canary_percent(requested_percent)

    if not enabled or effective_percent <= 0.0 or not normalized:
        target_count = 0
        selected: list[int] = []
    else:
        # Floor is deliberate: the realized cohort can never exceed the requested
        # percentage or the 25% safety cap. Tiny slates may therefore enroll zero.
        target_count = int(math.floor(len(normalized) * effective_percent / 100.0))
        ranked = sorted(normalized, key=lambda game_id: (_stable_score(game_id), game_id))
        selected = ranked[:target_count]

    realized_percent = (100.0 * len(selected) / len(normalized)) if normalized else 0.0
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "enabled_requested": enabled,
        "requested_percent": float(requested_percent),
        "effective_percent": effective_percent,
        "percent_bounded": percent_bounded,
        "max_canary_percent": MAX_CANARY_PERCENT,
        "cohort_salt": COHORT_SALT,
        "official_game_count": len(normalized),
        "target_game_count": target_count,
        "selected_game_ids": selected,
        "selected_game_count": len(selected),
        "realized_percent": realized_percent,
        "game_level_atomicity": True,
        "deterministic_assignment": True,
        "rollback_to_zero_is_exact": True,
        "production_default_enabled": False,
        "production_default_percent": 0.0,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
    }


def game_is_in_canary(game_id: Any, cohort: dict[str, Any]) -> bool:
    if not isinstance(cohort, dict) or cohort.get("data_type") != DATA_TYPE:
        raise MLBPriceGateCanaryError("certified Step 5.10 cohort context required")
    normalized = _game_id(game_id)
    selected = cohort.get("selected_game_ids")
    if not isinstance(selected, list):
        raise MLBPriceGateCanaryError("selected_game_ids must be a list")
    return normalized in selected


__all__ = [
    "COHORT_SALT",
    "DATA_TYPE",
    "MAX_CANARY_PERCENT",
    "MLBPriceGateCanaryError",
    "SCHEMA_VERSION",
    "bounded_canary_percent",
    "game_is_in_canary",
    "select_canary_game_ids",
]
