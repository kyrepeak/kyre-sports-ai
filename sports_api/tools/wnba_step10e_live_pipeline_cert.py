"""Offline certification for the frozen WNBA Step 10E full live pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step10_release_freeze as release
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step10_live_pipeline import build_step10e_live_market_board
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

UTC = timezone.utc
BRANCH = "wnba-step10e-live-pipeline-20260828"
CERT_MARKER = "STEP10_FULL_LIVE_MARKET_BOARD_RELEASE_FROZEN_CERTIFIED"
OUTPUT_PATH = Path("step10e-live-pipeline-cert.json")


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


def _step8(player_id: int, p_over: float) -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T05:34:00+00:00",
        "game_id": "1022600291",
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
            "rebounds": {"probability_mass": [{"value": 10, "probability": 0.4}, {"value": 11, "probability": 0.6}]},
            "assists": {"probability_mass": [{"value": 4, "probability": 0.4}, {"value": 5, "probability": 0.6}]},
            "points_rebounds_assists": {"probability_mass": [{"value": 39, "probability": 0.4}, {"value": 40, "probability": 0.6}]},
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def _provider_payload(provider: str, sportsbook: str, captured: str, players: list[int], *, over: int, under: int) -> dict:
    return {
        "provider": provider,
        "price_format": "american",
        "records": [
            {
                "game_id": "1022600291",
                "player_id": player_id,
                "player_name": f"Certification Player {player_id}",
                "sportsbook": sportsbook,
                "stat": "points",
                "line": 20.5,
                "over_price": over,
                "under_price": under,
                "market_captured_at": captured,
            }
            for player_id in players
        ],
    }


def main() -> None:
    evaluated = datetime(2026, 8, 28, 5, 35, 0, tzinfo=UTC)
    players = [1642301, 1642302, 1642303, 1642304]
    distributions = [
        _step8(1642301, 0.68),
        _step8(1642302, 0.66),
        _step8(1642303, 0.62),
        _step8(1642304, 0.64),
    ]
    provider_refreshes = [
        {
            "provider": "Certification Provider A",
            "adapter_type": "flat_two_way_v1",
            "attempts": [{
                "ok": True,
                "payload": _provider_payload(
                    "Certification Provider A", "Certification Book A",
                    "2026-08-28T05:34:30+00:00", players, over=-110, under=-110,
                ),
            }],
        },
        {
            "provider": "Certification Provider B",
            "adapter_type": "flat_two_way_v1",
            "attempts": [{
                "ok": True,
                "payload": _provider_payload(
                    "Certification Provider B", "Certification Book B",
                    "2026-08-28T05:34:40+00:00", players, over=-105, under=-115,
                ),
            }],
        },
    ]

    result = build_step10e_live_market_board(
        provider_refreshes=provider_refreshes,
        step8_distributions=distributions,
        expected_sportsbooks=["Certification Book A", "Certification Book B"],
        qualification_policy={"top_n": 5},
        evaluated_at=evaluated,
        cycle_started_at=datetime(2026, 8, 28, 5, 34, 50, tzinfo=UTC),
        env=_env(),
    )

    assert result["refresh_cycle"]["status"] == "ready"
    assert result["refresh_cycle"]["snapshot_source"] == "current_refresh"
    assert result["refresh_cycle"]["market_snapshot"]["snapshot"]["eligible_record_count"] == 8
    assert result["pipeline"]["matched_prop_count"] == 4
    assert result["board"]["qualification_summary"]["qualified_prop_count"] == 4
    assert result["board"]["qualification_summary"]["top_card_count"] == 4
    assert result["board"]["top_cards"]["requested_top_n"] == 5
    assert result["board"]["top_cards"]["not_forced"] is True
    ranked_players = [row["player_id"] for row in result["board"]["top_cards"]["primary"]]
    assert ranked_players == [1642301, 1642302, 1642304, 1642303], ranked_players

    guards = result["guardrails"]
    for key in (
        "sportsbook_network_fetch_performed", "retry_sleep_performed",
        "basketball_projection_changed", "step8_distribution_changed",
        "supabase_mutated", "persistence_mutated", "scheduler_started",
        "production_runtime_enabled", "production_activation_allowed",
    ):
        assert guards[key] is False, key
    for key in (
        "market_snapshot_reconciled", "step9_called_after_market_reconciliation",
        "vig_removed", "edge_calculated", "expected_value_calculated",
        "cross_sportsbook_consensus_calculated", "cross_prop_ranking_calculated",
    ):
        assert guards[key] is True, key

    evidence = {
        "data_type": "wnba_step10e_live_pipeline_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "release_id": release.RELEASE_ID,
        "integration_version": release.INTEGRATION_VERSION,
        "endpoint_path": release.ENDPOINT_PATH,
        "frozen_lineage": {
            "step8": release.STEP8_FROZEN_SHA,
            "step9": release.STEP9_FROZEN_SHA,
            "step10a": release.STEP10A_FROZEN_SHA,
            "step10b": release.STEP10B_FROZEN_SHA,
            "step10c": release.STEP10C_FROZEN_SHA,
            "step10d": release.STEP10D_FROZEN_SHA,
        },
        "certified_pipeline": {
            "order": result["pipeline"]["order"],
            "refresh_status": result["refresh_cycle"]["status"],
            "snapshot_source": result["refresh_cycle"]["snapshot_source"],
            "eligible_market_records": result["refresh_cycle"]["market_snapshot"]["snapshot"]["eligible_record_count"],
            "matched_prop_count": result["pipeline"]["matched_prop_count"],
            "qualified_prop_count": result["board"]["qualification_summary"]["qualified_prop_count"],
            "requested_top_n": result["board"]["top_cards"]["requested_top_n"],
            "returned_top_cards": result["board"]["qualification_summary"]["top_card_count"],
            "not_forced": result["board"]["top_cards"]["not_forced"],
            "ranked_player_ids": ranked_players,
            "ranking_content_sha256": result["board"]["ranking_content_sha256"],
            "pipeline_content_sha256": result["pipeline_content_sha256"],
            "refresh_cycle_content_sha256": result["refresh_cycle"]["refresh_cycle_content_sha256"],
            "step10c_snapshot_content_sha256": result["refresh_cycle"]["market_snapshot"]["snapshot_content_sha256"],
        },
        "safety": guards,
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
