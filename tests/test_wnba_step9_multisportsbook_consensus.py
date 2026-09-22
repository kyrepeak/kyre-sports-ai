from __future__ import annotations

from datetime import datetime, timezone
import statistics
import unittest

from sports_api import wnba_step9_multisportsbook_consensus as consensus
from sports_api import wnba_step9_sportsbook_market_comparison as market
from sports_api import wnba_step9_threshold_pricing as pricing

EVALUATED_AT = datetime(2026, 8, 28, 4, 46, 0, tzinfo=timezone.utc)


def _fair_record(probability: float) -> dict:
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


def _pricing_fixture(
    *,
    line: float,
    p_over: float,
    p_push: float,
    p_under: float,
    step8_hash: str = "a" * 64,
) -> dict:
    resolved = p_over + p_under
    fair_over = p_over / resolved
    fair_under = p_under / resolved
    result = {
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
            "line": float(line),
            "line_does_not_change_basketball_projection": True,
        },
        "raw_probabilities": {
            "over": {"probability": p_over, "percentage": p_over * 100.0},
            "push": {"probability": p_push, "percentage": p_push * 100.0},
            "under": {"probability": p_under, "percentage": p_under * 100.0},
            "sum": 1.0,
        },
        "resolved_non_push": {
            "probability": resolved,
            "percentage": resolved * 100.0,
            "over": _fair_record(fair_over),
            "under": _fair_record(fair_under),
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
            "result_content_sha256": step8_hash,
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
    p_push: float,
    p_under: float,
    over_odds: int,
    under_odds: int,
    captured_at: str,
    step8_hash: str = "a" * 64,
    require_fresh_market: bool = True,
) -> dict:
    price = _pricing_fixture(
        line=line,
        p_over=p_over,
        p_push=p_push,
        p_under=p_under,
        step8_hash=step8_hash,
    )
    comparison = market.build_step9b_market_comparison(
        price,
        sportsbook=sportsbook,
        over_odds=over_odds,
        under_odds=under_odds,
        market_captured_at_utc=captured_at,
        minimum_required_ev=0.05,
        max_market_age_minutes=10,
        require_fresh_market=require_fresh_market,
        evaluated_at=EVALUATED_AT,
        env={market.STEP9B_MARKET_COMPARISON_ENABLED_ENV: "true"},
    )
    return {"pricing": price, "comparison": comparison}


def _env(**updates: str) -> dict[str, str]:
    values = {consensus.STEP9C_MULTIBOOK_CONSENSUS_ENABLED_ENV: "true"}
    values.update(updates)
    return values


class Step9MultiSportsbookConsensusTests(unittest.TestCase):
    def test_flag_is_default_off(self) -> None:
        self.assertFalse(consensus.step9c_multibook_consensus_enabled({}))

    def test_production_switch_fails_closed(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
            ),
        ]
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusDisabledError):
            consensus.build_step9c_multibook_consensus(
                offers, env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true")
            )

    def test_same_line_consensus_uses_median_no_vig_probability(self) -> None:
        a = _bundle(
            sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
        )
        b = _bundle(
            sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
        )
        result = consensus.build_step9c_multibook_consensus([a, b], env=_env())
        group = result["same_line_consensus"][0]
        observed = [
            a["comparison"]["sportsbook"]["quote"]["over"]["no_vig_probability"],
            b["comparison"]["sportsbook"]["quote"]["over"]["no_vig_probability"],
        ]
        self.assertTrue(group["consensus_available"])
        self.assertAlmostEqual(group["no_vig_over"]["median_probability"], statistics.median(observed))
        self.assertAlmostEqual(group["model"]["resolved_fair_over_probability"], 0.60)
        self.assertTrue(result["guardrails"]["cross_sportsbook_consensus_calculated"])
        self.assertFalse(result["guardrails"]["different_lines_blended_into_consensus"])

    def test_different_lines_are_kept_in_separate_consensus_groups(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=19.5, p_over=0.68, p_push=0.0, p_under=0.32,
                over_odds=-125, under_odds=105, captured_at="2026-08-28T04:45:20Z"
            ),
        ]
        result = consensus.build_step9c_multibook_consensus(offers, env=_env())
        self.assertEqual(len(result["same_line_consensus"]), 2)
        self.assertTrue(all(not group["consensus_available"] for group in result["same_line_consensus"]))
        self.assertTrue(result["prop"]["different_lines_are_never_probability_averaged"])

    def test_best_available_over_can_span_lines_using_each_lines_own_ev(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
            ),
            _bundle(
                sportsbook="BookC", line=19.5, p_over=0.68, p_push=0.0, p_under=0.32,
                over_odds=-125, under_odds=105, captured_at="2026-08-28T04:45:30Z"
            ),
        ]
        result = consensus.build_step9c_multibook_consensus(offers, env=_env())
        best = result["best_available"]["over"]
        self.assertEqual(best["sportsbook"], "BookC")
        self.assertEqual(best["line"], 19.5)
        self.assertGreater(best["ev_per_unit"], 0.20)
        self.assertFalse(best["cross_prop_ranking_applied"])

    def test_reference_line_best_price_is_selected_per_side(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
            ),
            _bundle(
                sportsbook="BookC", line=19.5, p_over=0.68, p_push=0.0, p_under=0.32,
                over_odds=-125, under_odds=105, captured_at="2026-08-28T04:45:30Z"
            ),
        ]
        result = consensus.build_step9c_multibook_consensus(offers, env=_env())
        ref = result["best_available"]["reference_line_best_price"]
        self.assertEqual(ref["line"], 20.5)
        self.assertEqual(ref["over"]["sportsbook"], "BookB")
        self.assertEqual(ref["under"]["sportsbook"], "BookA")

    def test_snapshot_spread_over_limit_fails_closed(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:42:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:30Z"
            ),
        ]
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusNotReadyError):
            consensus.build_step9c_multibook_consensus(
                offers, max_snapshot_spread_seconds=120, env=_env()
            )

    def test_stale_quote_fails_when_fresh_quotes_required(self) -> None:
        stale = _bundle(
            sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:20:00Z",
            require_fresh_market=False,
        )
        fresh = _bundle(
            sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:00Z"
        )
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusNotReadyError):
            consensus.build_step9c_multibook_consensus(
                [stale, fresh],
                require_fresh_quotes=True,
                require_synchronized_snapshot=False,
                env=_env(),
            )

    def test_duplicate_sportsbook_same_line_is_rejected(self) -> None:
        a = _bundle(
            sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
        )
        b = _bundle(
            sportsbook="booka", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
        )
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusNotReadyError):
            consensus.build_step9c_multibook_consensus([a, b], env=_env())

    def test_tampered_step9b_hash_is_rejected(self) -> None:
        a = _bundle(
            sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
        )
        b = _bundle(
            sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
        )
        b["comparison"]["sportsbook"]["quote"]["over"]["american_odds"] = -104
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusUpstreamError):
            consensus.build_step9c_multibook_consensus([a, b], env=_env())

    def test_comparison_must_reference_supplied_pricing_hash(self) -> None:
        a = _bundle(
            sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
        )
        b = _bundle(
            sportsbook="BookB", line=19.5, p_over=0.68, p_push=0.0, p_under=0.32,
            over_odds=-125, under_odds=105, captured_at="2026-08-28T04:45:20Z"
        )
        bad = {"comparison": a["comparison"], "pricing": b["pricing"]}
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusUpstreamError):
            consensus.build_step9c_multibook_consensus([bad, b], env=_env())

    def test_different_step8_distribution_hashes_cannot_be_mixed(self) -> None:
        a = _bundle(
            sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
            over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z",
            step8_hash="a" * 64,
        )
        b = _bundle(
            sportsbook="BookB", line=19.5, p_over=0.68, p_push=0.0, p_under=0.32,
            over_odds=-125, under_odds=105, captured_at="2026-08-28T04:45:20Z",
            step8_hash="b" * 64,
        )
        with self.assertRaises(consensus.WNBAStep9MultiBookConsensusUpstreamError):
            consensus.build_step9c_multibook_consensus([a, b], env=_env())

    def test_output_hash_is_stable_for_same_snapshot(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
            ),
        ]
        first = consensus.build_step9c_multibook_consensus(offers, env=_env())
        second = consensus.build_step9c_multibook_consensus(offers, env=_env())
        self.assertEqual(first["consensus_content_sha256"], second["consensus_content_sha256"])

    def test_cross_prop_ranking_and_qualification_remain_off(self) -> None:
        offers = [
            _bundle(
                sportsbook="BookA", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-110, under_odds=-110, captured_at="2026-08-28T04:45:00Z"
            ),
            _bundle(
                sportsbook="BookB", line=20.5, p_over=0.60, p_push=0.0, p_under=0.40,
                over_odds=-105, under_odds=-115, captured_at="2026-08-28T04:45:20Z"
            ),
        ]
        result = consensus.build_step9c_multibook_consensus(offers, env=_env())
        self.assertFalse(result["guardrails"]["cross_prop_ranking_calculated"])
        self.assertFalse(result["guardrails"]["qualification_applied"])
        self.assertFalse(result["guardrails"]["sportsbook_called"])
        self.assertFalse(result["guardrails"]["production_runtime_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
