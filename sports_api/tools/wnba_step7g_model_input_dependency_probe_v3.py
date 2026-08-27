"""OFF-only real-chain probe after certified Step 4J team history.

This probe reuses the already-certified Step 7G first-party player-history,
play-by-play, Step 4N schedule-context, and Step 4J team-history adapters. It
executes the real frozen Step 4X model-input readiness call and records the next
boundary reached after Step 4J. Production remains disabled throughout.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_model_input_dependency_probe as probe
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)
from sports_api.wnba_step7g_first_party_team_history import (
    get_first_party_team_game_log_dataset,
)

REPORT_PATH = Path("step7g-model-input-dependency-probe-v3.json")


def main() -> int:
    probe._assert_off()
    started = datetime.now(timezone.utc)
    player, selected_history = probe._select_probe_player()
    player_id = int(player["player_id"])
    team_history_calls: list[dict[str, Any]] = []

    def recent_history(
        pid: int,
        season: int,
        *,
        season_type: str = "Regular Season",
    ) -> dict[str, Any]:
        if (
            pid == player_id
            and season == probe.SEASON
            and season_type == "Regular Season"
        ):
            return selected_history
        return probe.get_first_party_player_recent_game_log_dataset(
            pid,
            season,
            season_type=season_type,
        )

    def certified_team_history(
        team_key: str,
        season: int,
        *,
        season_type: str = "Regular Season",
        **kwargs: Any,
    ) -> dict[str, Any]:
        dataset = get_first_party_team_game_log_dataset(
            team_key,
            season,
            season_type=season_type,
            **kwargs,
        )
        verification = dataset.get("verification") or {}
        team_history_calls.append(
            {
                "team_key": team_key,
                "season": season,
                "season_type": season_type,
                "game_count": dataset.get("game_count"),
                "source": dataset.get("source"),
                "all_game_ids_valid": verification.get("all_game_ids_valid"),
                "all_rows_mapped": verification.get("all_rows_mapped_to_registry"),
                "all_opponents_resolved": verification.get(
                    "all_opponent_team_keys_resolved"
                ),
                "schedule_box_identity_match": verification.get(
                    "schedule_box_identity_match"
                ),
                "schedule_box_score_match": verification.get(
                    "schedule_box_score_match"
                ),
            }
        )
        return dataset

    # Diagnostic process-local injections only. Frozen source files remain unchanged.
    probe.rotation._request_stats_json = probe._raise_rotation_transport_unavailable
    probe.rotation.get_player_game_log_dataset = recent_history
    probe.event_lineup.get_play_by_play_dataset = (
        probe.get_first_party_play_by_play_dataset
    )
    probe.event_features.get_player_game_log_dataset = recent_history
    probe.opportunity.get_player_role_context_dataset = (
        probe._raise_optional_lineup_unavailable
    )
    probe.opportunity.get_lineups_dataset = probe._raise_optional_lineup_unavailable
    probe.schedule_context._season_schedule_dataset = (
        get_step7g_step4n_season_schedule_dataset
    )
    probe.schedule_context.get_team_game_log_dataset = certified_team_history

    report: dict[str, Any] = {
        "data_type": "wnba_step7g_real_model_input_dependency_probe_v3",
        "started_at_utc": started.isoformat(),
        "season": probe.SEASON,
        "sample_game_id": probe.SAMPLE_GAME_ID,
        "recent_window_games": probe.LAST_N_GAMES,
        "sample_player": player,
        "diagnostic_injections": {
            "first_party_player_recent_history": True,
            "first_party_play_by_play": True,
            "certified_rotation_fallback_forced_by_transport_failure": True,
            "certified_first_party_step4n_schedule_context": True,
            "certified_first_party_step4j_team_history": True,
            "optional_step4v_lineup_stats_fail_soft_without_network": True,
            "frozen_source_files_modified": False,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "production_activation_allowed": False,
        },
    }

    try:
        result = probe.readiness.get_player_game_model_input_readiness(
            player_id,
            probe.SAMPLE_GAME_ID,
            probe.SEASON,
            season_type="Regular Season",
            last_n_games=probe.LAST_N_GAMES,
            require_current_availability=False,
            include_shot_context=False,
            include_advanced_context=False,
            include_officiating_context=False,
            include_snapshot=True,
        )
    except Exception as exc:  # boundary discovery; no user secrets in probe inputs
        report["returned_readiness"] = False
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:1500],
        }
    else:
        report["returned_readiness"] = True
        report["readiness"] = result.get("readiness")
        report["can_start_projection"] = result.get("can_start_projection")
        report["summary"] = result.get("summary")
        report["verification"] = result.get("verification")

    report["step4j_team_history_calls"] = team_history_calls
    report["step4j_boundary_cleared"] = bool(team_history_calls)
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_seconds"] = round(
        (datetime.now(timezone.utc) - started).total_seconds(), 3
    )

    exception_message = str((report.get("exception") or {}).get("message") or "")
    old_sentinel_seen = "STEP7G_UNRESOLVED_TEAM_GAME_HISTORY_TRANSPORT_SENTINEL" in exception_message
    report["old_team_history_sentinel_seen"] = old_sentinel_seen

    if not team_history_calls:
        report["probe_outcome"] = "FAILED_BEFORE_CERTIFIED_STEP4J_TEAM_HISTORY"
        report["next_required_dependency"] = "Investigate pre-Step4J regression"
    elif old_sentinel_seen:
        report["probe_outcome"] = "FAILED_TO_REPLACE_OLD_STEP4J_SENTINEL"
        report["next_required_dependency"] = "Repair diagnostic injection"
    elif report.get("returned_readiness"):
        report["probe_outcome"] = "REAL_STEP4X_CHAIN_RETURNED_AFTER_CERTIFIED_STEP4J"
        report["next_required_dependency"] = None
    else:
        report["probe_outcome"] = "REAL_STEP4X_CHAIN_PASSED_STEP4J_AND_REACHED_NEXT_BOUNDARY"
        report["next_required_dependency"] = report.get("exception")

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    probe._assert_off()

    if not team_history_calls or old_sentinel_seen:
        raise RuntimeError(
            "Step 7G v3 probe did not prove the real Step 4X chain cleared certified Step 4J."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
