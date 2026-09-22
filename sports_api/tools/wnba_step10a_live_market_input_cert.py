"""Offline deterministic certification for WNBA Step 10A live market input."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step9_release_freeze as step9
from sports_api import wnba_step10_live_market_input as market

REPORT_PATH = Path("step10a-live-market-input-cert.json")
MARKER = "STEP10A_LIVE_MARKET_INPUT_CONTRACT_FROZEN_CERTIFIED"


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_environment() -> None:
    if not _truthy(os.getenv(market.STEP10A_LIVE_MARKET_INPUT_ENABLED_ENV)):
        raise RuntimeError("Step 10A certification gate is not enabled.")
    for name in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    ):
        if _truthy(os.getenv(name)):
            raise RuntimeError(f"Step 10A certification refuses unsafe switch {name}.")


def main() -> int:
    _assert_environment()
    if market.STEP9_FROZEN_HEAD_SHA != "bd228921ea993c8c74b6454ae56cee94711b0e94":
        raise RuntimeError("Step 10A frozen Step-9 head drifted.")
    if step9.RELEASE_ID != "wnba_step9_market_board_2026_regular_season_frozen_v1":
        raise RuntimeError("Step 10A Step-9 release lineage drifted.")
    if step9.DEFAULT_ENABLED is not False or step9.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise RuntimeError("Step 10A requires Step 9 to remain default-OFF and non-production.")

    evaluated = datetime(2026, 8, 28, 5, 10, 0, tzinfo=timezone.utc)
    records = [
        {
            "game_id": "1022600291",
            "player_id": 1642301,
            "player_name": "Certification Player One",
            "sportsbook": "Certification Book A",
            "stat": "PTS",
            "line": 20.5,
            "over_odds": -110,
            "under_odds": -110,
            "market_captured_at_utc": "2026-08-28T05:09:20+00:00",
        },
        {
            "game_id": "1022600291",
            "player_id": 1642301,
            "player_name": "Certification Player One",
            "sportsbook": "Certification Book B",
            "stat": "points",
            "line": 20.5,
            "over_odds": -105,
            "under_odds": -115,
            "market_captured_at_utc": "2026-08-28T05:09:30+00:00",
        },
        {
            "game_id": "1022600291",
            "player_id": 1642301,
            "player_name": "Certification Player One",
            "sportsbook": "Certification Book A",
            "stat": "points",
            "line": 19.5,
            "over_odds": -125,
            "under_odds": 105,
            "market_captured_at_utc": "2026-08-28T05:09:40+00:00",
        },
        {
            "game_id": "1022600291",
            "player_id": 1642302,
            "player_name": "Certification Player Two",
            "sportsbook": "Certification Book A",
            "stat": "rebs",
            "line": 10.5,
            "over_odds": 100,
            "under_odds": -120,
            "market_captured_at_utc": "2026-08-28T05:09:50+00:00",
        },
    ]

    result = market.build_step10a_live_market_input_snapshot(
        records,
        evaluated_at=evaluated,
    )
    snapshot = result["snapshot"]
    if snapshot["record_count"] != 4:
        raise RuntimeError("Step 10A certification record count drifted.")
    if snapshot["unique_game_count"] != 1 or snapshot["unique_player_game_count"] != 2:
        raise RuntimeError("Step 10A certification identity counts drifted.")
    if snapshot["unique_sportsbook_count"] != 2 or snapshot["unique_stat_count"] != 2:
        raise RuntimeError("Step 10A certification market dimension counts drifted.")
    if snapshot["capture_spread_seconds"] != 30.0:
        raise RuntimeError("Step 10A certification capture-spread evidence drifted.")
    if result["records"][0]["stat"] != "points":
        raise RuntimeError("Step 10A certification stat normalization drifted.")
    if result["lineage"]["step9_frozen_head_sha"] != market.STEP9_FROZEN_HEAD_SHA:
        raise RuntimeError("Step 10A certification Step-9 lineage drifted.")

    guards = result["guardrails"]
    if guards["sportsbook_quote_consumed"] is not True:
        raise RuntimeError("Step 10A must consume caller-supplied quote content.")
    for key in (
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9_called",
        "sportsbook_network_fetch_performed",
        "sportsbook_adapter_applied",
        "vig_removed",
        "edge_calculated",
        "expected_value_calculated",
        "cross_sportsbook_consensus_calculated",
        "line_movement_calculated",
        "cross_prop_ranking_calculated",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        if guards[key] is not False:
            raise RuntimeError(f"Step 10A safety guard {key!r} drifted.")

    report = {
        "data_type": "wnba_step10a_live_market_input_cert_v1",
        "certification_result": MARKER,
        "branch": os.getenv("GITHUB_REF_NAME"),
        "github_head_sha": os.getenv("GITHUB_SHA"),
        "release_id": market.RELEASE_ID,
        "schema_version": market.SCHEMA_VERSION,
        "model_version": market.MODEL_VERSION,
        "frozen_step9_head_sha": market.STEP9_FROZEN_HEAD_SHA,
        "snapshot_content_sha256": result["snapshot_content_sha256"],
        "snapshot": snapshot,
        "certified_records": [
            {
                "quote_id": row["quote_id"],
                "game_id": row["game_id"],
                "player_id": row["player_id"],
                "sportsbook": row["sportsbook"],
                "stat": row["stat"],
                "line": row["line"],
                "over_odds": row["over_odds"],
                "under_odds": row["under_odds"],
                "market_captured_at_utc": row["market_captured_at_utc"],
            }
            for row in result["records"]
        ],
        "safety": guards,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(MARKER)
    _assert_environment()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
