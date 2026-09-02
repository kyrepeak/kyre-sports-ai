from __future__ import annotations

import os
import unittest

import numpy as np

from sports_api.wnba_step8_context_adjustment import MODEL_VERSION as STEP8C_MODEL_VERSION, SCHEMA_VERSION as STEP8C_SCHEMA_VERSION
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION,
    _build_model_spec,
    _regularization_weight,
    probability_for_line,
    simulate_step8_joint_distribution,
    step8_monte_carlo_enabled,
)


SAFE_ENV = {
    "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    "WNBA_BOARD_SCHEDULER_ENABLED": "false",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
    "WNBA_STEP6J_CANARY_ENABLED": "false",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
    "WNBA_STEP8_CORE_PROJECTION_ENABLED": "true",
    "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED": "true",
    "WNBA_STEP8_MONTE_CARLO_ENABLED": "true",
}


def _fixture() -> tuple[dict, dict]:
    rows = [
        (11, 26, 3),
        (31, 14, 2),
        (20, 10, 8),
        (21, 10, 4),
        (15, 14, 6),
    ]
    games = [
        {
            "game_id": str(index),
            "points": p,
            "rebounds": r,
            "assists": a,
            "points_rebounds_assists": p + r + a,
        }
        for index, (p, r, a) in enumerate(rows, 1)
    ]
    adjusted = {
        "data_type": "context_adjusted_deterministic_player_projection",
        "schema_version": STEP8C_SCHEMA_VERSION,
        "model_version": STEP8C_MODEL_VERSION,
        "game_id": "target-game",
        "player_id": 1642291,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "projection_id": "fixture-projection",
        "projection_content_sha256": "a" * 64,
        "projection": {
            "points": 20.446228,
            "rebounds": 15.438988,
            "assists": 4.798605,
            "points_rebounds_assists": 40.683821,
        },
    }
    baseline = {
        "data_type": "official_recent_player_box_stat_baseline",
        "requested_game_id": "target-game",
        "player_id": 1642291,
        "baseline_content_sha256": "b" * 64,
        "selected_game_ids": [str(i) for i in range(1, 6)],
        "games": games,
    }
    return adjusted, baseline


class Step8JointMonteCarloTests(unittest.TestCase):
    def test_flag_is_default_off(self) -> None:
        env = dict(os.environ)
        env.pop("WNBA_STEP8_MONTE_CARLO_ENABLED", None)
        self.assertFalse(step8_monte_carlo_enabled(env))

    def test_five_game_evidence_weight_is_one_quarter(self) -> None:
        self.assertAlmostEqual(_regularization_weight(5), 0.25, places=12)

    def test_empirical_correlation_is_shrunk_toward_identity_and_psd(self) -> None:
        adjusted, baseline = _fixture()
        matrix = np.asarray(
            [[row[stat] for stat in ("points", "rebounds", "assists")] for row in baseline["games"]],
            dtype=float,
        )
        spec = _build_model_spec(adjusted["projection"], matrix)
        empirical = spec["empirical_correlation"]
        regularized = spec["regularized_latent_correlation"]
        for i in range(3):
            self.assertAlmostEqual(regularized[i, i], 1.0, places=12)
            for j in range(3):
                if i != j:
                    self.assertAlmostEqual(regularized[i, j], 0.25 * empirical[i, j], places=12)
        self.assertGreater(float(np.min(np.linalg.eigvalsh(regularized))), 0.0)

    def test_overdispersed_points_and_rebounds_use_negative_binomial(self) -> None:
        adjusted, baseline = _fixture()
        matrix = np.asarray(
            [[row[stat] for stat in ("points", "rebounds", "assists")] for row in baseline["games"]],
            dtype=float,
        )
        spec = _build_model_spec(adjusted["projection"], matrix)
        self.assertEqual(spec["marginals"]["points"]["family"], "negative_binomial")
        self.assertEqual(spec["marginals"]["rebounds"]["family"], "negative_binomial")
        self.assertGreater(spec["marginals"]["points"]["variance"], adjusted["projection"]["points"])
        self.assertGreater(spec["marginals"]["rebounds"]["variance"], adjusted["projection"]["rebounds"])

    def test_small_simulation_preserves_target_means_and_joint_pra_identity(self) -> None:
        adjusted, baseline = _fixture()
        result = simulate_step8_joint_distribution(
            adjusted,
            baseline,
            simulations=120_000,
            batch_size=20_000,
            seed=123456,
            env=SAFE_ENV,
        )
        self.assertEqual(result["model_version"], MODEL_VERSION)
        self.assertFalse(result["convergence"]["converged"])
        distributions = result["distributions"]
        for stat in ("points", "rebounds", "assists"):
            self.assertLess(abs(distributions[stat]["expected"] - adjusted["projection"][stat]), 0.12)
            self.assertAlmostEqual(distributions[stat]["probability_mass_sum"], 1.0, places=10)
        component_mean = sum(distributions[stat]["expected"] for stat in ("points", "rebounds", "assists"))
        self.assertAlmostEqual(distributions["points_rebounds_assists"]["expected"], component_mean, places=6)
        self.assertTrue(result["guardrails"]["p_r_a_not_simulated_independently"])
        self.assertTrue(result["guardrails"]["pra_recomposed_from_same_joint_p_r_a_draws"])

    def test_probability_for_line_handles_half_and_integer_lines(self) -> None:
        adjusted, baseline = _fixture()
        result = simulate_step8_joint_distribution(
            adjusted,
            baseline,
            simulations=40_000,
            batch_size=10_000,
            seed=7,
            env=SAFE_ENV,
        )
        half = probability_for_line(result, "rebounds", 15.5)
        self.assertEqual(half["push_probability"], 0.0)
        self.assertAlmostEqual(half["under_probability"] + half["over_probability"], 1.0, places=7)
        integer = probability_for_line(result, "assists", 5.0)
        self.assertGreaterEqual(integer["push_probability"], 0.0)
        self.assertAlmostEqual(
            integer["under_probability"] + integer["push_probability"] + integer["over_probability"],
            1.0,
            places=7,
        )

    def test_production_switch_fails_closed(self) -> None:
        adjusted, baseline = _fixture()
        bad = dict(SAFE_ENV)
        bad["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        with self.assertRaises(RuntimeError):
            simulate_step8_joint_distribution(
                adjusted,
                baseline,
                simulations=10_000,
                batch_size=10_000,
                seed=1,
                env=bad,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
