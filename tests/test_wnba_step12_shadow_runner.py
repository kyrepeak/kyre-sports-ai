from __future__ import annotations

from copy import deepcopy
import io
import json
import sys
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api.tools import wnba_step12a_shadow_runner as cli
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)


def env():
    return {
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED": "true",
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED": "true",
        "WNBA_STEP11B_NETWORK_REFRESH_ENABLED": "true",
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
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
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def step8():
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T06:30:00+00:00",
        "game_id": "1022600291",
        "player_id": 1642301,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {"converged": True},
        "distributions": {
            "points": {"probability_mass": [{"value": 20, "probability": 0.36}, {"value": 21, "probability": 0.64}]},
            "rebounds": {"probability_mass": [{"value": 10, "probability": 0.4}, {"value": 11, "probability": 0.6}]},
            "assists": {"probability_mass": [{"value": 4, "probability": 0.4}, {"value": 5, "probability": 0.6}]},
            "points_rebounds_assists": {"probability_mass": [{"value": 39, "probability": 0.4}, {"value": 40, "probability": 0.6}]},
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def request(previous_state=None):
    return step12a.build_step12a_request(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=[step8()],
        previous_state=previous_state,
        evaluated_at="2026-08-28T06:45:00+00:00",
    )


def fake_tick(**kwargs):
    state = {"state_content_sha256": "d" * 64}
    return {
        "status": "healthy",
        "health": "healthy",
        "execution": {
            "cycle_due": True,
            "cycle_executed": True,
            "cycle_outcome": "shadow_board_ready",
            "skip_reason": None,
            "half_open_probe": False,
        },
        "automation_state": state,
        "shadow_board_result": {"shadow_board_content_sha256": "a" * 64},
        "controller_content_sha256": "e" * 64,
        "lineage": {
            "step11_release_id": release.RELEASE_ID,
            "step11a_frozen_sha": release.STEP11A_FROZEN_SHA,
            "step11b_frozen_sha": release.STEP11B_FROZEN_SHA,
            "step11c_frozen_sha": release.STEP11C_FROZEN_SHA,
            "step11d_frozen_sha": release.STEP11D_FROZEN_SHA,
            "step10_frozen_sha": release.STEP10_FROZEN_SHA,
            "step9_frozen_sha": release.STEP9_FROZEN_SHA,
            "step8_frozen_sha": release.STEP8_FROZEN_SHA,
        },
        "guardrails": {
            "caller_driven_tick_only": True,
            "background_scheduler_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
        },
    }


class Tests(unittest.TestCase):
    def test_default_off_and_frozen_parent(self):
        self.assertFalse(step12a.step12a_shadow_runner_enabled({}))
        self.assertEqual(
            step12a.STEP11E_FROZEN_SHA,
            "f96d580e398aaa199c424e3b70b7a8f1386a8452",
        )

    def test_requires_step11e_gate(self):
        e = env()
        e["WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED"] = "false"
        with self.assertRaises(step12a.WNBAStep12ShadowRunnerDisabledError):
            step12a.run_step12a_shadow_job(request(), env=e, tick_runner=fake_tick)

    def test_refuses_all_external_activation_switches(self):
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        ):
            e = env()
            e[key] = "true"
            with self.assertRaises(
                step12a.WNBAStep12ShadowRunnerDisabledError,
                msg=key,
            ):
                step12a.run_step12a_shadow_job(request(), env=e, tick_runner=fake_tick)

    def test_request_hash_is_tamper_evident(self):
        bad = deepcopy(request())
        bad["slate_date"] = "2026-08-29"
        with self.assertRaises(step12a.WNBAStep12ShadowRunnerIntegrityError):
            step12a.run_step12a_shadow_job(bad, env=env(), tick_runner=fake_tick)

    def test_one_external_job_calls_exactly_one_tick(self):
        calls = []

        def runner(**kwargs):
            calls.append(kwargs)
            return fake_tick(**kwargs)

        result = step12a.run_step12a_shadow_job(
            request(), env=env(), tick_runner=runner
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["season"], 2026)
        self.assertEqual(calls[0]["slate_date"], "2026-08-28")
        self.assertEqual(result["status"], "healthy")
        self.assertTrue(result["guardrails"]["external_execution_surface"])
        self.assertFalse(result["guardrails"]["state_persisted"])

    def test_previous_state_is_forwarded_without_storage(self):
        prior = {"state_content_sha256": "1" * 64}
        captured = {}

        def runner(**kwargs):
            captured.update(kwargs)
            return fake_tick(**kwargs)

        step12a.run_step12a_shadow_job(
            request(prior), env=env(), tick_runner=runner
        )
        self.assertEqual(captured["previous_state"], prior)

    def test_unsafe_downstream_tick_is_rejected(self):
        bad = fake_tick()
        bad["guardrails"]["supabase_mutated"] = True
        with self.assertRaises(step12a.WNBAStep12ShadowRunnerIntegrityError):
            step12a.run_step12a_shadow_job(
                request(), env=env(), tick_runner=lambda **_: bad
            )

    def test_real_frozen_step11e_boundary(self):
        shadow = {
            "shadow_board_content_sha256": "a" * 64,
            "lineage": {
                "step10_pipeline_content_sha256": "b" * 64,
                "step9_ranking_content_sha256": "c" * 64,
            },
        }
        with patch.object(
            step11e.step11d,
            "run_step11d_multibook_shadow_board",
            return_value=shadow,
        ):
            result = step12a.run_step12a_shadow_job(request(), env=env())
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(
            result["lineage"]["step11e_frozen_sha"],
            step12a.STEP11E_FROZEN_SHA,
        )
        self.assertEqual(result["step11e_tick"]["shadow_board_result"], shadow)

    def test_cli_stdin_stdout_contract(self):
        fake_response = {"ok": True}
        stdin = io.StringIO(json.dumps(request()))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(
            sys, "stdout", stdout
        ), patch.object(sys, "stderr", stderr), patch.object(
            cli.step12a,
            "run_step12a_shadow_job",
            return_value=fake_response,
        ):
            code = cli.main()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), fake_response)
        self.assertEqual(stderr.getvalue(), "")

    def test_unknown_request_field_is_fail_closed(self):
        bad = request()
        bad.pop("request_content_sha256")
        bad["surprise"] = "nope"
        with self.assertRaises(step12a.WNBAStep12ShadowRunnerInputError):
            step12a.run_step12a_shadow_job(bad, env=env(), tick_runner=fake_tick)


if __name__ == "__main__":
    unittest.main(verbosity=2)
