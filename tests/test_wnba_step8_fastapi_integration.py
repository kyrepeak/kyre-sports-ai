from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sports_api import wnba_step8_release_freeze as freeze
from sports_api.main import app
from sports_api.wnba_step8_joint_monte_carlo import WNBAStep8MonteCarloDisabledError


PATH = "/api/v1/wnba/games/1022600291/players/1642291/projection-probabilities"


def _fake_result() -> dict:
    return {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": "wnba_step_8d_joint_probability_distribution_v1",
        "model_version": freeze.MODEL_VERSIONS["step8d"],
        "game_id": "1022600291",
        "player_id": 1642291,
        "simulation": {"simulations": 5_000_000},
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


class Step8FastAPIIntegrationTests(unittest.TestCase):
    def test_release_freeze_is_default_off(self) -> None:
        self.assertFalse(freeze.DEFAULT_ENABLED)
        self.assertFalse(freeze.PRODUCTION_ACTIVATION_ALLOWED)
        self.assertFalse(freeze.SAFETY_CONTRACT["sportsbook_calls_allowed"])
        self.assertFalse(freeze.SAFETY_CONTRACT["supabase_mutation_allowed"])
        self.assertFalse(freeze.SAFETY_CONTRACT["persistence_mutation_allowed"])

    def test_projection_probability_route_is_registered_once(self) -> None:
        matches = [
            route
            for route in app.routes
            if getattr(route, "path", None)
            == "/api/v1/wnba/games/{game_id}/players/{player_id}/projection-probabilities"
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("GET", matches[0].methods)

    def test_route_returns_distribution_and_requested_line_probabilities(self) -> None:
        with patch(
            "sports_api.api.wnba_step8_projection.get_player_game_step8_joint_probability_distribution",
            return_value=_fake_result(),
        ) as mocked:
            with TestClient(app) as client:
                response = client.get(
                    PATH,
                    params={
                        "simulation_count": 10000,
                        "batch_size": 10000,
                        "points_line": 20.5,
                        "rebounds_line": 15.5,
                        "assists_line": 4.5,
                        "pra_line": 40.5,
                    },
                )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body["requested_line_probabilities"]),
            {"points", "rebounds", "assists", "points_rebounds_assists"},
        )
        self.assertAlmostEqual(
            body["requested_line_probabilities"]["points"]["over_probability"],
            0.6,
            places=9,
        )
        self.assertAlmostEqual(
            body["requested_line_probabilities"]["points"]["under_probability"],
            0.4,
            places=9,
        )
        mocked.assert_called_once_with(
            1642291,
            "1022600291",
            simulations=10000,
            batch_size=10000,
        )

    def test_invalid_identity_fails_before_model_call(self) -> None:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/wnba/games/not-a-game/players/1642291/projection-probabilities"
            )
        self.assertEqual(response.status_code, 400)

    def test_batch_larger_than_simulation_count_is_422(self) -> None:
        with TestClient(app) as client:
            response = client.get(
                PATH,
                params={"simulation_count": 10000, "batch_size": 20000},
            )
        self.assertEqual(response.status_code, 422)

    def test_disabled_step8_maps_to_503(self) -> None:
        with patch(
            "sports_api.api.wnba_step8_projection.get_player_game_step8_joint_probability_distribution",
            side_effect=WNBAStep8MonteCarloDisabledError("Step 8D disabled for test"),
        ):
            with TestClient(app) as client:
                response = client.get(
                    PATH,
                    params={"simulation_count": 10000, "batch_size": 10000},
                )
        self.assertEqual(response.status_code, 503)
        self.assertIn("disabled", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
