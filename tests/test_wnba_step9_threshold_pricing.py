from __future__ import annotations

import unittest

from sports_api import wnba_step8_release_freeze as step8_freeze
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)


def _step8_result() -> dict:
    result = {
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


def _env(**updates: str) -> dict[str, str]:
    values = {pricing.STEP9_THRESHOLD_PRICING_ENABLED_ENV: "true"}
    values.update(updates)
    return values


class Step9ThresholdPricingTests(unittest.TestCase):
    def test_flag_is_default_off(self) -> None:
        self.assertFalse(pricing.step9_threshold_pricing_enabled({}))

    def test_production_switch_fails_closed(self) -> None:
        with self.assertRaises(pricing.WNBAStep9ThresholdPricingDisabledError):
            pricing.build_step9_threshold_pricing(
                _step8_result(),
                stat="points",
                line=20.5,
                env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true"),
            )

    def test_half_point_line_creates_raw_and_fair_prices(self) -> None:
        result = pricing.build_step9_threshold_pricing(
            _step8_result(), stat="points", line=20.5, env=_env()
        )
        self.assertEqual(result["prop"]["stat"], "points")
        self.assertTrue(result["prop"]["line_does_not_change_basketball_projection"])
        self.assertAlmostEqual(result["raw_probabilities"]["over"]["probability"], 0.6)
        self.assertAlmostEqual(result["raw_probabilities"]["under"]["probability"], 0.4)
        self.assertAlmostEqual(result["raw_probabilities"]["push"]["probability"], 0.0)
        self.assertAlmostEqual(result["resolved_non_push"]["over"]["fair_probability"], 0.6)
        self.assertAlmostEqual(result["resolved_non_push"]["under"]["fair_probability"], 0.4)
        self.assertEqual(result["resolved_non_push"]["over"]["fair_american_odds"], -150)
        self.assertEqual(result["resolved_non_push"]["under"]["fair_american_odds"], 150)
        self.assertFalse(result["guardrails"]["sportsbook_quote_consumed"])
        self.assertFalse(result["guardrails"]["edge_calculated"])
        self.assertFalse(result["guardrails"]["expected_value_calculated"])

    def test_integer_line_preserves_push_and_resolves_fair_probability(self) -> None:
        result = pricing.build_step9_threshold_pricing(
            _step8_result(), stat="points", line=20, env=_env()
        )
        self.assertAlmostEqual(result["raw_probabilities"]["push"]["probability"], 0.4)
        self.assertAlmostEqual(result["raw_probabilities"]["over"]["probability"], 0.6)
        self.assertAlmostEqual(result["raw_probabilities"]["under"]["probability"], 0.0)
        self.assertAlmostEqual(result["resolved_non_push"]["probability"], 0.6)
        self.assertAlmostEqual(result["resolved_non_push"]["over"]["fair_probability"], 1.0)
        self.assertFalse(result["resolved_non_push"]["over"]["available"])
        self.assertFalse(result["resolved_non_push"]["under"]["available"])

    def test_pra_alias_maps_to_joint_step8_distribution(self) -> None:
        result = pricing.build_step9_threshold_pricing(
            _step8_result(),
            stat="points+rebounds+assists",
            line=40.5,
            env=_env(),
        )
        self.assertEqual(result["prop"]["stat"], "pra")
        self.assertEqual(
            result["prop"]["step8_distribution_key"], "points_rebounds_assists"
        )
        self.assertAlmostEqual(result["raw_probabilities"]["over"]["probability"], 0.49)

    def test_tampered_step8_payload_fails_hash_validation(self) -> None:
        payload = _step8_result()
        payload["distributions"]["points"]["probability_mass"][0]["probability"] = 0.3
        with self.assertRaises(pricing.WNBAStep9ThresholdPricingUpstreamError):
            pricing.build_step9_threshold_pricing(
                payload, stat="points", line=20.5, env=_env()
            )

    def test_nonconverged_step8_payload_is_not_ready(self) -> None:
        payload = _step8_result()
        payload["convergence"]["converged"] = False
        hash_surface = dict(payload)
        hash_surface.pop("generated_at_utc", None)
        hash_surface.pop("result_content_sha256", None)
        payload["result_content_sha256"] = pricing._canonical_hash(hash_surface)
        with self.assertRaises(pricing.WNBAStep9ThresholdPricingNotReadyError):
            pricing.build_step9_threshold_pricing(
                payload, stat="points", line=20.5, env=_env()
            )

    def test_sub_five_million_step8_payload_is_not_ready(self) -> None:
        payload = _step8_result()
        payload["simulation"]["simulations"] = step8_freeze.DEFAULT_SIMULATIONS - 1
        hash_surface = dict(payload)
        hash_surface.pop("generated_at_utc", None)
        hash_surface.pop("result_content_sha256", None)
        payload["result_content_sha256"] = pricing._canonical_hash(hash_surface)
        with self.assertRaises(pricing.WNBAStep9ThresholdPricingNotReadyError):
            pricing.build_step9_threshold_pricing(
                payload, stat="points", line=20.5, env=_env()
            )

    def test_invalid_stat_and_line_rejected_before_pricing(self) -> None:
        with self.assertRaises(ValueError):
            pricing.build_step9_threshold_pricing(
                _step8_result(), stat="steals", line=1.5, env=_env()
            )
        with self.assertRaises(ValueError):
            pricing.build_step9_threshold_pricing(
                _step8_result(), stat="points", line=251, env=_env()
            )

    def test_output_hash_is_independent_of_generation_timestamp(self) -> None:
        first = pricing.build_step9_threshold_pricing(
            _step8_result(), stat="rebounds", line=15.5, env=_env()
        )
        second = pricing.build_step9_threshold_pricing(
            _step8_result(), stat="rebounds", line=15.5, env=_env()
        )
        self.assertEqual(first["pricing_content_sha256"], second["pricing_content_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
