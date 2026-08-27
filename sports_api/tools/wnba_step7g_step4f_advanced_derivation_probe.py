"""OFF-only live probe for Step 7G first-party Step 4F derivation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step7g_first_party_advanced_stats import (
    get_first_party_player_advanced_stats_dataset,
    get_first_party_team_advanced_stats_dataset,
)

REPORT_PATH = Path("step7g-step4f-advanced-derivation-probe.json")
PLAYER_ID = 1642785
TEAM_KEY = "washington-mystics"
OPPONENT_KEY = "phoenix-mercury"
SEASON = 2026
LAST_N = 5

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
        raise RuntimeError("Step 4F derivation probe refuses production-enabled environment: " + ", ".join(bad))
    if _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Direct Step 4F derivation probe requires Step 7G integration OFF.")


def _advanced_row(dataset: dict[str, Any], collection: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = dataset.get(collection)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise AssertionError(f"Expected exactly one {collection} row")
    adv = rows[0].get("advanced")
    if not isinstance(adv, dict):
        raise AssertionError(f"{collection} row is missing advanced metrics")
    return rows[0], adv


def _metric_summary(adv: dict[str, Any]) -> dict[str, Any]:
    non_null = sorted(key for key, value in adv.items() if value is not None)
    null = sorted(key for key, value in adv.items() if value is None)
    return {
        "non_null_fields": non_null,
        "null_fields": null,
        "non_null_count": len(non_null),
        "estimated_pace_positive": isinstance(adv.get("estimated_pace"), (int, float)) and adv["estimated_pace"] > 0,
        "true_shooting_present": adv.get("true_shooting_percentage") is not None,
        "effective_field_goal_present": adv.get("effective_field_goal_percentage") is not None,
        "pie_present": adv.get("player_impact_estimate") is not None,
    }


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    player = get_first_party_player_advanced_stats_dataset(
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N,
        per_mode="PerGame",
        player_id=PLAYER_ID,
    )
    team = get_first_party_team_advanced_stats_dataset(
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N,
        per_mode="PerGame",
        team_key=TEAM_KEY,
    )
    opponent = get_first_party_team_advanced_stats_dataset(
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N,
        per_mode="PerGame",
        team_key=OPPONENT_KEY,
    )

    player_row, player_adv = _advanced_row(player, "players")
    team_row, team_adv = _advanced_row(team, "teams")
    opponent_row, opponent_adv = _advanced_row(opponent, "teams")

    assert player_row.get("player_id") == PLAYER_ID
    assert player_row.get("team_key") == TEAM_KEY
    assert team_row.get("team_key") == TEAM_KEY
    assert opponent_row.get("team_key") == OPPONENT_KEY
    for dataset in (player, team, opponent):
        assert dataset.get("last_n_games") == LAST_N
        assert dataset.get("season") == SEASON
        assert dataset.get("season_type") == "Regular Season"
        assert dataset.get("per_mode") == "PerGame"
        assert dataset.get("verification", {}).get("reproducible_advanced_core_present") is True
        assert dataset.get("verification", {}).get("estimated_fields_not_mislabeled_as_official") is True
        assert dataset.get("verification", {}).get("third_party_sources_used") is False
        ids = dataset.get("selected_game_ids")
        assert isinstance(ids, list) and len(ids) == LAST_N and len(ids) == len(set(ids))
        assert all(isinstance(game_id, str) and game_id.startswith("10226") for game_id in ids)

    assert player_adv.get("estimated_usage_percentage") is not None
    assert player_adv.get("usage_percentage") is None
    assert player_adv.get("offensive_rating") is None
    assert player_adv.get("defensive_rating") is None
    for adv in (team_adv, opponent_adv):
        assert adv.get("estimated_offensive_rating") is not None
        assert adv.get("estimated_defensive_rating") is not None
        assert adv.get("estimated_net_rating") is not None
        assert adv.get("offensive_rating") is None
        assert adv.get("defensive_rating") is None
        assert adv.get("pace") is None

    report = {
        "data_type": "wnba_step7g_step4f_advanced_derivation_probe_v1",
        "result": "LIVE_FIRST_PARTY_BOX_DERIVATION_READY_FOR_STEP4F_INTEGRATION",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "player": {
            "player_id": PLAYER_ID,
            "team_key": player_row.get("team_key"),
            "selected_game_ids": player.get("selected_game_ids"),
            "metric_summary": _metric_summary(player_adv),
            "identity_rows": len(player.get("identity_evidence") or []),
        },
        "team": {
            "team_key": TEAM_KEY,
            "selected_game_ids": team.get("selected_game_ids"),
            "metric_summary": _metric_summary(team_adv),
        },
        "opponent": {
            "team_key": OPPONENT_KEY,
            "selected_game_ids": opponent.get("selected_game_ids"),
            "metric_summary": _metric_summary(opponent_adv),
        },
        "semantics": {
            "estimated_ratings_labeled_estimated": True,
            "unavailable_official_on_court_metrics_left_null": True,
            "derived_only_from_official_box_counts": True,
            "no_projection_values": True,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
            "step7g_integration_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
