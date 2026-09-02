from __future__ import annotations

from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sports_api import wnba_step9_release_freeze as release
from sports_api.main import app
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)


def _step8_result(*, player_id: int = 1642301, over_probability: float = 0.64) -> dict:
    under_probability = 1.0 - over_probability
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T04:32:31+00:00",
        "game_id": "1022600291",
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {"converged": True},
        "distributions": {
            "points": {
                "probability_mass": [
                    {"value": 20, "probability": under_probability},
                    {"value": 21, "probability": over_probability},
                ]
            },
            "rebounds": {
                "probability_mass": [
                    {"value": 10, "probability": 0.4},
                    {"value": 11, "probability": 0.6},
                ]
            },
            "assists": {
                "probability_mass": [
                    {"value": 4, "probability": 0.4},
                    {"value": 5, "probability": 0.6},
                ]
            },
            "points_rebounds_assists": {
                "probability_mass": [
                    {"value": 39, "probability": 0.4},
                    {"value": 40, "probability": 0.6},
                ]
            },
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def _enabled_env() -> dict[str, str]:
    return {
        "WNBA_STEP9_FASTAPI_ENABLED": "true",
        "WNBA_STEP9_THRESHOLD_PRICING_ENABLED": "true",
        "WNBA_STEP9B_MARKET_COMPARISON_ENABLED": "true",
        "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED": "true",
        "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    }


def _request_payload() -> dict:
    captured = datetime.now(timezone.utc).isoformat()
    return {
        "props": [
            {
                "step8_distribution": _step8_result(),
                "stat": "points",
                "offers": [
                    {
                        "sportsbook": "Book A",
                        "line": 20.5,
                        "over_odds": -110,
                        "under_odds": -110,
                        "market_captured_at_utc": captured,
                    },
                    {
                        "sportsbook": "Book B",
                        "line": 20.5,
                        "over_odds": -105,
                        "under_odds": -115,
                        "market_captured_at_utc": captured,
                    },
                ],
            }
        ],
        "policy": {"top_n": 1},
    }


class Step9FastAPIIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_release_is_default_off_and_production_disallowed(self) -> None:
        self.assertFalse(release.step9_fastapi_enabled({}))
        self.assertFalse(release.DEFAULT_ENABLED)
        self.assertFalse(release.PRODUCTION_ACTIVATION_ALLOWED)

    def test_market_board_route_is_registered_once_as_post(self) -> None:
        schema = app.openapi()
        self.assertIn(release.ENDPOINT_PATH, schema["paths"])
        operations = schema["paths"][release.ENDPOINT_PATH]
        self.assertEqual(set(operations), {"post"})
        self.assertIn("wnba_step9_market_board", operations["post"]["operationId"])

    def test_disabled_step9_api_maps_to_503(self) -> None:
        env = _enabled_env()
        env["WNBA_STEP9_FASTAPI_ENABLED"] = "false"
        with patch.dict(os.environ, env, clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=_request_payload())
        self.assertEqual(response.status_code, 503)

    def test_real_frozen_a_through_d_pipeline_returns_qualified_card(self) -> None:
        with patch.dict(os.environ, _enabled_env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=_request_payload())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["release"]["release_id"], release.RELEASE_ID)
        self.assertEqual(body["pipeline"]["order"], ["step9a", "step9b", "step9c", "step9d"])
        self.assertEqual(body["board"]["qualification_summary"]["qualified_prop_count"], 1)
        self.assertEqual(body["board"]["qualification_summary"]["top_card_count"], 1)
        self.assertTrue(body["board"]["top_cards"]["not_forced"])
        card = body["board"]["top_cards"]["primary"][0]
        self.assertEqual(card["side"], "over")
        self.assertEqual(card["stat"], "points")
        self.assertGreaterEqual(card["model_probability"], 0.55)
        self.assertGreaterEqual(card["ev_per_unit"], 0.05)
        self.assertFalse(body["guardrails"]["sportsbook_network_fetch_performed"])
        self.assertFalse(body["guardrails"]["production_runtime_enabled"])

    def test_tampered_step8_distribution_maps_to_502(self) -> None:
        payload = _request_payload()
        payload["props"][0]["step8_distribution"]["distributions"]["points"]["probability_mass"][0]["probability"] = 0.10
        with patch.dict(os.environ, _enabled_env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 502)

    def test_extra_request_field_is_rejected_by_schema(self) -> None:
        payload = _request_payload()
        payload["unexpected"] = True
        with patch.dict(os.environ, _enabled_env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
