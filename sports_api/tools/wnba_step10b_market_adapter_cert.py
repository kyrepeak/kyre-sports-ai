"""Offline release certificate for WNBA Step 10B market adapters."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step10_live_market_input as step10a
from sports_api import wnba_step10_market_adapters as step10b


BRANCH = "wnba-step10b-market-adapters-20260828"
CERT_MARKER = "STEP10B_MARKET_ADAPTER_CONTRACT_FROZEN_CERTIFIED"
EVALUATED_AT = datetime(2026, 8, 28, 5, 10, 0, tzinfo=timezone.utc)


def _assert_env() -> None:
    for key in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    ):
        if str(os.environ.get(key, "")).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}:
            raise RuntimeError(f"Certification refuses unsafe environment: {key}")
    if not step10a.step10a_live_market_input_enabled(os.environ):
        raise RuntimeError("Step 10A certification gate must be enabled for Step 10B cert.")
    if not step10b.step10b_market_adapter_enabled(os.environ):
        raise RuntimeError("Step 10B certification gate must be enabled.")


def _flat_payload() -> dict:
    return {
        "provider": "Certification Flat Feed",
        "price_format": "american",
        "records": [
            {
                "game_id": "1022600291",
                "player_id": 1642301,
                "player_name": "Certification Player",
                "sportsbook": "Certification Book A",
                "stat": "points",
                "line": 20.5,
                "over_price": -110,
                "under_price": -110,
                "market_captured_at": "2026-08-28T05:09:20Z",
            },
            {
                "game_id": "1022600291",
                "player_id": 1642301,
                "player_name": "Certification Player",
                "sportsbook": "Certification Book B",
                "stat": "pts",
                "line": 20.5,
                "over_price": -105,
                "under_price": -115,
                "market_captured_at": "2026-08-28T05:09:30Z",
            },
            {
                "game_id": "1022600291",
                "player_id": 1642301,
                "player_name": "Certification Player",
                "sportsbook": "Certification Book A",
                "stat": "points",
                "line": 19.5,
                "over_price": -125,
                "under_price": 105,
                "market_captured_at": "2026-08-28T05:09:40Z",
            },
        ],
    }


def _outcomes_payload() -> dict:
    return {
        "provider": "Certification Outcomes Feed",
        "price_format": "decimal",
        "markets": [
            {
                "game_id": "1022600291",
                "player_id": 1642302,
                "player_name": "Certification Rebounder",
                "sportsbook": "Certification Book A",
                "stat": "reb",
                "market_captured_at": "2026-08-28T05:09:50+00:00",
                "outcomes": [
                    {"side": "Under", "price": 1.8333333333, "line": 10.5},
                    {"side": "Over", "price": 2.0, "line": 10.5},
                ],
            }
        ],
    }


def main() -> None:
    _assert_env()
    if step10b.STEP10A_FROZEN_HEAD_SHA != "4a8f822684c1d56d1ef062f0db25d5f671409def":
        raise RuntimeError("Step 10A frozen-head binding drifted.")
    if step10b.SCHEMA_VERSION != "wnba_step_10b_market_adapter_v1":
        raise RuntimeError("Step 10B schema drifted.")
    if step10b.MODEL_VERSION != "wnba_step10b_strict_provider_adapter_2026_regular_v1":
        raise RuntimeError("Step 10B model drifted.")

    flat = step10b.adapt_step10b_market_payload(
        step10b.ADAPTER_FLAT_TWO_WAY_V1,
        _flat_payload(),
        evaluated_at=EVALUATED_AT,
        env=os.environ,
    )
    outcomes = step10b.adapt_step10b_market_payload(
        step10b.ADAPTER_OUTCOMES_TWO_WAY_V1,
        _outcomes_payload(),
        evaluated_at=EVALUATED_AT,
        env=os.environ,
    )

    if flat["step10a_snapshot"]["snapshot"]["record_count"] != 3:
        raise RuntimeError("Flat adapter record count mismatch.")
    if outcomes["step10a_snapshot"]["snapshot"]["record_count"] != 1:
        raise RuntimeError("Outcomes adapter record count mismatch.")
    outcome_row = outcomes["step10a_snapshot"]["records"][0]
    if outcome_row["over_odds"] != 100 or outcome_row["under_odds"] != -120:
        raise RuntimeError("Decimal-to-American certification conversion mismatch.")
    for result in (flat, outcomes):
        guards = result["guardrails"]
        if not guards["sportsbook_adapter_applied"] or not guards["raw_provider_payload_consumed"]:
            raise RuntimeError("Step 10B adapter evidence missing.")
        for key in (
            "sportsbook_network_fetch_performed",
            "basketball_projection_changed",
            "step8_distribution_changed",
            "step9_called",
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
                raise RuntimeError(f"Unsafe Step 10B guardrail: {key}")

    evidence = {
        "data_type": "wnba_step10b_market_adapter_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "frozen_step10a_head_sha": step10b.STEP10A_FROZEN_HEAD_SHA,
        "release_id": step10b.RELEASE_ID,
        "schema_version": step10b.SCHEMA_VERSION,
        "model_version": step10b.MODEL_VERSION,
        "supported_adapters": list(step10b.SUPPORTED_ADAPTERS),
        "supported_price_formats": list(step10b.SUPPORTED_PRICE_FORMATS),
        "certified_adapters": {
            "flat_two_way_v1": {
                "provider": flat["adapter"]["provider"],
                "record_count": flat["adapter"]["output_record_count"],
                "step10a_snapshot_content_sha256": flat["step10a_snapshot"]["snapshot_content_sha256"],
                "adapter_content_sha256": flat["adapter_content_sha256"],
            },
            "outcomes_two_way_v1": {
                "provider": outcomes["adapter"]["provider"],
                "record_count": outcomes["adapter"]["output_record_count"],
                "converted_over_odds": outcome_row["over_odds"],
                "converted_under_odds": outcome_row["under_odds"],
                "step10a_snapshot_content_sha256": outcomes["step10a_snapshot"]["snapshot_content_sha256"],
                "adapter_content_sha256": outcomes["adapter_content_sha256"],
            },
        },
        "safety": flat["guardrails"],
    }
    Path("step10b-market-adapter-cert.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
