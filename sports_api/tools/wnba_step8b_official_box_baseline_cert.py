"""OFF-only live certification for the Step-8B official box-stat baseline."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step8_official_box_baseline import (
    BASELINE_RELEASE_ID,
    SCHEMA_VERSION,
    build_step8_official_box_baseline,
)
from sports_api.wnba_step8_projection_handoff import get_player_game_step8_projection_handoff

REPORT_PATH = Path("step8b-official-box-baseline-cert.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Step 8B box baseline cert refuses production switches: " + ", ".join(bad))
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 8B box baseline cert requires Step 7G first-party mode in isolated CI.")
    if not _truthy(os.getenv("WNBA_STEP8_PROJECTION_HANDOFF_ENABLED")):
        raise RuntimeError("Step 8B box baseline cert requires Step 8A in isolated CI.")


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])

    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    baseline = build_step8_official_box_baseline(handoff)
    if baseline.get("data_type") != "official_recent_player_box_stat_baseline":
        raise RuntimeError("Step 8B official baseline returned wrong data type.")
    if baseline.get("schema_version") != SCHEMA_VERSION or baseline.get("baseline_release_id") != BASELINE_RELEASE_ID:
        raise RuntimeError("Step 8B official baseline returned wrong contract identity.")
    if baseline.get("player_id") != player_id or baseline.get("requested_game_id") != game_id:
        raise RuntimeError("Step 8B official baseline returned wrong requested identity.")
    ids = baseline.get("selected_game_ids")
    if not isinstance(ids, list) or len(ids) != 5 or len(set(ids)) != 5:
        raise RuntimeError("Step 8B official baseline did not preserve exactly five unique games.")
    if not all(isinstance(gid, str) and gid.startswith("10226") for gid in ids):
        raise RuntimeError("Step 8B official baseline admitted a non-certified game family.")

    summary = baseline.get("summary")
    if not isinstance(summary, dict) or summary.get("game_count") != 5:
        raise RuntimeError("Step 8B official baseline summary is malformed.")
    for stat in ("minutes", "points", "rebounds", "assists", "points_rebounds_assists"):
        row = summary.get(stat)
        if not isinstance(row, dict) or not isinstance(row.get("mean"), (int, float)):
            raise RuntimeError(f"Step 8B official baseline missing numeric {stat} mean.")
    for stat in ("points", "rebounds", "assists", "points_rebounds_assists"):
        rate = (summary.get("official_per_minute_rates") or {}).get(stat)
        if not isinstance(rate, (int, float)) or rate < 0:
            raise RuntimeError(f"Step 8B official baseline missing valid {stat} per-minute rate.")

    handoff_snapshot = handoff["snapshot"]
    opportunity = handoff_snapshot["inputs"]["player_opportunity_context"]
    stability = opportunity["observed_minutes_opportunity"]["tracked_minutes"]["stability"]
    rotation_mean = float(stability["tracked_minutes_mean"])
    official_mean = float(summary["minutes"]["mean"])
    if abs(rotation_mean - official_mean) > 0.02:
        raise RuntimeError(
            f"Step 8B official box/rotation average minutes diverged: {official_mean} vs {rotation_mean}."
        )

    event_rates = opportunity["observed_event_opportunity"]["own_event_counts_per_feature_game"]
    event_quality = opportunity["observed_event_opportunity"]["data_quality"]
    verification = baseline.get("verification") or {}
    semantics = baseline.get("semantics") or {}
    guardrails = baseline.get("guardrails") or {}
    for key in (
        "advanced_selected_game_ids_used_exactly",
        "player_resolved_exactly_once_per_box",
        "box_player_team_identity_matches_handoff_evidence",
        "advanced_and_box_average_minutes_match",
        "most_recent_team_matches_current_focal_team",
    ):
        if verification.get(key) is not True:
            raise RuntimeError(f"Step 8B baseline verification {key!r} is not true.")
    if semantics.get("points_rebounds_assists_are_complete_official_box_counts") is not True:
        raise RuntimeError("Step 8B baseline did not preserve official P/R/A semantics.")
    if semantics.get("pbp_feature_counts_are_not_used_as_official_box_totals") is not True:
        raise RuntimeError("Step 8B baseline did not explicitly reject PBP counts as box totals.")
    if guardrails.get("baseline_is_observed_history_not_projection") is not True:
        raise RuntimeError("Step 8B box baseline incorrectly claims projection semantics.")
    if guardrails.get("no_monte_carlo_created") is not True:
        raise RuntimeError("Step 8B box baseline unexpectedly created Monte Carlo semantics.")

    report = {
        "data_type": "wnba_step8b_official_box_baseline_cert_v1",
        "certification_result": "STEP8B_OFFICIAL_BOX_BASELINE_LIVE_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "handoff": {
            "handoff_id": handoff.get("handoff_id"),
            "handoff_content_sha256": handoff.get("handoff_content_sha256"),
        },
        "official_box_baseline": {
            "baseline_id": baseline.get("baseline_id"),
            "baseline_content_sha256": baseline.get("baseline_content_sha256"),
            "selected_game_ids": ids,
            "official_means": {
                stat: summary[stat]["mean"]
                for stat in ("minutes", "points", "rebounds", "assists", "points_rebounds_assists")
            },
            "official_per_minute_rates": summary.get("official_per_minute_rates"),
            "rotation_mean_minutes": rotation_mean,
            "box_rotation_mean_minutes_difference": round(official_mean - rotation_mean, 6),
        },
        "pbp_diagnostic_contrast_not_model_baseline": {
            "feature_eligible_share": event_quality.get("feature_eligible_share_of_selected_lineup_events"),
            "event_points_per_feature_game": event_rates.get("points"),
            "event_rebounds_per_feature_game": event_rates.get("rebounds"),
            "event_assists_per_feature_game": event_rates.get("assists"),
            "event_fta_per_feature_game": event_rates.get("free_throws_attempted"),
            "used_as_official_baseline": False,
        },
        "safety": {
            "projection_created": False,
            "monte_carlo_created": False,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8B_OFFICIAL_BOX_BASELINE_LIVE_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
