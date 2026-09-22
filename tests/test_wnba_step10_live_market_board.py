from __future__ import annotations

from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sports_api import wnba_step10_release_freeze as release
from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_market_snapshot as step10c
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.main import app
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)


def _env() -> dict[str, str]:
    return {
        "WNBA_STEP10_FASTAPI_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
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


def _step8_result(*, player_id: int = 1642301, game_id: str = "1022600291", p_over: float = 0.64) -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T05:34:00+00:00",
        "game_id": game_id,
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {"converged": True},
        "distributions": {
            "points": {"probability_mass": [
                {"value": 20, "probability": 1.0 - p_over},
                {"value": 21, "probability": p_over},
            ]},
            "rebounds": {"probability_mass": [
                {"value": 10, "probability": 0.4},
                {"value": 11, "probability": 0.6},
            ]},
            "assists": {"probability_mass": [
                {"value": 4, "probability": 0.4},
                {"value": 5, "probability": 0.6},
            ]},
            "points_rebounds_assists": {"probability_mass": [
                {"value": 39, "probability": 0.4},
                {"value": 40, "probability": 0.6},
            ]},
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def _payload(provider: str, sportsbook: str, *, player_id: int = 1642301, game_id: str = "1022600291", captured: str | None = None, over: int = -110, under: int = -110) -> dict:
    captured = captured or datetime.now(timezone.utc).isoformat()
    return {
        "provider": provider,
        "price_format": "american",
        "records": [{
            "game_id": game_id,
            "player_id": player_id,
            "player_name": f"Player {player_id}",
            "sportsbook": sportsbook,
            "stat": "points",
            "line": 20.5,
            "over_price": over,
            "under_price": under,
            "market_captured_at": captured,
        }],
    }


def _provider(provider: str, sportsbook: str, **kwargs) -> dict:
    return {
        "provider": provider,
        "adapter_type": "flat_two_way_v1",
        "attempts": [{"ok": True, "payload": _payload(provider, sportsbook, **kwargs)}],
    }


def _request(*, player_id: int = 1642301) -> dict:
    return {
        "provider_refreshes": [
            _provider("Provider A", "Book A", player_id=player_id, over=-110, under=-110),
            _provider("Provider B", "Book B", player_id=player_id, over=-105, under=-115),
        ],
        "step8_distributions": [_step8_result(player_id=player_id)],
        "qualification_policy": {"top_n": 5},
    }


def _last_good(env: dict[str, str]) -> dict:
    evaluated = datetime.now(timezone.utc)
    captured = evaluated.isoformat()
    a = step10b.adapt_step10b_market_payload(
        "flat_two_way_v1", _payload("Provider A", "Book A", captured=captured),
        evaluated_at=evaluated, env=env,
    )
    b = step10b.adapt_step10b_market_payload(
        "flat_two_way_v1", _payload("Provider B", "Book B", captured=captured, over=-105, under=-115),
        evaluated_at=evaluated, env=env,
    )
    return step10c.build_step10c_market_snapshot([a, b], evaluated_at=evaluated, env=env)


class Step10LiveMarketBoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_release_is_default_off_and_production_disallowed(self) -> None:
        self.assertFalse(release.step10_fastapi_enabled({}))
        self.assertFalse(release.DEFAULT_ENABLED)
        self.assertFalse(release.PRODUCTION_ACTIVATION_ALLOWED)

    def test_live_market_board_route_registered_once_as_post(self) -> None:
        schema = app.openapi()
        self.assertIn(release.ENDPOINT_PATH, schema["paths"])
        operations = schema["paths"][release.ENDPOINT_PATH]
        self.assertEqual(set(operations), {"post"})
        self.assertIn("wnba_step10_live_market_board", operations["post"]["operationId"])

    def test_disabled_step10_api_maps_to_503(self) -> None:
        env = _env()
        env["WNBA_STEP10_FASTAPI_ENABLED"] = "false"
        with patch.dict(os.environ, env, clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=_request())
        self.assertEqual(response.status_code, 503)

    def test_scheduler_switch_maps_to_503(self) -> None:
        env = _env()
        env["WNBA_BOARD_SCHEDULER_ENABLED"] = "true"
        with patch.dict(os.environ, env, clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=_request())
        self.assertEqual(response.status_code, 503)

    def test_full_refresh_to_frozen_step9_pipeline_returns_card(self) -> None:
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=_request())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["release"]["release_id"], release.RELEASE_ID)
        result = body["pipeline_result"]
        self.assertEqual(
            result["pipeline"]["order"],
            ["step10a", "step10b", "step10c", "step10d", "step9a", "step9b", "step9c", "step9d"],
        )
        self.assertEqual(result["refresh_cycle"]["status"], "ready")
        self.assertEqual(result["refresh_cycle"]["snapshot_source"], "current_refresh")
        self.assertEqual(result["pipeline"]["matched_prop_count"], 1)
        self.assertEqual(result["board"]["qualification_summary"]["qualified_prop_count"], 1)
        self.assertEqual(result["board"]["qualification_summary"]["top_card_count"], 1)
        self.assertTrue(result["board"]["top_cards"]["not_forced"])
        self.assertFalse(result["guardrails"]["sportsbook_network_fetch_performed"])
        self.assertFalse(result["guardrails"]["scheduler_started"])
        self.assertFalse(result["guardrails"]["production_runtime_enabled"])
        self.assertTrue(result["pipeline_content_sha256"])

    def test_provider_retry_then_success_reaches_board_without_sleep(self) -> None:
        payload = _request()
        payload["provider_refreshes"][0]["attempts"] = [
            {"ok": False, "error_code": "timeout"},
            {"ok": True, "payload": _payload("Provider A", "Book A")},
        ]
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["pipeline_result"]
        self.assertEqual(result["refresh_cycle"]["refresh"]["total_attempts_consumed"], 3)
        self.assertFalse(result["guardrails"]["retry_sleep_performed"])

    def test_verified_last_good_can_feed_step9_when_current_providers_fail(self) -> None:
        env = _env()
        with patch.dict(os.environ, env, clear=False):
            last_good = _last_good(env)
            payload = {
                "provider_refreshes": [
                    {"provider": "Provider A", "adapter_type": "flat_two_way_v1", "attempts": [{"ok": False, "error_code": "timeout"}]},
                    {"provider": "Provider B", "adapter_type": "flat_two_way_v1", "attempts": [{"ok": False, "error_code": "upstream_503"}]},
                ],
                "step8_distributions": [_step8_result()],
                "last_good_snapshot": last_good,
            }
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["pipeline_result"]
        self.assertEqual(result["refresh_cycle"]["status"], "degraded_last_good")
        self.assertEqual(result["lineage"]["snapshot_source"], "last_good_snapshot")
        self.assertEqual(result["board"]["qualification_summary"]["qualified_prop_count"], 1)

    def test_market_without_matching_step8_returns_409(self) -> None:
        payload = _request(player_id=1642301)
        payload["step8_distributions"] = [_step8_result(player_id=1642302)]
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 409)

    def test_one_surviving_offer_is_not_promoted_to_step9(self) -> None:
        payload = _request()
        payload["provider_refreshes"] = [payload["provider_refreshes"][0]]
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 409)

    def test_duplicate_step8_identity_is_422(self) -> None:
        payload = _request()
        payload["step8_distributions"].append(_step8_result())
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 422)

    def test_tampered_step8_distribution_maps_to_502(self) -> None:
        payload = _request()
        payload["step8_distributions"][0]["distributions"]["points"]["probability_mass"][0]["probability"] = 0.10
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 502)

    def test_extra_request_field_is_rejected_by_schema(self) -> None:
        payload = _request()
        payload["unexpected"] = True
        with patch.dict(os.environ, _env(), clear=False):
            response = self.client.post(release.ENDPOINT_PATH, json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
