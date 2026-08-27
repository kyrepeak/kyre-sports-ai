"""Sanitized probe of WNBA.com first-party shot-action fields for Step 7G."""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step7g_first_party_history import (
    get_first_party_player_recent_game_log_dataset,
    get_first_party_play_by_play_dataset,
)

REPORT_PATH = Path("step7g-shot-surface-probe.json")
SEASON = 2026
PLAYER_ID = 1642785
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
        raise RuntimeError("Shot-surface probe refuses to run with production switches enabled: " + ", ".join(bad))


def main() -> int:
    _assert_safe()
    history = get_first_party_player_recent_game_log_dataset(PLAYER_ID, SEASON)
    games = history.get("games") or []
    if not games:
        raise RuntimeError("No recent first-party player games were available for shot-surface probe.")
    game_id = str(games[0]["game_id"])
    pbp = get_first_party_play_by_play_dataset(game_id, SEASON, event_category="shot")
    actions = [row for row in pbp.get("actions", []) if isinstance(row, dict)]
    if not actions:
        raise RuntimeError("No first-party shot actions were exposed for probe game.")

    def present(key: str) -> int:
        return sum(row.get(key) is not None for row in actions)

    combo_counts = Counter(
        (
            str(row.get("action_type") or ""),
            str(row.get("sub_type") or ""),
            str(row.get("location") or ""),
            tuple(str(x) for x in (row.get("qualifiers") or [])),
        )
        for row in actions
    )
    samples = []
    for row in actions[:24]:
        samples.append({
            "action_type": row.get("action_type"),
            "sub_type": row.get("sub_type"),
            "shot_result": row.get("shot_result"),
            "shot_distance_feet": row.get("shot_distance_feet"),
            "x_legacy": row.get("x_legacy"),
            "y_legacy": row.get("y_legacy"),
            "location": row.get("location"),
            "qualifiers": row.get("qualifiers"),
            "points_total": row.get("points_total"),
            "description": row.get("description"),
        })

    report = {
        "data_type": "wnba_step7g_shot_surface_probe_v1",
        "season": SEASON,
        "player_id": PLAYER_ID,
        "game_id": game_id,
        "shot_action_count": len(actions),
        "field_presence": {
            key: present(key)
            for key in (
                "action_type", "sub_type", "shot_result", "shot_distance_feet",
                "x_legacy", "y_legacy", "location", "qualifiers", "points_total",
                "person_id", "team_key",
            )
        },
        "action_surface_counts": [
            {
                "action_type": key[0],
                "sub_type": key[1],
                "location": key[2],
                "qualifiers": list(key[3]),
                "count": count,
            }
            for key, count in combo_counts.most_common()
        ],
        "samples": samples,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
