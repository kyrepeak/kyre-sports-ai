"""Offline certification for Step 9C multi-sportsbook consensus + best offer.

All sportsbook quotes are deterministic synthetic inputs. The certificate proves
same-line consensus, synchronized snapshot enforcement, cross-line best-offer
selection with common Step-8 lineage, and that Step-9D ranking remains OFF.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step9_multisportsbook_consensus as consensus
from sports_api import wnba_step9_sportsbook_market_comparison as market
from sports_api import wnba_step9_threshold_pricing as pricing

REPORT_PATH = Path("step9c-multisportsbook-consensus-cert.json")
STEP9B_FROZEN_SHA = "45cd3b43ca2771ae01f6fa3c7345ef0b9a444394"
STEP9A_FROZEN_SHA = "3b9acde91250d0e7a1767f3861765d4366f510ba"
EVALUATED_AT = datetime(2026, 8, 28, 4, 46, 0, tzinfo=timezone.utc)
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
        raise RuntimeError("Step 9C cert refuses production switches: " + ", ".join(bad))
    if not _truthy(os.getenv(consensus.STEP9C_MULTIBOOK_CONSENSUS_ENABLED_ENV)):
        raise RuntimeError("Step 9C cert requires its isolated CI flag.")


def _fair_record(probability: float) -> dict[str, Any]:
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
    decimal = 1.0 / probability
    american = (
        int(round((decimal - 1.0) * 100.0))
        if decimal >= 2.0
        else int(round(-100.0 / (decimal - 1.0)))
    )
    return {
        "available": True,
        "fair_probability": round(probability, 10),
        "fair_percentage": round(probability * 100.0, 6),
        "fair_decimal_odds": round(decimal, 8),
        "fair_american_odds": american,
    }


def _pricing_fixture(*, line: float, p_over: float, p_under: float) -> dict[str, Any]:
    p_push = 0.0
    resolved = p_over + p_under
    result: dict[str, Any] = {
        "data_type": "post_projection_prop_threshold_pricing",
        "schema_version": pricing.SCHEMA_VERSION,
        "source": pricing.SOURCE,
        "model_version": pricing.MODEL_VERSION,
        "release_id": pricing.RELEASE_ID,
        "generated_at_utc": "2026-08-28T04:45:00+00:00",
        "game_id": "1022600291",
        "player_id": 1642291,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "prop": {
            "stat": "points",
            "step8_distribution_key": "points",
            "line": line,
            "line_does_not_change_basketball_projection": True,
        },
        "raw_probabilities": {
            "over": {"probability": p_over, "percentage": p_over * 100.0},
            "push": {"probability": p_push, "percentage": 0.0},
            "under": {"probability": p_under, "percentage": p_under * 100.0},
            "sum": 1.0,
        },
        "resolved_non_push": {
            "probability": resolved,
            "percentage": resolved * 100.0,
            "over": _fair_record(p_over / resolved),
            "under": _fair_record(p_under / resolved),
            "fair_probability_sum": 1.0,
            "settlement_basis": "fair prices are conditional on a resolved non-push outcome",
        },
        "precision": {
            "simulations": 5_000_000,
            "over_monte_carlo_standard_error": 0.00022,
            "push_monte_carlo_standard_error": 0.0,
            "under_monte_carlo_standard_error": 0.00022,
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
    result["pricing_content_sha256"] = consensus._canonical_hash(surface)
    return result


def _bundle(
    *,
    sportsbook: str,
    line: float,
    p_over: float,
    p_under: float,
    over_odds: int,
    under_odds: int,
    captured_at: str,
) -> dict[str, Any]:
    price = _pricing_fixture(line=line, p_over=p_over, p_under=p_under)
    compared = market.build_step9b_market_comparison(
        price,
        sportsbook=sportsbook,
        over_odds=over_odds,
        under_odds=under_odds,
        market_captured_at_utc=captured_at,
        minimum_required_ev=0.05,
        max_market_age_minutes=10,
        require_fresh_market=True,
        evaluated_at=EVALUATED_AT,
        env={market.STEP9B_MARKET_COMPARISON_ENABLED_ENV: "true"},
    )
    return {"pricing": price, "comparison": compared}


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    if consensus.STEP9B_FROZEN_SHA != STEP9B_FROZEN_SHA:
        raise RuntimeError("Step 9C frozen Step-9B SHA constant drifted.")
    if consensus.STEP9A_FROZEN_SHA != STEP9A_FROZEN_SHA:
        raise RuntimeError("Step 9C frozen Step-9A SHA constant drifted.")
    if market.RELEASE_ID != "wnba_step9b_sportsbook_market_comparison_2026_regular_season_v1":
        raise RuntimeError("Step 9B release identity drifted.")

    offers = [
        _bundle(
            sportsbook="CertificationBookA",
            line=20.5,
            p_over=0.60,
            p_under=0.40,
            over_odds=-110,
            under_odds=-110,
            captured_at="2026-08-28T04:45:00Z",
        ),
        _bundle(
            sportsbook="CertificationBookB",
            line=20.5,
            p_over=0.60,
            p_under=0.40,
            over_odds=-105,
            under_odds=-115,
            captured_at="2026-08-28T04:45:20Z",
        ),
        _bundle(
            sportsbook="CertificationBookC",
            line=19.5,
            p_over=0.68,
            p_under=0.32,
            over_odds=-125,
            under_odds=105,
            captured_at="2026-08-28T04:45:30Z",
        ),
    ]
    result = consensus.build_step9c_multibook_consensus(
        offers,
        max_snapshot_spread_seconds=120,
        require_fresh_quotes=True,
        require_synchronized_snapshot=True,
    )

    if result["snapshot"]["unique_sportsbook_count"] != 3:
        raise RuntimeError("Step 9C unique sportsbook count changed.")
    if result["snapshot"]["snapshot_spread_seconds"] != 30.0:
        raise RuntimeError("Step 9C synchronized snapshot calculation changed.")
    if result["prop"]["reference_line"] != 20.5:
        raise RuntimeError("Step 9C reference-line selection changed.")
    groups = {float(item["line"]): item for item in result["same_line_consensus"]}
    reference = groups[20.5]
    alternate = groups[19.5]
    if reference["book_count"] != 2 or reference["consensus_available"] is not True:
        raise RuntimeError("Step 9C same-line consensus availability changed.")
    if alternate["book_count"] != 1 or alternate["consensus_available"] is not False:
        raise RuntimeError("Step 9C different-line non-blending guard changed.")
    if abs(reference["no_vig_over"]["median_probability"] - 0.4945828819) > 1e-10:
        raise RuntimeError("Step 9C median no-vig Over consensus changed.")
    if abs(reference["consensus_edge"]["over_probability"] - 0.1054171181) > 1e-10:
        raise RuntimeError("Step 9C consensus Over edge changed.")

    best_over = result["best_available"]["over"]
    best_under = result["best_available"]["under"]
    reference_price = result["best_available"]["reference_line_best_price"]
    if best_over["sportsbook"] != "CertificationBookC" or best_over["line"] != 19.5:
        raise RuntimeError("Step 9C cross-line best Over offer changed.")
    if abs(best_over["ev_per_unit"] - 0.224) > 1e-10:
        raise RuntimeError("Step 9C best Over EV changed.")
    if best_under["sportsbook"] != "CertificationBookA" or best_under["line"] != 20.5:
        raise RuntimeError("Step 9C best Under offer changed.")
    if reference_price["over"]["sportsbook"] != "CertificationBookB":
        raise RuntimeError("Step 9C best Over price at reference line changed.")
    if reference_price["under"]["sportsbook"] != "CertificationBookA":
        raise RuntimeError("Step 9C best Under price at reference line changed.")

    guards = result["guardrails"]
    for key in (
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9a_probabilities_changed",
        "step9b_comparisons_changed",
        "sportsbook_called",
        "different_lines_blended_into_consensus",
        "cross_prop_ranking_calculated",
        "qualification_applied",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        if guards.get(key) is not False:
            raise RuntimeError(f"Step 9C safety guard {key!r} is not false.")
    if guards.get("cross_sportsbook_consensus_calculated") is not True:
        raise RuntimeError("Step 9C consensus capability guard changed.")
    if guards.get("best_offer_selected_within_prop") is not True:
        raise RuntimeError("Step 9C best-offer capability guard changed.")

    report = {
        "data_type": "wnba_step9c_multisportsbook_consensus_cert_v1",
        "certification_result": "STEP9C_MULTISPORTSBOOK_CONSENSUS_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step9c": {
            "release_id": consensus.RELEASE_ID,
            "schema_version": consensus.SCHEMA_VERSION,
            "model_version": consensus.MODEL_VERSION,
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "branch": os.getenv("GITHUB_REF_NAME"),
            "consensus_content_sha256": result["consensus_content_sha256"],
        },
        "frozen_lineage": result["lineage"],
        "snapshot": result["snapshot"],
        "reference_line_consensus": reference,
        "best_available": {
            "over": best_over,
            "under": best_under,
            "reference_line_best_price": reference_price,
        },
        "safety": {
            "caller_supplied_quotes_only": True,
            "sportsbook_called": False,
            "different_lines_blended": False,
            "cross_prop_ranking_calculated": False,
            "qualification_applied": False,
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
    print("STEP9C_MULTISPORTSBOOK_CONSENSUS_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
