"""Read-only Step 7G probe of Step 4N season-schedule identity edge cases."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_schedule as frozen_schedule
from sports_api.wnba_step7g_first_party_schedule import _fetch_first_party_schedule_payload

SEASON = 2026
REPORT_PATH = Path("step7g-step4n-schedule-integrity-probe.json")
OFF_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _assert_off() -> None:
    enabled = [
        key for key in OFF_KEYS
        if str(os.getenv(key, "false")).strip().casefold() not in {"", "0", "false", "no", "off"}
    ]
    if enabled:
        raise RuntimeError("Production switch enabled: " + ", ".join(enabled))


def _team_view(team: Any) -> dict[str, Any]:
    team = team if isinstance(team, dict) else {}
    return {
        "official_team_id": team.get("official_team_id"),
        "team_key": team.get("team_key"),
        "full_name": team.get("full_name"),
        "source_name": team.get("source_name"),
        "source_city": team.get("source_city"),
        "source_tricode": team.get("source_tricode"),
        "mapped_to_registry": bool(team.get("mapped_to_registry")),
    }


def main() -> int:
    _assert_off()
    payload, retrieved, variant, source_url, cache_hit = _fetch_first_party_schedule_payload(SEASON)
    root = frozen_schedule._schedule_root(payload)
    rows: list[dict[str, Any]] = []
    one_sided: list[dict[str, Any]] = []
    both_unmapped: list[dict[str, Any]] = []
    both_mapped = 0

    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        date = frozen_schedule._date_block_iso(block.get("gameDate"))
        if date is None:
            continue
        for raw in block.get("games", []) if isinstance(block.get("games"), list) else []:
            if not isinstance(raw, dict):
                continue
            game = frozen_schedule._normalize_game(raw, date, SEASON)
            away = _team_view(game.get("away"))
            home = _team_view(game.get("home"))
            item = {
                "game_id": game.get("game_id"),
                "date": date,
                "status": game.get("status"),
                "competition": game.get("competition"),
                "venue": game.get("venue"),
                "away": away,
                "home": home,
                "raw_identity_fields": {
                    "gameLabel": raw.get("gameLabel"),
                    "gameSubLabel": raw.get("gameSubLabel"),
                    "gameSubtype": raw.get("gameSubtype"),
                    "seriesText": raw.get("seriesText"),
                    "weekName": raw.get("weekName"),
                    "isNeutral": raw.get("isNeutral"),
                },
            }
            rows.append(item)
            mapped = int(away["mapped_to_registry"]) + int(home["mapped_to_registry"])
            if mapped == 2:
                both_mapped += 1
            elif mapped == 1:
                one_sided.append(item)
            else:
                both_unmapped.append(item)

    report = {
        "data_type": "wnba_step7g_step4n_schedule_integrity_probe_v1",
        "season": SEASON,
        "retrieved_at_utc": retrieved,
        "probed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "source_variant": variant,
        "cache_hit": cache_hit,
        "counts": {
            "total_normalized_games": len(rows),
            "both_mapped_games": both_mapped,
            "one_sided_unmapped_games": len(one_sided),
            "both_unmapped_games": len(both_unmapped),
        },
        "one_sided_unmapped_games": one_sided,
        "both_unmapped_games": both_unmapped,
        "step4n_frozen_semantics": {
            "both_mapped": "included",
            "both_unmapped": "excluded as possible non-franchise event",
            "one_sided_unmapped": "blocking upstream error",
            "validation_loosened": False,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_off()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
