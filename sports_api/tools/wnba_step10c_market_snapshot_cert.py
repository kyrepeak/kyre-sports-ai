"""Offline deterministic release certificate for WNBA Step 10C."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_market_snapshot as step10c

CERT_MARKER = "STEP10C_MARKET_SNAPSHOT_CONTRACT_FROZEN_CERTIFIED"
OUTPUT_PATH = Path("step10c-market-snapshot-cert.json")


def _flat(provider: str, records: list[dict], evaluated_at: datetime) -> dict:
    return step10b.adapt_step10b_market_payload(
        "flat_two_way_v1",
        {"provider": provider, "price_format": "american", "records": records},
        evaluated_at=evaluated_at,
    )


def _row(
    book: str,
    line: float,
    over: int,
    under: int,
    captured: str,
    *,
    player_id: int = 1642301,
    player_name: str = "Certification Player A",
    stat: str = "points",
) -> dict:
    return {
        "game_id": "1022600291",
        "player_id": player_id,
        "player_name": player_name,
        "sportsbook": book,
        "stat": stat,
        "line": line,
        "over_price": over,
        "under_price": under,
        "market_captured_at": captured,
    }


def main() -> None:
    for key in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    ):
        assert str(os.environ.get(key, "false")).casefold() == "false", key
    assert str(os.environ.get("WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED", "")).casefold() == "true"
    assert str(os.environ.get("WNBA_STEP10B_MARKET_ADAPTER_ENABLED", "")).casefold() == "true"
    assert str(os.environ.get("WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED", "")).casefold() == "true"
    assert step10c.STEP10B_FROZEN_HEAD_SHA == "1088358452ca2bc9e45a2bb3544b44331606d88c"

    prior_eval = datetime(2026, 8, 28, 5, 18, 0, tzinfo=timezone.utc)
    prior_adapter = _flat(
        "Certification Prior Feed",
        [
            _row("Certification Book A", 20.5, -110, -110, "2026-08-28T05:17:30Z"),
            _row("Certification Book C", 18.5, -120, 100, "2026-08-28T05:17:40Z"),
        ],
        prior_eval,
    )
    prior = step10c.build_step10c_market_snapshot(
        [prior_adapter],
        evaluated_at=prior_eval,
        expected_sportsbooks=["Certification Book A", "Certification Book C", "Certification Book D"],
    )

    current_eval = datetime(2026, 8, 28, 5, 20, 0, tzinfo=timezone.utc)
    snapshots = [
        _flat(
            "Certification Feed A old",
            [_row("Certification Book A", 20.5, -115, -105, "2026-08-28T05:18:50Z")],
            current_eval,
        ),
        _flat(
            "Certification Feed A current",
            [_row("Certification Book A", 20.5, -105, -115, "2026-08-28T05:19:30Z")],
            current_eval,
        ),
        _flat(
            "Certification Feed B",
            [_row("Certification Book B", 20.5, -110, -110, "2026-08-28T05:19:40Z")],
            current_eval,
        ),
        _flat(
            "Certification Feed C",
            [_row("Certification Book C", 19.5, -125, 105, "2026-08-28T05:19:45Z")],
            current_eval,
        ),
        _flat(
            "Certification stale feed",
            [_row("Certification Stale Book", 20.5, -110, -110, "2026-08-28T05:00:00Z")],
            current_eval,
        ),
    ]

    result = step10c.build_step10c_market_snapshot(
        snapshots,
        evaluated_at=current_eval,
        previous_snapshot=prior,
        expected_sportsbooks=[
            "Certification Book A", "Certification Book B", "Certification Book C", "Certification Book D"
        ],
    )

    assert result["snapshot"]["input_adapter_snapshot_count"] == 5
    assert result["snapshot"]["input_record_count"] == 5
    assert result["snapshot"]["reconciled_identity_count"] == 4
    assert result["snapshot"]["eligible_record_count"] == 3
    assert result["snapshot"]["stale_record_count"] == 1
    assert result["snapshot"]["board_synchronized"] is True
    assert result["snapshot"]["board_capture_spread_seconds"] == 15.0

    point_205 = next(group for group in result["market_groups"] if group["line"] == 20.5)
    assert point_205["sportsbook_count"] == 2
    assert point_205["consensus_ready_two_plus_books"] is True
    book_a = next(record for record in result["records"] if record["sportsbook"] == "Certification Book A")
    assert book_a["over_odds"] == -105
    assert book_a["under_odds"] == -115
    assert book_a["superseded_update_count"] == 1
    assert any(item["reason"] == "stale" for item in result["excluded_records"])
    assert len(result["movement"]["exact_line_price_changes"]) == 1
    assert len(result["movement"]["unique_line_changes"]) == 1
    assert result["movement"]["unique_line_changes"][0]["previous_line"] == 18.5
    assert result["movement"]["unique_line_changes"][0]["current_line"] == 19.5
    assert all("Certification Book D" in family["missing_expected_sportsbooks"] for family in result["market_families"])

    guards = result["guardrails"]
    assert guards["market_snapshot_reconciled"] is True
    assert guards["freshness_evaluated"] is True
    assert guards["line_movement_calculated"] is True
    for key in (
        "sportsbook_network_fetch_performed", "basketball_projection_changed",
        "step8_distribution_changed", "step9_called", "vig_removed", "edge_calculated",
        "expected_value_calculated", "cross_sportsbook_consensus_calculated",
        "cross_prop_ranking_calculated", "supabase_mutated", "persistence_mutated",
        "scheduler_started", "production_runtime_enabled", "production_activation_allowed",
    ):
        assert guards[key] is False, key

    evidence = {
        "data_type": "wnba_step10c_market_snapshot_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": os.environ.get("GITHUB_REF_NAME", "offline"),
        "github_head_sha": os.environ.get("GITHUB_SHA", "offline"),
        "frozen_step10b_head_sha": step10c.STEP10B_FROZEN_HEAD_SHA,
        "schema_version": step10c.SCHEMA_VERSION,
        "model_version": step10c.MODEL_VERSION,
        "release_id": step10c.RELEASE_ID,
        "snapshot_content_sha256": result["snapshot_content_sha256"],
        "reconciled_step10a_snapshot_content_sha256": result["reconciled_step10a_snapshot"]["snapshot_content_sha256"],
        "snapshot": result["snapshot"],
        "certified_market_groups": result["market_groups"],
        "movement": result["movement"],
        "safety": result["guardrails"],
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
