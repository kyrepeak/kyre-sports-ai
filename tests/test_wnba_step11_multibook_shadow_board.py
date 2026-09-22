from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step11_multibook_shadow_board as s11d
from sports_api.main import app
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import MODEL_VERSION as S8_MODEL, SCHEMA_VERSION as S8_SCHEMA

UTC = timezone.utc
EVALUATED = datetime(2026, 8, 28, 6, 20, 0, tzinfo=UTC)
GAME_ID = "1022600291"
PLAYER_ID = 1642301


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED": "true",
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
        "WNBA_STEP11B_NETWORK_REFRESH_ENABLED": "true",
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED": "true",
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
    env.update(overrides)
    return env


def _step8_result(p_over: float = 0.64) -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": S8_SCHEMA,
        "model_version": S8_MODEL,
        "generated_at_utc": "2026-08-28T06:19:00+00:00",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {"converged": True},
        "distributions": {
            "points": {"probability_mass": [{"value": 20, "probability": 1-p_over}, {"value": 21, "probability": p_over}]},
            "rebounds": {"probability_mass": [{"value": 10, "probability": .4}, {"value": 11, "probability": .6}]},
            "assists": {"probability_mass": [{"value": 4, "probability": .4}, {"value": 5, "probability": .6}]},
            "points_rebounds_assists": {"probability_mass": [{"value": 39, "probability": .4}, {"value": 40, "probability": .6}]},
        },
    }
    surface = dict(result); surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def _payload(provider: str, line: float = 20.5, over: int = -110, under: int = -110) -> dict:
    return {
        "provider": provider,
        "price_format": "american",
        "records": [{
            "game_id": GAME_ID,
            "player_id": PLAYER_ID,
            "player_name": "Certification Player",
            "sportsbook": provider,
            "stat": "points",
            "line": line,
            "over_price": over,
            "under_price": under,
            "market_captured_at": "2026-08-28T06:19:45+00:00",
        }],
    }


def _bridge(provider: str, line: float = 20.5, over: int = -110, under: int = -110) -> dict:
    payload = _payload(provider, line, over, under)
    guards = {
        "sportsbook_network_fetch_performed": True,
        "official_wnba_network_fetch_performed": True,
        "sportsbook_http_methods": ["GET"],
        "authentication_used": False,
        "cookies_used": False,
        "wager_action_performed": False,
        "paid_odds_vendor_used": False,
        "basketball_projection_changed": False,
        "step8_distribution_changed": False,
        "step9_called": False,
        "vig_removed": False,
        "edge_calculated": False,
        "expected_value_calculated": False,
        "supabase_mutated": False,
        "persistence_mutated": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "production_activation_allowed": False,
    }
    if provider == dk.PROVIDER:
        result = {
            "data_type": "wnba_step11a_draftkings_provider_bridge",
            "schema_version": dk.SCHEMA_VERSION,
            "model_version": dk.MODEL_VERSION,
            "release_id": dk.RELEASE_ID,
            "generated_at_utc": "2026-08-28T06:19:46+00:00",
            "provider": provider,
            "provider_refresh": {"provider": provider, "adapter_type": dk.ADAPTER_TYPE, "attempts": [{"ok": True, "payload": payload}]},
            "lineage": {
                "step10_frozen_git_sha": s11d.STEP10_FROZEN_HEAD_SHA,
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
            "guardrails": guards,
        }
    else:
        result = {
            "data_type": "wnba_step11c_fanduel_provider_bridge",
            "schema_version": fd.SCHEMA_VERSION,
            "model_version": fd.MODEL_VERSION,
            "release_id": fd.RELEASE_ID,
            "generated_at_utc": "2026-08-28T06:19:47+00:00",
            "provider": provider,
            "provider_refresh": {"provider": provider, "adapter_type": fd.ADAPTER_TYPE, "attempts": [{"ok": True, "payload": payload}]},
            "lineage": {
                "step11b_frozen_git_sha": s11d.STEP11B_FROZEN_HEAD_SHA,
                "step11a_frozen_git_sha": s11d.STEP11A_FROZEN_HEAD_SHA,
                "step10_frozen_git_sha": s11d.STEP10_FROZEN_HEAD_SHA,
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
            "guardrails": guards,
        }
    surface = dict(result); surface.pop("generated_at_utc", None)
    result["provider_bridge_content_sha256"] = s11d._canonical_hash(surface)
    return result


def _fetcher(provider: str, line: float = 20.5, over: int = -110, under: int = -110):
    bridge = _bridge(provider, line, over, under)
    def fetcher(**kwargs):
        return deepcopy(bridge)
    return fetcher


def _run(**overrides):
    kwargs = {
        "season": 2026,
        "slate_date": "2026-08-28",
        "step8_distributions": [_step8_result()],
        "evaluated_at": EVALUATED,
        "provider_attempts": 3,
        "draftkings_fetcher": _fetcher(dk.PROVIDER, 20.5, -105, -115),
        "fanduel_fetcher": _fetcher(fd.PROVIDER),
        "env": _env(),
    }
    kwargs.update(overrides)
    return s11d.run_step11d_multibook_shadow_board(**kwargs)


class Step11MultiBookShadowBoardTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(s11d.step11d_multibook_shadow_enabled({}))

    def test_production_switch_fails_closed(self):
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowDisabledError):
            _run(env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true"))

    def test_scheduler_switch_fails_closed(self):
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowDisabledError):
            _run(env=_env(WNBA_BOARD_SCHEDULER_ENABLED="true"))

    def test_underlying_frozen_gate_is_required(self):
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowDisabledError):
            _run(env=_env(WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED="false"))

    def test_happy_path_builds_true_two_book_qualified_shadow_card(self):
        result = _run()
        self.assertTrue(result["shadow_only"])
        self.assertEqual(result["sportsbooks"], ["DraftKings", "FanDuel"])
        self.assertEqual(result["shadow_summary"]["successful_provider_count"], 2)
        self.assertEqual(result["shadow_summary"]["eligible_market_record_count"], 2)
        self.assertEqual(result["shadow_summary"]["exact_line_multibook_group_count"], 1)
        self.assertEqual(result["shadow_summary"]["qualified_prop_count"], 1)
        self.assertEqual(result["shadow_summary"]["top_card_count"], 1)

    def test_different_lines_never_create_fake_consensus(self):
        result = _run(fanduel_fetcher=_fetcher(fd.PROVIDER, 21.5))
        self.assertEqual(result["market_audit"]["exact_line_multibook_group_count"], 0)
        self.assertFalse(result["market_audit"]["different_lines_blended"])
        self.assertEqual(result["shadow_summary"]["qualified_prop_count"], 0)
        self.assertEqual(result["shadow_summary"]["top_card_count"], 0)

    def test_minimum_books_cannot_be_lowered_below_two(self):
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowInputError):
            _run(qualification_policy={"minimum_books_at_line": 1})

    def test_both_current_providers_are_required(self):
        def fail(**kwargs):
            raise fd.WNBAStep11FanDuelProviderUpstreamError("temporary")
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowNotReadyError):
            _run(fanduel_fetcher=fail, provider_attempts=2)

    def test_retryable_failure_then_success_is_bounded_without_sleep(self):
        calls = {"count": 0}; success = _bridge(fd.PROVIDER)
        def flaky(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise fd.WNBAStep11FanDuelProviderUpstreamError("503")
            return deepcopy(success)
        result = _run(fanduel_fetcher=flaky)
        status = next(row for row in result["providers"] if row["provider"] == "FanDuel")
        self.assertEqual(status["attempts_executed"], 2)
        self.assertEqual(status["retryable_failures"], 1)
        self.assertTrue(status["succeeded"])

    def test_terminal_identity_error_is_not_hidden_as_outage(self):
        def fail(**kwargs):
            raise fd.WNBAStep11FanDuelProviderIdentityError("ambiguous")
        with self.assertRaises(fd.WNBAStep11FanDuelProviderIdentityError):
            _run(fanduel_fetcher=fail)

    def test_provider_attempt_limit_is_bounded(self):
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowInputError):
            _run(provider_attempts=6)

    def test_tampered_draftkings_bridge_hash_is_rejected(self):
        bad = _bridge(dk.PROVIDER)
        bad["provider_refresh"]["attempts"][0]["payload"]["records"][0]["over_price"] = 999
        def fetcher(**kwargs): return deepcopy(bad)
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowIntegrityError):
            _run(draftkings_fetcher=fetcher)

    def test_wrong_fanduel_release_is_rejected(self):
        bad = _bridge(fd.PROVIDER); bad["release_id"] = "wrong"
        surface = dict(bad); surface.pop("generated_at_utc", None); surface.pop("provider_bridge_content_sha256", None)
        bad["provider_bridge_content_sha256"] = s11d._canonical_hash(surface)
        def fetcher(**kwargs): return deepcopy(bad)
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowIntegrityError):
            _run(fanduel_fetcher=fetcher)

    def test_provider_order_is_deterministic(self):
        result = _run()
        self.assertEqual([row["provider"] for row in result["providers"]], ["DraftKings", "FanDuel"])

    def test_exact_line_audit_lists_both_books(self):
        group = _run()["market_audit"]["exact_line_multibook_groups"][0]
        self.assertEqual(group["line"], 20.5)
        self.assertEqual(group["sportsbooks"], ["DraftKings", "FanDuel"])

    def test_shadow_guardrails_allow_analysis_but_no_writes_or_activation(self):
        guards = _run()["guardrails"]
        self.assertTrue(guards["sportsbook_network_fetch_performed"])
        self.assertTrue(guards["exact_line_consensus_required"])
        self.assertTrue(guards["vig_removed_in_frozen_step9"])
        self.assertTrue(guards["edge_calculated_in_frozen_step9"])
        for key in ("wager_action_performed", "different_lines_blended", "supabase_mutated", "persistence_mutated", "scheduler_started", "production_runtime_enabled", "production_activation_allowed", "public_fastapi_route_added"):
            self.assertFalse(guards[key], key)

    def test_no_step11d_public_route_was_added(self):
        forbidden = "/api/v1/wnba/props/multibook-shadow-board"
        self.assertNotIn(forbidden, app.openapi()["paths"])

    def test_frozen_pipeline_and_ranking_hashes_are_exposed(self):
        result = _run()
        self.assertTrue(result["lineage"]["step10_pipeline_content_sha256"])
        self.assertTrue(result["lineage"]["step10c_snapshot_content_sha256"])
        self.assertTrue(result["lineage"]["step9_ranking_content_sha256"])
        self.assertTrue(result["shadow_board_content_sha256"])

    def test_tampered_step8_distribution_fails_frozen_step9_integrity(self):
        distribution = _step8_result(); distribution["distributions"]["points"]["probability_mass"][0]["probability"] = .1
        with self.assertRaises(Exception):
            _run(step8_distributions=[distribution])

    def test_only_2026_regular_season_is_certified(self):
        with self.assertRaises(s11d.WNBAStep11MultiBookShadowInputError):
            _run(season=2025)


if __name__ == "__main__":
    unittest.main(verbosity=2)
