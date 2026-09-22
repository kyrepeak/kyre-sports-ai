from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step13a_bounded_scheduler as scheduler
from sports_api import wnba_step19a_draftkings_sportscontent as step19a
from sports_api import wnba_step19a_step17b_bridge as bridge
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

AT = datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
SLATE = "2026-08-28"
GAME_ID = "1022600291"
PLAYER_ID = 1642301


def _env() -> dict[str, str]:
    return {
        scheduler.STEP13A_BOUNDED_SCHEDULER_ENABLED_ENV: "true",
        "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED": "true",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
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
        step19a.STEP19A_ENABLED_ENV: "true",
        step19a.STEP19A_SITE_ENV: "dkusaz",
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


def _record() -> dict:
    return {
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "player_name": "Scheduler Path Player",
        "stat": "points",
        "line": 20.5,
        "over_price": -110,
        "under_price": -110,
        "market_captured_at": AT.isoformat(),
    }


def _provider_bridge(provider: str) -> dict:
    payload = {
        "provider": provider,
        "price_format": "american",
        "records": [{**_record(), "sportsbook": provider}],
    }
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
            "generated_at_utc": AT.isoformat(),
            "slate_date": SLATE,
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": dk.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step10_frozen_git_sha": step11d.STEP10_FROZEN_HEAD_SHA,
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
            "generated_at_utc": AT.isoformat(),
            "slate_date": SLATE,
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": fd.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step11b_frozen_git_sha": step11d.STEP11B_FROZEN_HEAD_SHA,
                "step11a_frozen_git_sha": step11d.STEP11A_FROZEN_HEAD_SHA,
                "step10_frozen_git_sha": step11d.STEP10_FROZEN_HEAD_SHA,
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
            "guardrails": guards,
        }
    surface = {
        key: value
        for key, value in result.items()
        if key not in {"generated_at_utc", "provider_bridge_content_sha256"}
    }
    result["provider_bridge_content_sha256"] = step11d._canonical_hash(surface)
    return result


def _distribution() -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": AT.isoformat(),
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": "scheduler-team",
        "opponent_team_key": "scheduler-opponent",
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


def test_real_bounded_scheduler_path_resolves_step11d_default_draftkings_to_step19a() -> None:
    """Regression: scheduler -> Step12 -> Step11E -> Step11D must resolve Step19A."""
    assert dk.fetch_step11a_draftkings_provider_bridge is bridge.fetch_step11a_draftkings_provider_bridge_step19a

    calls: list[dict] = []
    frozen_result = _provider_bridge(dk.PROVIDER)
    fanduel_result = _provider_bridge(fd.PROVIDER)

    def frozen_step11a_stub(**kwargs):
        calls.append(dict(kwargs))
        assert kwargs["season"] == 2026
        assert kwargs["slate_date"] == SLATE
        # Step19A must inject its current SportsContent requester into the frozen
        # Step11A parser while leaving the frozen parser/source itself unchanged.
        assert callable(kwargs.get("requester"))
        return deepcopy(frozen_result)

    def fanduel_fetcher(**_kwargs):
        return deepcopy(fanduel_result)

    request = scheduler.build_step13a_request(
        season=2026,
        slate_date=SLATE,
        max_cycles=1,
        max_total_sleep_seconds=0,
    )

    with patch.object(bridge, "_ORIGINAL_STEP11A_FETCHER", frozen_step11a_stub):
        result = scheduler.run_step13a_bounded_scheduler(
            request,
            env=_env(),
            clock=lambda: AT,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("one-cycle regression must not sleep")),
            fanduel_fetcher=fanduel_fetcher,
            projection_loader=lambda **_kwargs: _distribution(),
        )

    assert calls, "The bounded scheduler never reached the Step19A DraftKings compatibility bridge."
    assert result["status"] == "completed"
    assert result["scheduler_summary"]["executed_ticks"] == 1
    assert result["latest_runtime"]["cycle_executed"] is True
    assert result["latest_board"]["available"] is True
    assert result["latest_board"]["top_card_count"] >= 1

    environment = _env()
    for key in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_PERSISTENCE_ENABLED",
        "WNBA_SUPABASE_WRITE_ENABLED",
        "WNBA_WAGERING_ENABLED",
    ):
        assert environment[key] == "false"
