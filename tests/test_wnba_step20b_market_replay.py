from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step20b_market_replay as replay
from sports_api.api import wnba_step20b_replay_runtime as replay_api


class Step20BMarketReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = {replay.STEP20B_MARKET_REPLAY_ENABLED_ENV: "true"}
        self.at = datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc)

    def test_default_off_and_frozen_runtime_counts(self):
        self.assertFalse(replay.market_replay_enabled({}))
        self.assertEqual(step12b.CERTIFIED_SIMULATIONS, 5_000_000)
        self.assertEqual(step12b.CERTIFIED_BATCH_SIZE, 250_000)
        status = replay.installation_status({})
        self.assertFalse(status["enabled"])
        guards = status["guardrails"]
        self.assertTrue(guards["default_off"])
        self.assertTrue(guards["certification_only"])
        self.assertFalse(guards["projection_loader_injected"])
        self.assertFalse(guards["simulations_modified"])
        self.assertFalse(guards["batch_size_modified"])
        self.assertFalse(guards["projection_math_modified"])
        self.assertFalse(guards["readiness_relaxed"])
        self.assertFalse(guards["sportsbook_transport_modified"])
        self.assertFalse(guards["persistence_modified"])
        self.assertFalse(guards["wagering_enabled"])

    def test_replay_requires_explicit_gate(self):
        with self.assertRaises(RuntimeError):
            replay.draftkings_replay_fetcher(
                season=2026,
                slate_date="2026-08-31",
                evaluated_at=self.at,
                env={},
            )

    def test_both_replay_bridges_pass_unmodified_frozen_verifier(self):
        dk_bridge = replay.draftkings_replay_fetcher(
            season=2026,
            slate_date="2026-08-31",
            evaluated_at=self.at,
            env=self.env,
        )
        fd_bridge = replay.fanduel_replay_fetcher(
            season=2026,
            slate_date="2026-08-31",
            evaluated_at=self.at,
            env=self.env,
        )
        dk_payload = step11d._verify_bridge(dk_bridge, provider=dk.PROVIDER)
        fd_payload = step11d._verify_bridge(fd_bridge, provider=fd.PROVIDER)
        dk_row = dk_payload["records"][0]
        fd_row = fd_payload["records"][0]
        for key in ("game_id", "player_id", "stat", "line"):
            self.assertEqual(dk_row[key], fd_row[key])
        self.assertEqual(dk_row["game_id"], replay.REPLAY_GAME_ID)
        self.assertEqual(dk_row["player_id"], replay.REPLAY_PLAYER_ID)
        self.assertEqual(len(dk_payload["records"]), 1)
        self.assertEqual(len(fd_payload["records"]), 1)
        self.assertTrue(dk_bridge["replay_metadata"]["quote_values_are_deterministic_certification_placeholders"])
        self.assertFalse(dk_bridge["replay_metadata"]["sportsbook_network_performed_during_replay_invocation"])

    def test_replay_fetchers_return_isolated_deep_copies(self):
        first = replay.draftkings_replay_fetcher(
            season=2026,
            slate_date="2026-08-31",
            evaluated_at=self.at,
            env=self.env,
        )
        pristine = deepcopy(first)
        first["provider_refresh"]["attempts"][0]["payload"]["records"][0]["line"] = 999.5
        second = replay.draftkings_replay_fetcher(
            season=2026,
            slate_date="2026-08-31",
            evaluated_at=self.at,
            env=self.env,
        )
        self.assertEqual(second, pristine)

    def test_runtime_helper_injects_only_provider_fetchers(self):
        captured: dict = {}

        def fake_runner(request, **kwargs):
            captured["request"] = request
            captured["kwargs"] = kwargs
            return {"status": "captured"}

        runtime_env = {replay.STEP20B_MARKET_REPLAY_ENABLED_ENV: "true"}
        with patch.object(
            replay_api.step12b,
            "run_step12b_live_runtime_job",
            side_effect=fake_runner,
        ):
            result = replay_api._run_replay_job(
                runtime_env,
                slate_date="2026-08-31",
            )

        self.assertEqual(result["status"], "captured")
        kwargs = captured["kwargs"]
        self.assertIs(kwargs["draftkings_fetcher"], replay.draftkings_replay_fetcher)
        self.assertIs(kwargs["fanduel_fetcher"], replay.fanduel_replay_fetcher)
        self.assertNotIn("projection_loader", kwargs)
        self.assertNotIn("step12a_runner", kwargs)
        self.assertEqual(captured["request"]["season"], 2026)

    def test_live_provider_bindings_are_not_replaced(self):
        self.assertIsNot(dk.fetch_step11a_draftkings_provider_bridge, replay.draftkings_replay_fetcher)
        self.assertIsNot(fd.fetch_step11c_fanduel_provider_bridge, replay.fanduel_replay_fetcher)


if __name__ == "__main__":
    unittest.main()
