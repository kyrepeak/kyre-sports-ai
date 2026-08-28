"""Offline certification for frozen WNBA Step 10D refresh controller."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_market_snapshot as step10c
from sports_api import wnba_step10_refresh_controller as step10d

UTC = timezone.utc
BRANCH = "wnba-step10d-refresh-controller-20260828"
CERT_MARKER = "STEP10D_REFRESH_CONTROLLER_CONTRACT_FROZEN_CERTIFIED"
OUTPUT_PATH = Path("step10d-refresh-controller-cert.json")


def _env() -> dict[str, str]:
    return {
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
    }


def _payload(provider: str, sportsbook: str, captured: str, over: int, under: int) -> dict:
    return {
        "provider": provider,
        "price_format": "american",
        "records": [{
            "game_id": "1022600291",
            "player_id": 1642301,
            "player_name": "Certification Player A",
            "sportsbook": sportsbook,
            "stat": "points",
            "line": 20.5,
            "over_price": over,
            "under_price": under,
            "market_captured_at": captured,
        }],
    }


def _build_last_good(env: dict[str, str]) -> dict:
    evaluated = datetime(2026, 8, 28, 5, 26, 0, tzinfo=UTC)
    a = step10b.adapt_step10b_market_payload(
        "flat_two_way_v1",
        _payload("Provider A", "Book A", "2026-08-28T05:25:30+00:00", -110, -110),
        evaluated_at=evaluated,
        env=env,
    )
    b = step10b.adapt_step10b_market_payload(
        "flat_two_way_v1",
        _payload("Provider B", "Book B", "2026-08-28T05:25:40+00:00", -108, -112),
        evaluated_at=evaluated,
        env=env,
    )
    return step10c.build_step10c_market_snapshot([a, b], evaluated_at=evaluated, env=env)


def main() -> None:
    env = _env()
    last_good = _build_last_good(env)
    evaluated = datetime(2026, 8, 28, 5, 27, 0, tzinfo=UTC)
    current = step10d.run_step10d_refresh_cycle(
        [
            {
                "provider": "Provider A",
                "adapter_type": "flat_two_way_v1",
                "attempts": [
                    {"ok": False, "error_code": "timeout"},
                    {"ok": True, "payload": _payload(
                        "Provider A", "Book A", "2026-08-28T05:26:30+00:00", -105, -115
                    )},
                ],
            },
            {
                "provider": "Provider B",
                "adapter_type": "flat_two_way_v1",
                "attempts": [
                    {"ok": True, "payload": _payload(
                        "Provider B", "Book B", "2026-08-28T05:26:40+00:00", -110, -110
                    )},
                ],
            },
            {
                "provider": "Provider C",
                "adapter_type": "flat_two_way_v1",
                "attempts": [
                    {"ok": False, "error_code": "timeout"},
                    {"ok": False, "error_code": "rate_limited"},
                ],
            },
        ],
        evaluated_at=evaluated,
        cycle_started_at=datetime(2026, 8, 28, 5, 26, 50, tzinfo=UTC),
        last_good_snapshot=last_good,
        expected_sportsbooks=["Book A", "Book B", "Book C"],
        env=env,
    )

    assert current["status"] == "ready"
    assert current["snapshot_source"] == "current_refresh"
    assert current["refresh"]["provider_count"] == 3
    assert current["refresh"]["successful_provider_count"] == 2
    assert current["refresh"]["failed_provider_count"] == 1
    assert current["refresh"]["total_attempts_consumed"] == 5
    assert current["providers"][0]["attempts"][1]["retry_delay_seconds_before_attempt"] == 2.0
    assert current["refresh"]["retry_policy"]["sleep_executed"] is False
    assert current["market_snapshot"]["snapshot"]["eligible_record_count"] == 2
    assert current["market_snapshot"]["snapshot"]["board_capture_spread_seconds"] == 10.0
    assert current["market_snapshot"]["market_groups"][0]["consensus_ready_two_plus_books"] is True
    assert current["market_snapshot"]["market_families"][0]["missing_expected_sportsbooks"] == ["Book C"]
    assert current["market_snapshot"]["movement"]["previous_snapshot_supplied"] is True
    assert len(current["market_snapshot"]["movement"]["exact_line_price_changes"]) == 2

    fallback = step10d.run_step10d_refresh_cycle(
        [
            {
                "provider": "Provider A",
                "adapter_type": "flat_two_way_v1",
                "attempts": [{"ok": False, "error_code": "timeout"}],
            },
            {
                "provider": "Provider B",
                "adapter_type": "flat_two_way_v1",
                "attempts": [{"ok": False, "error_code": "upstream_503"}],
            },
        ],
        evaluated_at=datetime(2026, 8, 28, 5, 27, 30, tzinfo=UTC),
        cycle_started_at=datetime(2026, 8, 28, 5, 27, 20, tzinfo=UTC),
        last_good_snapshot=current["market_snapshot"],
        env=env,
    )
    assert fallback["status"] == "degraded_last_good"
    assert fallback["snapshot_source"] == "last_good_snapshot"
    assert fallback["last_good"]["used"] is True
    assert fallback["last_good"]["age_seconds_at_evaluation"] == 50.0
    assert fallback["market_snapshot"]["snapshot_content_sha256"] == current["market_snapshot"]["snapshot_content_sha256"]

    guards = current["guardrails"]
    for key in (
        "sportsbook_network_fetch_performed", "retry_sleep_performed", "basketball_projection_changed",
        "step8_distribution_changed", "step9_called", "vig_removed", "edge_calculated",
        "expected_value_calculated", "cross_sportsbook_consensus_calculated", "cross_prop_ranking_calculated",
        "supabase_mutated", "persistence_mutated", "scheduler_started", "production_runtime_enabled",
        "production_activation_allowed",
    ):
        assert guards[key] is False, key

    evidence = {
        "data_type": "wnba_step10d_refresh_controller_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "frozen_step10c_head_sha": step10d.STEP10C_FROZEN_HEAD_SHA,
        "schema_version": step10d.SCHEMA_VERSION,
        "model_version": step10d.MODEL_VERSION,
        "release_id": step10d.RELEASE_ID,
        "current_cycle": {
            "refresh_cycle_id": current["refresh_cycle_id"],
            "status": current["status"],
            "successful_provider_count": current["refresh"]["successful_provider_count"],
            "failed_provider_count": current["refresh"]["failed_provider_count"],
            "total_attempts_consumed": current["refresh"]["total_attempts_consumed"],
            "next_refresh_due_at_utc": current["refresh"]["next_refresh_due_at_utc"],
            "step10c_snapshot_content_sha256": current["market_snapshot"]["snapshot_content_sha256"],
            "refresh_cycle_content_sha256": current["refresh_cycle_content_sha256"],
        },
        "fallback_cycle": {
            "refresh_cycle_id": fallback["refresh_cycle_id"],
            "status": fallback["status"],
            "snapshot_source": fallback["snapshot_source"],
            "last_good_age_seconds": fallback["last_good"]["age_seconds_at_evaluation"],
            "served_snapshot_content_sha256": fallback["market_snapshot"]["snapshot_content_sha256"],
            "refresh_cycle_content_sha256": fallback["refresh_cycle_content_sha256"],
        },
        "safety": guards,
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
