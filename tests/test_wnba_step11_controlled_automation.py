from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step10_live_pipeline import WNBAStep10LivePipelineNotReadyError
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)


def _env() -> dict[str, str]:
    return {
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
    }


def _step8_result(player_id: int = 1642301, game_id: str = "1022600291", p_over: float = 0.64) -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T06:30:00+00:00",
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


def _payload(provider: str, evaluated: datetime) -> dict:
    over, under = (-110, -110) if provider == dk.PROVIDER else (-105, -115)
    return {
        "provider": provider,
        "price_format": "american",
        "records": [{
            "game_id": "1022600291",
            "player_id": 1642301,
            "player_name": "Player 1642301",
            "sportsbook": provider,
            "stat": "points",
            "line": 20.5,
            "over_price": over,
            "under_price": under,
            "market_captured_at": evaluated.isoformat(),
        }],
    }


def _bridge(provider: str, evaluated: datetime) -> dict:
    payload = _payload(provider, evaluated)
    if provider == dk.PROVIDER:
        result = {
            "data_type": "wnba_step11a_draftkings_provider_bridge",
            "schema_version": dk.SCHEMA_VERSION,
            "model_version": dk.MODEL_VERSION,
            "release_id": dk.RELEASE_ID,
            "generated_at_utc": evaluated.isoformat(),
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": dk.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step10_frozen_git_sha": release.STEP10_FROZEN_SHA,
                "step10b_frozen_git_sha": "5dbc9656665821367728e6a16f8f9741f8331360",
            },
            "guardrails": {
                "sportsbook_network_fetch_performed": True,
                "sportsbook_http_methods": ["GET"],
                "authentication_used": False,
                "cookies_used": False,
                "wager_action_performed": False,
                "paid_odds_vendor_used": False,
                "basketball_projection_changed": False,
                "step8_distribution_changed": False,
                "supabase_mutated": False,
                "persistence_mutated": False,
                "scheduler_started": False,
                "production_runtime_enabled": False,
                "production_activation_allowed": False,
            },
        }
    else:
        result = {
            "data_type": "wnba_step11c_fanduel_provider_bridge",
            "schema_version": fd.SCHEMA_VERSION,
            "model_version": fd.MODEL_VERSION,
            "release_id": fd.RELEASE_ID,
            "generated_at_utc": evaluated.isoformat(),
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": fd.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step11b_frozen_git_sha": release.STEP11B_FROZEN_SHA,
                "step11a_frozen_git_sha": release.STEP11A_FROZEN_SHA,
                "step10_frozen_git_sha": release.STEP10_FROZEN_SHA,
                "step10b_frozen_git_sha": "5dbc9656665821367728e6a16f8f9741f8331360",
            },
            "guardrails": {
                "sportsbook_network_fetch_performed": True,
                "sportsbook_http_methods": ["GET"],
                "authentication_used": False,
                "cookies_used": False,
                "wager_action_performed": False,
                "paid_odds_vendor_used": False,
                "basketball_projection_changed": False,
                "step8_distribution_changed": False,
                "supabase_mutated": False,
                "persistence_mutated": False,
                "scheduler_started": False,
                "production_runtime_enabled": False,
                "production_activation_allowed": False,
            },
        }
    surface = {k: v for k, v in result.items() if k != "generated_at_utc"}
    result["provider_bridge_content_sha256"] = step11e.step11d._canonical_hash(surface)
    return result


def _fetcher(provider: str):
    def fetch(**kwargs):
        return _bridge(provider, kwargs["evaluated_at"])
    return fetch


def _shadow_result() -> dict:
    return {
        "shadow_board_content_sha256": "a" * 64,
        "lineage": {
            "step10_pipeline_content_sha256": "b" * 64,
            "step9_ranking_content_sha256": "c" * 64,
        },
    }


def _tick(at: datetime, *, previous_state=None, **kwargs):
    return step11e.run_step11e_controlled_automation_tick(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=[_step8_result()],
        previous_state=previous_state,
        evaluated_at=at,
        env=_env(),
        **kwargs,
    )


class Step11ControlledAutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 28, 6, 40, tzinfo=timezone.utc)

    def test_step11e_flag_is_default_off(self) -> None:
        self.assertFalse(step11e.step11e_controlled_automation_enabled({}))

    def test_final_release_is_default_off_and_production_scheduler_disallowed(self) -> None:
        self.assertFalse(release.DEFAULT_ENABLED)
        self.assertFalse(release.PRODUCTION_ACTIVATION_ALLOWED)
        self.assertFalse(release.BACKGROUND_SCHEDULER_ALLOWED)
        self.assertFalse(release.PUBLIC_FASTAPI_ACTIVATION_ALLOWED)

    def test_production_switch_fails_closed(self) -> None:
        env = _env(); env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationDisabledError):
            step11e.run_step11e_controlled_automation_tick(
                season=2026, slate_date="2026-08-28", step8_distributions=[_step8_result()], evaluated_at=self.t0, env=env
            )

    def test_scheduler_switch_fails_closed(self) -> None:
        env = _env(); env["WNBA_BOARD_SCHEDULER_ENABLED"] = "true"
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationDisabledError):
            step11e.run_step11e_controlled_automation_tick(
                season=2026, slate_date="2026-08-28", step8_distributions=[_step8_result()], evaluated_at=self.t0, env=env
            )

    def test_frozen_lower_gate_is_required_even_when_tick_would_skip(self) -> None:
        env = _env(); env["WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED"] = "false"
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationDisabledError):
            step11e.run_step11e_controlled_automation_tick(
                season=2026, slate_date="2026-08-28", step8_distributions=[_step8_result()], evaluated_at=self.t0, env=env
            )

    def test_only_2026_regular_season_is_certified(self) -> None:
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError):
            step11e.run_step11e_controlled_automation_tick(
                season=2025, slate_date="2026-08-28", step8_distributions=[_step8_result()], evaluated_at=self.t0, env=_env()
            )

    def test_policy_bounds_fail_closed(self) -> None:
        for kwargs in (
            {"refresh_interval_seconds": 14},
            {"failure_threshold": 0},
            {"circuit_cooldown_seconds": 29},
            {"provider_attempts": 6},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError):
                _tick(self.t0, **kwargs)

    def test_initial_due_tick_success_is_healthy_and_returns_state(self) -> None:
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()) as mocked:
            result = _tick(self.t0)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["health"], "healthy")
        self.assertTrue(result["execution"]["cycle_executed"])
        self.assertEqual(result["automation_state"]["circuit_state"], "closed")
        self.assertEqual(result["automation_state"]["consecutive_failure_count"], 0)
        self.assertTrue(result["automation_state"]["state_content_sha256"])
        self.assertFalse(result["guardrails"]["background_scheduler_started"])
        self.assertFalse(result["guardrails"]["state_persisted"])

    def test_not_due_tick_skips_without_calling_step11d(self) -> None:
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()):
            first = _tick(self.t0)
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board") as mocked:
            second = _tick(self.t0 + timedelta(seconds=30), previous_state=first["automation_state"])
        mocked.assert_not_called()
        self.assertEqual(second["status"], "not_due")
        self.assertEqual(second["execution"]["skip_reason"], "refresh_not_due")
        self.assertFalse(second["guardrails"]["sportsbook_network_fetch_attempted"])

    def test_tampered_previous_state_hash_is_rejected(self) -> None:
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()):
            first = _tick(self.t0)
        bad = deepcopy(first["automation_state"]); bad["consecutive_failure_count"] = 99
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationIntegrityError):
            _tick(self.t0 + timedelta(seconds=60), previous_state=bad)

    def test_policy_change_requires_state_reset(self) -> None:
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()):
            first = _tick(self.t0)
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError):
            _tick(self.t0 + timedelta(seconds=60), previous_state=first["automation_state"], refresh_interval_seconds=120)

    def test_state_time_reversal_is_rejected(self) -> None:
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()):
            first = _tick(self.t0)
        with self.assertRaises(step11e.WNBAStep11ControlledAutomationInputError):
            _tick(self.t0 - timedelta(seconds=1), previous_state=first["automation_state"])

    def test_first_transient_provider_failure_is_degraded_not_open(self) -> None:
        with patch.object(
            step11e.step11d,
            "run_step11d_multibook_shadow_board",
            side_effect=step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("books unavailable"),
        ):
            result = _tick(self.t0)
        self.assertEqual(result["status"], "transient_failure")
        self.assertEqual(result["health"], "degraded")
        self.assertEqual(result["automation_state"]["consecutive_failure_count"], 1)
        self.assertEqual(result["automation_state"]["circuit_state"], "closed")

    def test_third_consecutive_transient_failure_opens_circuit(self) -> None:
        exc = step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("provider outage")
        state = None
        statuses = []
        for offset in (0, 60, 120):
            with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", side_effect=exc):
                result = _tick(self.t0 + timedelta(seconds=offset), previous_state=state)
            statuses.append(result["status"]); state = result["automation_state"]
        self.assertEqual(statuses, ["transient_failure", "transient_failure", "circuit_opened"])
        self.assertEqual(state["circuit_state"], "open")
        self.assertEqual(state["consecutive_failure_count"], 3)
        self.assertEqual(state["circuit_open_until_utc"], (self.t0 + timedelta(seconds=300)).isoformat())

    def test_open_circuit_skips_network_until_cooldown_expires(self) -> None:
        exc = step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("provider outage")
        state = None
        for offset in (0, 60, 120):
            with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", side_effect=exc):
                state = _tick(self.t0 + timedelta(seconds=offset), previous_state=state)["automation_state"]
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board") as mocked:
            result = _tick(self.t0 + timedelta(seconds=180), previous_state=state)
        mocked.assert_not_called()
        self.assertEqual(result["status"], "circuit_open")
        self.assertEqual(result["execution"]["skip_reason"], "circuit_open_cooldown")

    def test_half_open_success_closes_circuit_and_resets_failures(self) -> None:
        exc = step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("provider outage")
        state = None
        for offset in (0, 60, 120):
            with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", side_effect=exc):
                state = _tick(self.t0 + timedelta(seconds=offset), previous_state=state)["automation_state"]
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()):
            recovered = _tick(self.t0 + timedelta(seconds=300), previous_state=state)
        self.assertEqual(recovered["status"], "half_open_recovered")
        self.assertTrue(recovered["execution"]["half_open_probe"])
        self.assertEqual(recovered["automation_state"]["circuit_state"], "closed")
        self.assertEqual(recovered["automation_state"]["consecutive_failure_count"], 0)

    def test_half_open_failure_reopens_new_cooldown(self) -> None:
        exc = step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("provider outage")
        state = None
        for offset in (0, 60, 120):
            with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", side_effect=exc):
                state = _tick(self.t0 + timedelta(seconds=offset), previous_state=state)["automation_state"]
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", side_effect=exc):
            failed = _tick(self.t0 + timedelta(seconds=300), previous_state=state)
        self.assertEqual(failed["status"], "half_open_failed")
        self.assertEqual(failed["automation_state"]["circuit_state"], "open")
        self.assertEqual(failed["automation_state"]["circuit_open_until_utc"], (self.t0 + timedelta(seconds=480)).isoformat())

    def test_market_board_not_ready_does_not_trip_provider_circuit(self) -> None:
        with patch.object(
            step11e.step11d,
            "run_step11d_multibook_shadow_board",
            side_effect=WNBAStep10LivePipelineNotReadyError("no exact same-line market"),
        ):
            result = _tick(self.t0)
        self.assertEqual(result["status"], "market_not_ready")
        self.assertEqual(result["health"], "market_not_ready")
        self.assertEqual(result["automation_state"]["consecutive_failure_count"], 0)
        self.assertEqual(result["automation_state"]["circuit_state"], "closed")

    def test_terminal_identity_error_is_never_hidden_by_circuit_breaker(self) -> None:
        with patch.object(
            step11e.step11d,
            "run_step11d_multibook_shadow_board",
            side_effect=dk.WNBAStep11DraftKingsProviderIdentityError("identity mismatch"),
        ):
            with self.assertRaises(dk.WNBAStep11DraftKingsProviderIdentityError):
                _tick(self.t0)

    def test_actual_frozen_step11d_two_book_pipeline_reaches_qualified_shadow_card(self) -> None:
        result = _tick(
            self.t0,
            draftkings_fetcher=_fetcher(dk.PROVIDER),
            fanduel_fetcher=_fetcher(fd.PROVIDER),
        )
        self.assertEqual(result["status"], "healthy")
        shadow = result["shadow_board_result"]
        self.assertEqual(shadow["sportsbooks"], ["DraftKings", "FanDuel"])
        self.assertEqual(shadow["market_audit"]["exact_line_multibook_group_count"], 1)
        self.assertEqual(shadow["shadow_summary"]["qualified_prop_count"], 1)
        self.assertEqual(shadow["shadow_summary"]["top_card_count"], 1)
        self.assertFalse(shadow["guardrails"]["different_lines_blended"])

    def test_guardrails_never_start_scheduler_persist_or_activate_production(self) -> None:
        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board", return_value=_shadow_result()):
            result = _tick(self.t0)
        guards = result["guardrails"]
        for key in (
            "background_scheduler_started",
            "sleep_performed",
            "authentication_used",
            "cookies_used",
            "wager_action_performed",
            "state_persisted",
            "public_fastapi_route_added",
            "supabase_mutated",
            "persistence_mutated",
            "production_runtime_enabled",
            "production_activation_allowed",
            "basketball_projection_changed",
            "step8_distribution_changed",
        ):
            self.assertFalse(guards[key], key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
