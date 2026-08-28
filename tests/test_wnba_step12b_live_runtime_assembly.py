from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step8_projection_handoff as step8a
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)


def env() -> dict[str, str]:
    return {
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
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
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED": "true",
        "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED": "true",
        "WNBA_STEP8_MONTE_CARLO_ENABLED": "true",
        "WNBA_STEP7G_FIRST_PARTY_ENABLED": "true",
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


def record(
    player_id: int = 1642301,
    *,
    stat: str = "points",
    line: float = 20.5,
    evaluated: datetime | None = None,
) -> dict:
    at = evaluated or datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
    return {
        "game_id": "1022600291",
        "player_id": player_id,
        "player_name": f"Player {player_id}",
        "stat": stat,
        "line": line,
        "over_price": -110,
        "under_price": -110,
        "market_captured_at": at.isoformat(),
    }


def bridge(provider: str, records: list[dict], evaluated: datetime | None = None) -> dict:
    at = evaluated or datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
    payload = {
        "provider": provider,
        "price_format": "american",
        "records": [{**row, "sportsbook": provider} for row in records],
    }
    if provider == dk.PROVIDER:
        result = {
            "data_type": "wnba_step11a_draftkings_provider_bridge",
            "schema_version": dk.SCHEMA_VERSION,
            "model_version": dk.MODEL_VERSION,
            "release_id": dk.RELEASE_ID,
            "generated_at_utc": at.isoformat(),
            "slate_date": "2026-08-28",
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": dk.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step10_frozen_git_sha": release.STEP10_FROZEN_SHA,
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
        }
    else:
        result = {
            "data_type": "wnba_step11c_fanduel_provider_bridge",
            "schema_version": fd.SCHEMA_VERSION,
            "model_version": fd.MODEL_VERSION,
            "release_id": fd.RELEASE_ID,
            "generated_at_utc": at.isoformat(),
            "slate_date": "2026-08-28",
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
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
        }
    result["guardrails"] = {
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
    surface = {key: value for key, value in result.items() if key != "generated_at_utc"}
    result["provider_bridge_content_sha256"] = step11d._canonical_hash(surface)
    return result


def distribution(player_id: int = 1642301) -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T13:30:00+00:00",
        "game_id": "1022600291",
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {
            "simulations": step12b.CERTIFIED_SIMULATIONS,
            "batch_size": step12b.CERTIFIED_BATCH_SIZE,
        },
        "convergence": {"converged": True},
        "distributions": {
            "points": {
                "probability_mass": [
                    {"value": 20, "probability": 0.36},
                    {"value": 21, "probability": 0.64},
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
    surface = {key: value for key, value in result.items() if key != "generated_at_utc"}
    result["result_content_sha256"] = step12b._canonical_hash(surface)
    return result


def request() -> dict:
    return step12b.build_step12b_request(
        season=2026,
        slate_date="2026-08-28",
        evaluated_at="2026-08-28T13:30:00+00:00",
    )


def fetcher_for(value: dict, calls: list | None = None):
    def fetcher(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return deepcopy(value)

    return fetcher


class Tests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
        self.dk = bridge(dk.PROVIDER, [record(evaluated=self.at)], self.at)
        self.fd = bridge(fd.PROVIDER, [record(evaluated=self.at)], self.at)

    def test_default_off_and_frozen_parent(self):
        self.assertFalse(step12b.step12b_live_runtime_assembly_enabled({}))
        self.assertEqual(
            step12b.STEP12A_FROZEN_SHA,
            "4523abb8b230e8e29d9f9d298232dfb8948fc883",
        )
        self.assertEqual(step12b.CERTIFIED_SIMULATIONS, 5_000_000)

    def test_requires_all_isolated_gates(self):
        e = env()
        e["WNBA_STEP8_MONTE_CARLO_ENABLED"] = "false"
        with self.assertRaises(step12b.WNBAStep12LiveRuntimeDisabledError):
            step12b.run_step12b_live_runtime_job(
                request(),
                env=e,
                draftkings_fetcher=fetcher_for(self.dk),
                fanduel_fetcher=fetcher_for(self.fd),
                projection_loader=lambda **_: distribution(),
            )

    def test_refuses_external_activation_switches(self):
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
                step12b.WNBAStep12LiveRuntimeDisabledError,
                msg=key,
            ):
                step12b.run_step12b_live_runtime_job(
                    request(),
                    env=e,
                    draftkings_fetcher=fetcher_for(self.dk),
                    fanduel_fetcher=fetcher_for(self.fd),
                    projection_loader=lambda **_: distribution(),
                )

    def test_request_hash_is_tamper_evident(self):
        bad = deepcopy(request())
        bad["slate_date"] = "2026-08-29"
        with self.assertRaises(step12b.WNBAStep12LiveRuntimeIntegrityError):
            step12b.run_step12b_live_runtime_job(
                bad,
                env=env(),
                draftkings_fetcher=fetcher_for(self.dk),
                fanduel_fetcher=fetcher_for(self.fd),
                projection_loader=lambda **_: distribution(),
            )

    def test_exact_line_overlap_drives_projection_targets(self):
        dk_records = [
            record(1642301, stat="points", line=20.5),
            record(1642302, stat="rebounds", line=8.5),
        ]
        fd_records = [
            record(1642301, stat="points", line=20.5),
            record(1642302, stat="rebounds", line=9.5),
        ]
        targets, groups = step12b._exact_multibook_targets(dk_records, fd_records)
        self.assertEqual(targets, [("1022600291", 1642301)])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["line"], 20.5)

    def test_provider_discovery_retry_is_bounded_without_sleep(self):
        calls = []

        def flaky(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise dk.WNBAStep11DraftKingsProviderUpstreamError("temporary")
            return deepcopy(self.dk)

        found, audit = step12b._fetch_provider_bridge(
            provider=dk.PROVIDER,
            fetcher=flaky,
            season=2026,
            slate_date="2026-08-28",
            evaluated_at=self.at,
            attempts=2,
            requester=None,
            roster_loader=None,
            env=env(),
        )
        self.assertEqual(found["provider"], dk.PROVIDER)
        self.assertEqual(len(calls), 2)
        self.assertEqual(audit["retryable_failures"], 1)
        self.assertEqual(audit["attempts_executed"], 2)

    def test_tampered_step8_distribution_is_rejected(self):
        bad = distribution()
        bad["distributions"]["points"]["probability_mass"][1]["probability"] = 0.63
        with self.assertRaises(step12b.WNBAStep12LiveRuntimeIntegrityError):
            step12b._verify_step8_distribution(
                bad,
                game_id="1022600291",
                player_id=1642301,
            )

    def test_candidate_not_ready_is_skipped_without_killing_good_target(self):
        records = [record(1642301), record(1642302, line=18.5)]
        dk_bridge = bridge(dk.PROVIDER, records, self.at)
        fd_bridge = bridge(fd.PROVIDER, records, self.at)

        def loader(**kwargs):
            if kwargs["player_id"] == 1642302:
                raise step8a.WNBAStep8ProjectionHandoffNotReadyError("not ready")
            return distribution(kwargs["player_id"])

        result = step12b.run_step12b_live_runtime_job(
            request(),
            env=env(),
            draftkings_fetcher=fetcher_for(dk_bridge),
            fanduel_fetcher=fetcher_for(fd_bridge),
            projection_loader=loader,
        )
        self.assertEqual(result["projection_assembly"]["requested_target_count"], 2)
        self.assertEqual(result["projection_assembly"]["built_target_count"], 1)
        self.assertEqual(result["projection_assembly"]["skipped_target_count"], 1)
        self.assertEqual(result["status"], "healthy")

    def test_full_frozen_runtime_reuses_each_provider_bridge_once(self):
        dk_calls = []
        fd_calls = []
        projection_calls = []

        def loader(**kwargs):
            projection_calls.append(kwargs)
            return distribution(kwargs["player_id"])

        result = step12b.run_step12b_live_runtime_job(
            request(),
            env=env(),
            draftkings_fetcher=fetcher_for(self.dk, dk_calls),
            fanduel_fetcher=fetcher_for(self.fd, fd_calls),
            projection_loader=loader,
        )
        self.assertEqual(len(dk_calls), 1)
        self.assertEqual(len(fd_calls), 1)
        self.assertEqual(len(projection_calls), 1)
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["runtime_summary"]["step8_distribution_count"], 1)
        self.assertEqual(result["runtime_summary"]["qualified_prop_count"], 1)
        self.assertTrue(
            result["provider_discovery"]["sportsbook_network_fetches_reused_in_step11_tick"]
        )
        for key in (
            "scheduler_started",
            "background_worker_started",
            "sleep_performed",
            "state_persisted",
            "public_fastapi_route_added",
            "supabase_mutated",
            "persistence_mutated",
            "production_runtime_enabled",
            "production_activation_allowed",
            "wager_action_performed",
            "authentication_used",
            "cookies_used",
            "paid_odds_vendor_used",
            "basketball_model_modified",
            "step8_distribution_modified_after_generation",
        ):
            self.assertFalse(result["guardrails"][key], key)

    def test_unknown_request_field_fails_closed(self):
        bad = request()
        bad.pop("request_content_sha256")
        bad["surprise"] = True
        with self.assertRaises(step12b.WNBAStep12LiveRuntimeInputError):
            step12b.run_step12b_live_runtime_job(
                bad,
                env=env(),
                draftkings_fetcher=fetcher_for(self.dk),
                fanduel_fetcher=fetcher_for(self.fd),
                projection_loader=lambda **_: distribution(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
