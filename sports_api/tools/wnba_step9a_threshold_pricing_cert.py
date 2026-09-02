"""Offline release certificate for the WNBA Step 9A threshold-pricing boundary.

The cert exercises the post-projection contract against a deterministic,
hash-covered Step-8D-shaped fixture. It proves threshold semantics, push handling,
fair-price conversion, hash lineage, and default-OFF safety without calling any
sportsbook, network, persistence, scheduler, or production runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step8_release_freeze as step8_freeze
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

REPORT_PATH = Path("step9a-threshold-pricing-cert.json")
STEP8_FROZEN_HEAD_SHA = "8faf468b770f7a31244914df75390fc788f859a1"
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = [name for name in _OFF_ENV_KEYS if _truthy(os.getenv(name))]
    if bad:
        raise RuntimeError(
            "Step 9A cert refuses production switches: " + ", ".join(bad)
        )
    if not _truthy(os.getenv(pricing.STEP9_THRESHOLD_PRICING_ENABLED_ENV)):
        raise RuntimeError("Step 9A cert requires its isolated CI flag.")


def _fixture() -> dict[str, Any]:
    result: dict[str, Any] = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T04:32:31+00:00",
        "game_id": "1022600291",
        "player_id": 1642291,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {
            "simulations": step8_freeze.DEFAULT_SIMULATIONS,
            "batch_size": step8_freeze.DEFAULT_BATCH_SIZE,
        },
        "convergence": {
            "converged": True,
            "max_probe_batch_probability_range": 0.005,
            "max_mean_target_absolute_error": 0.002,
            "max_probe_monte_carlo_standard_error": 0.000224,
        },
        "distributions": {
            "points": {
                "probability_mass": [
                    {"value": 20, "probability": 0.4},
                    {"value": 21, "probability": 0.6},
                ]
            },
            "rebounds": {
                "probability_mass": [
                    {"value": 15, "probability": 0.55},
                    {"value": 16, "probability": 0.45},
                ]
            },
            "assists": {
                "probability_mass": [
                    {"value": 4, "probability": 0.35},
                    {"value": 5, "probability": 0.65},
                ]
            },
            "points_rebounds_assists": {
                "probability_mass": [
                    {"value": 40, "probability": 0.51},
                    {"value": 41, "probability": 0.49},
                ]
            },
        },
    }
    hash_surface = dict(result)
    hash_surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(hash_surface)
    return result


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    if step8_freeze.RELEASE_ID != "wnba_step8_projection_probability_2026_regular_season_frozen_v1":
        raise RuntimeError("Step 8 frozen release identity drifted.")
    if step8_freeze.DEFAULT_ENABLED is not False:
        raise RuntimeError("Step 8 no longer preserves default-OFF safety.")
    if step8_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise RuntimeError("Step 8 unexpectedly allows production activation.")
    if STEP8D_MODEL_VERSION != step8_freeze.MODEL_VERSIONS["step8d"]:
        raise RuntimeError("Step 8D model version disagrees with frozen release manifest.")

    fixture = _fixture()
    points_half = pricing.build_step9_threshold_pricing(
        fixture, stat="points", line=20.5
    )
    points_integer = pricing.build_step9_threshold_pricing(
        fixture, stat="points", line=20
    )
    pra_half = pricing.build_step9_threshold_pricing(
        fixture, stat="pra", line=40.5
    )

    if points_half["raw_probabilities"]["over"]["probability"] != 0.6:
        raise RuntimeError("Step 9A half-point Over semantics changed.")
    if points_half["resolved_non_push"]["over"]["fair_american_odds"] != -150:
        raise RuntimeError("Step 9A fair American odds conversion changed.")
    if points_half["resolved_non_push"]["under"]["fair_american_odds"] != 150:
        raise RuntimeError("Step 9A fair Under odds conversion changed.")
    if points_integer["raw_probabilities"]["push"]["probability"] != 0.4:
        raise RuntimeError("Step 9A integer-line push semantics changed.")
    if pra_half["prop"]["step8_distribution_key"] != "points_rebounds_assists":
        raise RuntimeError("Step 9A PRA distribution mapping changed.")

    for response in (points_half, points_integer, pra_half):
        guards = response.get("guardrails") or {}
        for key in (
            "sportsbook_quote_consumed",
            "sportsbook_called",
            "vig_removed",
            "edge_calculated",
            "expected_value_calculated",
            "supabase_mutated",
            "persistence_mutated",
            "scheduler_started",
            "production_runtime_enabled",
            "production_activation_allowed",
        ):
            if guards.get(key) is not False:
                raise RuntimeError(f"Step 9A safety guard {key!r} is not false.")
        if guards.get("post_projection_only") is not True:
            raise RuntimeError("Step 9A is no longer explicitly post-projection only.")

    report = {
        "data_type": "wnba_step9a_threshold_pricing_cert_v1",
        "certification_result": "STEP9A_THRESHOLD_PRICING_FROZEN_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step9a": {
            "release_id": pricing.RELEASE_ID,
            "schema_version": pricing.SCHEMA_VERSION,
            "model_version": pricing.MODEL_VERSION,
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "branch": os.getenv("GITHUB_REF_NAME"),
        },
        "frozen_step8_lineage": {
            "frozen_head_sha": STEP8_FROZEN_HEAD_SHA,
            "release_id": step8_freeze.RELEASE_ID,
            "integration_version": step8_freeze.INTEGRATION_VERSION,
            "certified_step8d_sha": step8_freeze.CERTIFIED_STEP8D_SHA,
            "step8d_model_version": STEP8D_MODEL_VERSION,
            "minimum_simulations": step8_freeze.DEFAULT_SIMULATIONS,
        },
        "contract_checks": {
            "points_20_5_over_probability": points_half["raw_probabilities"]["over"]["probability"],
            "points_20_5_under_probability": points_half["raw_probabilities"]["under"]["probability"],
            "points_20_5_fair_over_american": points_half["resolved_non_push"]["over"]["fair_american_odds"],
            "points_20_5_fair_under_american": points_half["resolved_non_push"]["under"]["fair_american_odds"],
            "points_20_push_probability": points_integer["raw_probabilities"]["push"]["probability"],
            "pra_40_5_over_probability": pra_half["raw_probabilities"]["over"]["probability"],
            "pricing_hash_stable_surface": points_half["pricing_content_sha256"],
        },
        "safety": {
            "step9a_default_enabled": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_quote_consumed": False,
            "sportsbook_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "step9a_enabled_for_isolated_ci_only": True,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP9A_THRESHOLD_PRICING_FROZEN_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
