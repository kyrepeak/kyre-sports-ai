"""Offline certification for Step 9B sportsbook market comparison.

Uses a deterministic, hash-covered Step-9A-shaped payload and a caller-supplied
synthetic two-way quote. No sportsbook/network call occurs. The certificate locks
vig removal, edge, EV, playable-price, freshness, and post-projection semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step9_sportsbook_market_comparison as market
from sports_api import wnba_step9_threshold_pricing as pricing

REPORT_PATH = Path("step9b-sportsbook-market-comparison-cert.json")
STEP9A_FROZEN_SHA = "3b9acde91250d0e7a1767f3861765d4366f510ba"
EVALUATED_AT = datetime(2026, 8, 28, 4, 40, 0, tzinfo=timezone.utc)
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
            "Step 9B cert refuses production switches: " + ", ".join(bad)
        )
    if not _truthy(os.getenv(market.STEP9B_MARKET_COMPARISON_ENABLED_ENV)):
        raise RuntimeError("Step 9B cert requires its isolated CI flag.")


def _pricing_fixture() -> dict[str, Any]:
    result: dict[str, Any] = {
        "data_type": "post_projection_prop_threshold_pricing",
        "schema_version": pricing.SCHEMA_VERSION,
        "source": pricing.SOURCE,
        "model_version": pricing.MODEL_VERSION,
        "release_id": pricing.RELEASE_ID,
        "generated_at_utc": "2026-08-28T04:39:00+00:00",
        "game_id": "1022600291",
        "player_id": 1642291,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "prop": {
            "stat": "points",
            "step8_distribution_key": "points",
            "line": 20.5,
            "line_does_not_change_basketball_projection": True,
        },
        "raw_probabilities": {
            "over": {"probability": 0.60, "percentage": 60.0},
            "push": {"probability": 0.00, "percentage": 0.0},
            "under": {"probability": 0.40, "percentage": 40.0},
            "sum": 1.0,
        },
        "resolved_non_push": {
            "probability": 1.0,
            "percentage": 100.0,
            "over": {
                "available": True,
                "fair_probability": 0.60,
                "fair_percentage": 60.0,
                "fair_decimal_odds": 1.66666667,
                "fair_american_odds": -150,
            },
            "under": {
                "available": True,
                "fair_probability": 0.40,
                "fair_percentage": 40.0,
                "fair_decimal_odds": 2.5,
                "fair_american_odds": 150,
            },
            "fair_probability_sum": 1.0,
            "settlement_basis": "fair prices are conditional on a resolved non-push outcome",
        },
        "precision": {
            "simulations": 5_000_000,
            "over_monte_carlo_standard_error": 0.0002191,
            "push_monte_carlo_standard_error": 0.0,
            "under_monte_carlo_standard_error": 0.0002191,
            "step8_converged": True,
        },
        "step8_lineage": {
            "release_id": "wnba_step8_projection_probability_2026_regular_season_frozen_v1",
            "integration_version": "wnba_step8e_fastapi_projection_probability_v1",
            "step8d_model_version": "wnba_step8d_regularized_gaussian_copula_counts_2026_regular_v1",
            "result_content_sha256": "a" * 64,
            "certified_step8d_sha": "932e1baf05bf762cfb149de1f58be4f72bb7a526",
            "minimum_required_simulations": 5_000_000,
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
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["pricing_content_sha256"] = market._canonical_hash(surface)
    return result


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    if market.STEP9A_FROZEN_SHA != STEP9A_FROZEN_SHA:
        raise RuntimeError("Step 9B frozen Step-9A SHA constant drifted.")
    if pricing.RELEASE_ID != "wnba_step9a_threshold_pricing_2026_regular_season_v1":
        raise RuntimeError("Step 9A release identity drifted.")

    result = market.build_step9b_market_comparison(
        _pricing_fixture(),
        sportsbook="CertificationBook",
        over_odds=-110,
        under_odds=-110,
        market_captured_at_utc="2026-08-28T04:39:00Z",
        minimum_required_ev=0.05,
        max_market_age_minutes=10,
        require_fresh_market=True,
        evaluated_at=EVALUATED_AT,
    )

    quote = result["sportsbook"]["quote"]
    over = result["comparison"]["over"]
    under = result["comparison"]["under"]
    if quote["over"]["no_vig_probability"] != 0.5:
        raise RuntimeError("Step 9B symmetric-market no-vig Over probability changed.")
    if quote["under"]["no_vig_probability"] != 0.5:
        raise RuntimeError("Step 9B symmetric-market no-vig Under probability changed.")
    if abs(over["edge"]["vs_no_vig_market_probability"] - 0.10) > 1e-10:
        raise RuntimeError("Step 9B no-vig Over edge changed.")
    if abs(under["edge"]["vs_no_vig_market_probability"] + 0.10) > 1e-10:
        raise RuntimeError("Step 9B no-vig Under edge changed.")
    if abs(over["expected_value"]["net_profit_per_unit_staked"] - 0.145454546) > 1e-10:
        raise RuntimeError("Step 9B Over EV formula changed.")
    if over["price_threshold"]["minimum_acceptable_american_odds"] != -133:
        raise RuntimeError("Step 9B +5% EV minimum playable price changed.")
    if over["price_threshold"]["offered_price_meets_minimum_required_ev"] is not True:
        raise RuntimeError("Step 9B playable-price comparison changed.")
    if result["sportsbook"]["market_freshness"]["status"] != "fresh":
        raise RuntimeError("Step 9B expected fresh certification quote.")
    if result["comparison"]["higher_ev_side"] != "over":
        raise RuntimeError("Step 9B side comparison changed.")
    if result["comparison"]["ranking_or_qualification_applied"] is not False:
        raise RuntimeError("Step 9B must not perform Step-9D ranking/qualification.")

    guards = result["guardrails"]
    expected_false = (
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9a_probabilities_changed",
        "sportsbook_called",
        "cross_sportsbook_consensus_calculated",
        "cross_prop_ranking_calculated",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    )
    for key in expected_false:
        if guards.get(key) is not False:
            raise RuntimeError(f"Step 9B safety guard {key!r} is not false.")
    for key in ("sportsbook_quote_consumed", "vig_removed", "edge_calculated", "expected_value_calculated"):
        if guards.get(key) is not True:
            raise RuntimeError(f"Step 9B expected capability guard {key!r} is not true.")

    report = {
        "data_type": "wnba_step9b_sportsbook_market_comparison_cert_v1",
        "certification_result": "STEP9B_SPORTSBOOK_MARKET_COMPARISON_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step9b": {
            "release_id": market.RELEASE_ID,
            "schema_version": market.SCHEMA_VERSION,
            "model_version": market.MODEL_VERSION,
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "branch": os.getenv("GITHUB_REF_NAME"),
            "comparison_content_sha256": result["comparison_content_sha256"],
        },
        "step9a_lineage": result["step9a_lineage"],
        "certified_quote": {
            "sportsbook": result["sportsbook"]["name"],
            "over_odds": quote["over"]["american_odds"],
            "under_odds": quote["under"]["american_odds"],
            "sportsbook_margin_percentage": quote["sportsbook_margin_percentage"],
            "no_vig_over_probability": quote["over"]["no_vig_probability"],
            "no_vig_under_probability": quote["under"]["no_vig_probability"],
            "freshness": result["sportsbook"]["market_freshness"],
        },
        "comparison": {
            "model_over_probability": over["model"]["resolved_fair_win_probability"],
            "over_no_vig_edge_percentage_points": over["edge"]["vs_no_vig_market_percentage_points"],
            "over_ev_roi_percentage": over["expected_value"]["roi_percentage"],
            "over_minimum_price_for_5pct_ev": over["price_threshold"]["minimum_acceptable_american_odds"],
            "model_under_probability": under["model"]["resolved_fair_win_probability"],
            "under_no_vig_edge_percentage_points": under["edge"]["vs_no_vig_market_percentage_points"],
            "under_ev_roi_percentage": under["expected_value"]["roi_percentage"],
            "higher_ev_side": result["comparison"]["higher_ev_side"],
        },
        "safety": {
            "caller_supplied_quote_only": True,
            "sportsbook_called": False,
            "basketball_projection_changed": False,
            "step9a_probability_changed": False,
            "cross_sportsbook_consensus_calculated": False,
            "cross_prop_ranking_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP9B_SPORTSBOOK_MARKET_COMPARISON_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
