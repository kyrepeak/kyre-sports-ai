from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step12c_live_board_runtime as step12c


STEP8_HASH = "1" * 64
STEP9A_HASH = "2" * 64
STEP9B_HASH = "3" * 64
STEP9C_HASH = "4" * 64
STEP9D_HASH = "5" * 64
STEP10_HASH = "6" * 64
STATE_HASH = "7" * 64


def _env() -> dict[str, str]:
    return {
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


def _candidate() -> dict:
    return {
        "candidate_id": "1022600291:1642301:points:over:20.500000:draftkings",
        "prop_key": "1022600291:1642301:points",
        "player_game_key": "1022600291:1642301",
        "game_id": "1022600291",
        "player_id": 1642301,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "stat": "points",
        "side": "over",
        "line": 20.5,
        "sportsbook": "DraftKings",
        "american_odds": -110,
        "decimal_odds": 1.90909091,
        "model_probability": 0.64,
        "model_percentage": 64.0,
        "model_raw_win_probability": 0.64,
        "model_push_probability": 0.0,
        "ev_per_unit": 0.2218181818,
        "ev_roi_percentage": 22.18181818,
        "same_line_market_no_vig_probability": 0.50,
        "same_line_consensus_edge_probability": 0.14,
        "same_line_consensus_edge_percentage_points": 14.0,
        "same_line_book_count": 2,
        "same_line_market_probability_range_percentage_points": 0.0,
        "offer_selection_method": "overall_best_available_with_same_line_consensus",
        "qualified": True,
        "qualification_failures": [],
        "qualification_margin": {
            "model_probability_above_minimum": 0.09,
            "ev_above_minimum": 0.1718181818,
            "consensus_edge_above_minimum": 0.11,
        },
        "lineage": {
            "step9c_consensus_content_sha256": STEP9C_HASH,
            "step8_result_content_sha256": STEP8_HASH,
            "step9b_comparison_content_sha256": STEP9B_HASH,
            "step9a_pricing_content_sha256": STEP9A_HASH,
        },
        "rank": 1,
    }


def _quote(book: str) -> dict:
    return {
        "game_id": "1022600291",
        "player_id": 1642301,
        "player_name": "Allisha Gray",
        "sportsbook": book,
        "stat": "points",
        "line": 20.5,
        "over_odds": -110,
        "under_odds": -110,
        "market_captured_at_utc": "2026-08-28T13:30:00+00:00",
        "quote_id": f"{book}-q",
        "market_age_seconds_at_evaluation": 0.0,
        "source_providers": [book],
        "source_adapter_content_sha256_all": ["8" * 64],
        "superseded_update_count": 0,
        "earliest_seen_capture_utc": "2026-08-28T13:30:00+00:00",
    }


def _parent() -> dict:
    card = _candidate()
    shadow = {
        "pipeline_result": {
            "refresh_cycle": {
                "snapshot_source": "current_refresh",
                "market_snapshot": {
                    "snapshot": {
                        "eligible_record_count": 2,
                        "unique_sportsbooks": ["DraftKings", "FanDuel"],
                        "board_earliest_capture_utc": "2026-08-28T13:30:00+00:00",
                        "board_latest_capture_utc": "2026-08-28T13:30:00+00:00",
                        "board_capture_spread_seconds": 0.0,
                        "board_synchronized": True,
                    },
                    "records": [_quote("DraftKings"), _quote("FanDuel")],
                },
            },
            "board": {
                "qualification_policy": {"top_n_requested": 5},
                "qualification_summary": {
                    "qualified_prop_count": 1,
                    "top_card_count": 1,
                    "full_requested_board_available": False,
                },
                "rankings": {"value": [deepcopy(card)]},
                "top_cards": {
                    "primary": [deepcopy(card)],
                    "selection_method": "frozen_pure_probability_after_qualification",
                },
            },
        },
        "lineage": {
            "step10_pipeline_content_sha256": STEP10_HASH,
            "step9_ranking_content_sha256": STEP9D_HASH,
        },
    }
    tick = {
        "evaluated_at_utc": "2026-08-28T13:30:00+00:00",
        "status": "healthy",
        "health": "healthy",
        "execution": {
            "cycle_due": True,
            "cycle_executed": True,
            "cycle_outcome": "shadow_board_ready",
            "skip_reason": None,
        },
        "circuit_breaker": {
            "state_after": "closed",
            "consecutive_failures_after": 0,
        },
        "automation_state": {
            "next_refresh_due_at_utc": "2026-08-28T13:31:00+00:00",
            "circuit_open_until_utc": None,
            "state_content_sha256": STATE_HASH,
        },
        "shadow_board_result": shadow,
    }
    result = {
        "data_type": "wnba_step12b_live_runtime_assembly_response",
        "schema_version": step12b.SCHEMA_VERSION,
        "source": step12b.SOURCE,
        "model_version": step12b.MODEL_VERSION,
        "generated_at_utc": "2026-08-28T13:30:01+00:00",
        "request_content_sha256": "9" * 64,
        "status": "healthy",
        "health": "healthy",
        "slate_date": "2026-08-28",
        "provider_discovery": {
            "sportsbooks": ["DraftKings", "FanDuel"],
            "sportsbook_network_fetches_reused_in_step11_tick": True,
        },
        "market_overlap": {
            "exact_line_multibook_group_count": 1,
            "different_lines_blended": False,
        },
        "projection_assembly": {
            "requested_target_count": 1,
            "built_target_count": 1,
            "skipped_target_count": 0,
            "simulations_per_built_target": 5_000_000,
            "batch_size": 250_000,
            "targets": [
                {
                    "game_id": "1022600291",
                    "player_id": 1642301,
                    "result_content_sha256": STEP8_HASH,
                    "simulations": 5_000_000,
                    "converged": True,
                }
            ],
            "skipped_targets": [],
            "all_built_distributions_converged": True,
        },
        "runtime_summary": {
            "step8_distribution_count": 1,
            "step11_cycle_executed": True,
            "qualified_prop_count": 1,
            "top_card_count": 1,
        },
        "step12a_result": {"step11e_tick": tick},
        "lineage": {
            "step12a_frozen_sha": step12b.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": step12b.STEP11E_FROZEN_SHA,
            "step8_frozen_sha": step12b.STEP8_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "caller_driven_job_only": True,
            "market_driven_projection_target_discovery": True,
            "official_wnba_identity_reconciliation_required": True,
            "exact_line_multibook_overlap_required": True,
            "frozen_step8_projection_generated": True,
            "five_million_simulations_required": True,
            "sportsbook_network_fetch_performed": True,
            "sportsbook_http_methods": ["GET"],
            "sportsbook_discovery_reused_without_second_network_fetch": True,
            "scheduler_started": False,
            "background_worker_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "caller_resupplies_state": True,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_model_modified": False,
            "step8_distribution_modified_after_generation": False,
        },
    }
    result["runtime_content_sha256"] = step12c._canonical_hash(
        step12c._step12b_hash_surface(result)
    )
    return result


def main() -> None:
    calls = []

    def parent_runner(parent_request, **kwargs):
        calls.append({
            "data_type": parent_request.get("data_type"),
            "schema_version": parent_request.get("schema_version"),
            "slate_date": parent_request.get("slate_date"),
        })
        return deepcopy(_parent())

    req = step12c.build_step12c_request(
        season=2026,
        slate_date="2026-08-28",
        evaluated_at="2026-08-28T13:30:00+00:00",
    )
    result = step12c.run_step12c_live_board_job(
        req,
        env=_env(),
        step12b_runner=parent_runner,
    )
    card = result["board"]["primary_top_cards"][0]
    assert len(calls) == 1
    assert result["board"]["available"] is True
    assert result["board"]["top_card_count"] == 1
    assert card["player"]["player_name"] == "Allisha Gray"
    assert card["prop"]["pick"] == "OVER 20.5"
    assert card["market"]["sportsbook"] == "DraftKings"
    assert card["market"]["american_odds"] == -110
    assert card["model"]["simulations"] == 5_000_000
    assert card["model"]["converged"] is True
    assert card["model"]["resolved_fair_percentage"] == 64.0
    assert card["model"]["fair_price"]["american_odds"] == -178
    assert card["consensus"]["no_vig_percentage"] == 50.0
    assert card["consensus"]["edge_percentage_points"] == 14.0
    assert result["runtime"]["snapshot_source"] == "current_refresh"
    assert result["runtime"]["circuit_state"] == "closed"
    assert result["controller_state_for_next_caller_tick"]["state_content_sha256"] == STATE_HASH
    assert result["lineage"]["step12b_frozen_sha"] == step12c.STEP12B_FROZEN_SHA
    assert result["guardrails"]["presentation_layer_only"] is True
    assert result["guardrails"]["frozen_step9_ranking_order_preserved"] is True
    assert result["guardrails"]["state_persisted"] is False
    assert result["guardrails"]["scheduler_started"] is False
    assert result["guardrails"]["public_fastapi_route_added"] is False
    assert result["guardrails"]["production_runtime_enabled"] is False
    assert result["guardrails"]["wager_action_performed"] is False

    evidence = {
        "data_type": "wnba_step12c_live_board_runtime_certification",
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "step12b_frozen_sha": step12c.STEP12B_FROZEN_SHA,
        "schema_version": result["schema_version"],
        "request_content_sha256": result["request_content_sha256"],
        "board_content_sha256": result["board_content_sha256"],
        "status": result["status"],
        "health": result["health"],
        "runtime": result["runtime"],
        "board_summary": {
            "available": result["board"]["available"],
            "requested_top_card_count": result["board"]["requested_top_card_count"],
            "qualified_prop_count": result["board"]["qualified_prop_count"],
            "top_card_count": result["board"]["top_card_count"],
            "primary_card": card,
        },
        "parent_calls": calls,
        "lineage": result["lineage"],
        "guardrails": result["guardrails"],
    }
    Path("step12c-live-board-runtime-cert.json").write_text(
        json.dumps(evidence, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("STEP12C_LIVE_BOARD_RUNTIME_OK")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
