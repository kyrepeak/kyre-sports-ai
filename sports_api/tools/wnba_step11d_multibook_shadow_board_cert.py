"""Offline deterministic certification for WNBA Step 11D multi-book shadow board."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step11_multibook_shadow_board as s11d
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

UTC = timezone.utc
BRANCH = "wnba-step11d-multibook-shadow-board-20260828"
CERT_MARKER = "STEP11D_MULTIBOOK_LIVE_SHADOW_BOARD_CERTIFIED"
OUTPUT_PATH = Path("step11d-multibook-shadow-board-cert.json")
GAME_ID = "1022600291"
EVALUATED = datetime(2026, 8, 28, 6, 20, 0, tzinfo=UTC)

PROPS = (
    (1642301, "points", 20.5, 0.64),
    (1642302, "rebounds", 10.5, 0.61),
    (1642303, "assists", 4.5, 0.58),
    (1642304, "pra", 39.5, 0.60),
)


def _env() -> dict[str, str]:
    return {
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


def _distribution(player_id: int, target_stat: str, p_over: float) -> dict:
    probs = {
        "points": 0.57,
        "rebounds": 0.57,
        "assists": 0.57,
        "pra": 0.57,
    }
    probs[target_stat] = p_over
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T06:18:00+00:00",
        "game_id": GAME_ID,
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {"converged": True},
        "distributions": {
            "points": {"probability_mass": [
                {"value": 20, "probability": 1.0 - probs["points"]},
                {"value": 21, "probability": probs["points"]},
            ]},
            "rebounds": {"probability_mass": [
                {"value": 10, "probability": 1.0 - probs["rebounds"]},
                {"value": 11, "probability": probs["rebounds"]},
            ]},
            "assists": {"probability_mass": [
                {"value": 4, "probability": 1.0 - probs["assists"]},
                {"value": 5, "probability": probs["assists"]},
            ]},
            "points_rebounds_assists": {"probability_mass": [
                {"value": 39, "probability": 1.0 - probs["pra"]},
                {"value": 40, "probability": probs["pra"]},
            ]},
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def _payload(provider: str, *, shift_points_line: bool = False) -> dict:
    records = []
    for index, (player_id, stat, line, _p_over) in enumerate(PROPS):
        effective_line = line + 1.0 if shift_points_line and stat == "points" else line
        records.append({
            "game_id": GAME_ID,
            "player_id": player_id,
            "player_name": f"Certification Player {player_id}",
            "sportsbook": provider,
            "stat": stat,
            "line": effective_line,
            "over_price": -105 if provider == dk.PROVIDER else -110,
            "under_price": -115 if provider == dk.PROVIDER else -110,
            "market_captured_at": (
                "2026-08-28T06:19:40+00:00" if provider == dk.PROVIDER
                else "2026-08-28T06:19:50+00:00"
            ),
        })
    return {"provider": provider, "price_format": "american", "records": records}


def _bridge(provider: str, *, shift_points_line: bool = False) -> dict:
    payload = _payload(provider, shift_points_line=shift_points_line)
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
            "source": dk.SOURCE,
            "model_version": dk.MODEL_VERSION,
            "release_id": dk.RELEASE_ID,
            "generated_at_utc": "2026-08-28T06:19:51+00:00",
            "slate_date": "2026-08-28",
            "provider": provider,
            "provider_refresh": {"provider": provider, "adapter_type": dk.ADAPTER_TYPE, "attempts": [{"ok": True, "payload": payload}]},
            "lineage": {
                "step10_frozen_git_sha": s11d.STEP10_FROZEN_HEAD_SHA,
                "step10a_frozen_git_sha": "4a8f822684c1d56d1ef062f0db25d5f671409def",
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
            "guardrails": guards,
        }
    else:
        result = {
            "data_type": "wnba_step11c_fanduel_provider_bridge",
            "schema_version": fd.SCHEMA_VERSION,
            "source": fd.SOURCE,
            "model_version": fd.MODEL_VERSION,
            "release_id": fd.RELEASE_ID,
            "generated_at_utc": "2026-08-28T06:19:52+00:00",
            "slate_date": "2026-08-28",
            "provider": provider,
            "provider_refresh": {"provider": provider, "adapter_type": fd.ADAPTER_TYPE, "attempts": [{"ok": True, "payload": payload}]},
            "lineage": {
                "step11b_frozen_git_sha": s11d.STEP11B_FROZEN_HEAD_SHA,
                "step11a_frozen_git_sha": s11d.STEP11A_FROZEN_HEAD_SHA,
                "step10_frozen_git_sha": s11d.STEP10_FROZEN_HEAD_SHA,
                "step10a_frozen_git_sha": "4a8f822684c1d56d1ef062f0db25d5f671409def",
                "step10b_frozen_git_sha": "1088358452ca2bc9e45a2bb3544b44331606d88c",
            },
            "guardrails": guards,
        }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["provider_bridge_content_sha256"] = s11d._canonical_hash(surface)
    return result


def _fetcher(bridge: dict):
    def fetcher(**kwargs):
        return deepcopy(bridge)
    return fetcher


def _run(*, shift_points_line: bool = False) -> dict:
    return s11d.run_step11d_multibook_shadow_board(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=[
            _distribution(player_id, stat, probability)
            for player_id, stat, _line, probability in PROPS
        ],
        evaluated_at=EVALUATED,
        draftkings_fetcher=_fetcher(_bridge(dk.PROVIDER)),
        fanduel_fetcher=_fetcher(_bridge(fd.PROVIDER, shift_points_line=shift_points_line)),
        qualification_policy={"top_n": 5, "minimum_books_at_line": 2},
        env=_env(),
    )


def main() -> None:
    result = _run()
    summary = result["shadow_summary"]
    assert result["shadow_only"] is True
    assert result["sportsbooks"] == ["DraftKings", "FanDuel"]
    assert summary["successful_provider_count"] == 2
    assert summary["eligible_market_record_count"] == 8
    assert summary["matched_prop_count"] == 4
    assert summary["exact_line_multibook_group_count"] == 4
    assert summary["qualified_prop_count"] == 4
    assert summary["requested_top_n"] == 5
    assert summary["top_card_count"] == 4
    assert result["pipeline_result"]["board"]["top_cards"]["not_forced"] is True
    assert result["pipeline_result"]["refresh_cycle"]["snapshot_source"] == "current_refresh"
    assert result["market_audit"]["different_lines_blended"] is False

    mismatch = _run(shift_points_line=True)
    assert mismatch["market_audit"]["exact_line_multibook_group_count"] == 3
    assert mismatch["shadow_summary"]["qualified_prop_count"] == 3
    assert mismatch["shadow_summary"]["top_card_count"] == 3
    assert mismatch["market_audit"]["different_lines_blended"] is False

    primary = result["pipeline_result"]["board"]["top_cards"]["primary"]
    ranking_order = [card["player_id"] for card in primary]
    assert ranking_order == [1642301, 1642302, 1642304, 1642303]

    guards = result["guardrails"]
    assert guards["shadow_only"] is True
    assert guards["sportsbook_network_fetch_performed"] is True
    assert guards["exact_line_consensus_required"] is True
    assert guards["different_lines_blended"] is False
    assert guards["scheduler_started"] is False
    assert guards["persistence_mutated"] is False
    assert guards["supabase_mutated"] is False
    assert guards["production_runtime_enabled"] is False
    assert guards["production_activation_allowed"] is False
    assert guards["public_fastapi_route_added"] is False
    assert guards["wager_action_performed"] is False

    evidence = {
        "data_type": "wnba_step11d_multibook_shadow_board_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "release_id": s11d.RELEASE_ID,
        "schema_version": s11d.SCHEMA_VERSION,
        "model_version": s11d.MODEL_VERSION,
        "frozen_lineage": {
            "step11c_sha": s11d.STEP11C_FROZEN_HEAD_SHA,
            "step11b_sha": s11d.STEP11B_FROZEN_HEAD_SHA,
            "step11a_sha": s11d.STEP11A_FROZEN_HEAD_SHA,
            "step10_sha": s11d.STEP10_FROZEN_HEAD_SHA,
        },
        "certified_shadow": {
            "sportsbooks": result["sportsbooks"],
            "eligible_market_record_count": summary["eligible_market_record_count"],
            "matched_prop_count": summary["matched_prop_count"],
            "exact_line_multibook_group_count": summary["exact_line_multibook_group_count"],
            "qualified_prop_count": summary["qualified_prop_count"],
            "requested_top_n": summary["requested_top_n"],
            "top_card_count": summary["top_card_count"],
            "ranking_player_order": ranking_order,
            "step10_pipeline_content_sha256": result["lineage"]["step10_pipeline_content_sha256"],
            "step10c_snapshot_content_sha256": result["lineage"]["step10c_snapshot_content_sha256"],
            "step9_ranking_content_sha256": result["lineage"]["step9_ranking_content_sha256"],
            "shadow_board_content_sha256": result["shadow_board_content_sha256"],
        },
        "mismatched_line_probe": {
            "exact_line_multibook_group_count": mismatch["market_audit"]["exact_line_multibook_group_count"],
            "qualified_prop_count": mismatch["shadow_summary"]["qualified_prop_count"],
            "top_card_count": mismatch["shadow_summary"]["top_card_count"],
            "different_lines_blended": mismatch["market_audit"]["different_lines_blended"],
        },
        "safety": guards,
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
