"""OFF-only live certification of promoted Step 7G first-party Step-4F advanced context.

The cert selects a real future 2026 WNBA pregame player, directly exercises the
three advanced datasets consumed by frozen Step 4W, validates frozen units and
identity, then calls the real public FastAPI Step-4X readiness endpoint with no
query overrides. Success requires ``advanced_context_coverage=pass``, existing
shot context to remain pass, zero blockers, projection start permission, and the
Step 7G integration to expose Advanced as formally certified rather than a
candidate.

Officiating may remain an optional warning during this isolated Step-4F cert.
No production/scheduler/feed/persistence switch may be enabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step7g_first_party_advanced_stats_contract_safe import (
    get_first_party_player_advanced_stats_dataset,
    get_first_party_team_advanced_stats_dataset,
)

REPORT_PATH = Path("step7g-step4f-advanced-context-cert.json")
SEASON = 2026
LAST_N_GAMES = 5
EXPECTED_INTEGRATION_VERSION = "wnba_step_7g_first_party_core_integration_v10_advanced_certified"
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)
_FRACTION_FIELDS = (
    "assist_percentage",
    "estimated_offensive_rebound_percentage",
    "estimated_defensive_rebound_percentage",
    "estimated_rebound_percentage",
    "estimated_turnover_percentage",
    "effective_field_goal_percentage",
    "true_shooting_percentage",
    "player_impact_estimate",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError(
            "Step 4F cert refuses to run with production switches enabled: "
            + ", ".join(bad)
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 4F cert requires Step 7G first-party mode ON in CI.")


def _check_by_id(body: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = body.get("checks")
    if not isinstance(checks, list):
        return None
    for row in checks:
        if isinstance(row, dict) and row.get("check_id") == check_id:
            return row
    return None


def _one_row(dataset: dict[str, Any], collection: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = dataset.get(collection)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError(f"Step 4F direct component expected exactly one {collection} row.")
    advanced = rows[0].get("advanced")
    if not isinstance(advanced, dict):
        raise RuntimeError(f"Step 4F direct {collection} row is missing advanced metrics.")
    return rows[0], advanced


def _assert_regular_ids(dataset: dict[str, Any], label: str) -> list[str]:
    ids = dataset.get("selected_game_ids")
    if not isinstance(ids, list) or len(ids) != LAST_N_GAMES or len(ids) != len(set(ids)):
        raise RuntimeError(f"{label} did not expose exactly {LAST_N_GAMES} unique game IDs.")
    if not all(
        isinstance(game_id, str)
        and len(game_id) == 10
        and game_id.isdigit()
        and game_id.startswith("10226")
        for game_id in ids
    ):
        raise RuntimeError(f"{label} admitted a non-certified regular-season game ID.")
    return ids


def _assert_fraction_units(advanced: dict[str, Any], *, include_usage: bool, label: str) -> None:
    fields = list(_FRACTION_FIELDS)
    if include_usage:
        fields.append("estimated_usage_percentage")
    for field in fields:
        value = advanced.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(f"{label}.{field} is not numeric.")
        if not 0.0 <= float(value) <= 1.0:
            raise RuntimeError(f"{label}.{field} is outside frozen fraction units: {value}.")


def _component_summary(dataset: dict[str, Any], advanced: dict[str, Any]) -> dict[str, Any]:
    verification = dataset.get("verification") or {}
    return {
        "data_type": dataset.get("data_type"),
        "source_variant": dataset.get("source_variant"),
        "window_scope": dataset.get("window_scope"),
        "selected_game_ids": dataset.get("selected_game_ids"),
        "non_null_advanced_fields": sorted(
            key for key, value in advanced.items() if value is not None
        ),
        "null_advanced_fields": sorted(
            key for key, value in advanced.items() if value is None
        ),
        "frozen_percentage_units_verified": verification.get(
            "frozen_step4f_percentage_units_verified"
        ),
        "frozen_window_scope_verified": verification.get(
            "frozen_window_scope_spelling_verified"
        ),
        "third_party_sources_used": verification.get("third_party_sources_used"),
        "estimated_fields_not_mislabeled_as_official": verification.get(
            "estimated_fields_not_mislabeled_as_official"
        ),
    }


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    player_id = int(selected_player["player_id"])
    team_key = str(selected_player["team_key"])
    away_key = str(selected_game["away_team_key"])
    home_key = str(selected_game["home_team_key"])
    if team_key == away_key:
        opponent_key = home_key
    elif team_key == home_key:
        opponent_key = away_key
    else:
        raise RuntimeError("Selected player team is not in selected official game.")

    player_dataset = get_first_party_player_advanced_stats_dataset(
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
        per_mode="PerGame",
        player_id=player_id,
    )
    team_dataset = get_first_party_team_advanced_stats_dataset(
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
        per_mode="PerGame",
        team_key=team_key,
    )
    opponent_dataset = get_first_party_team_advanced_stats_dataset(
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
        per_mode="PerGame",
        team_key=opponent_key,
    )

    player_row, player_advanced = _one_row(player_dataset, "players")
    team_row, team_advanced = _one_row(team_dataset, "teams")
    opponent_row, opponent_advanced = _one_row(opponent_dataset, "teams")

    if player_dataset.get("data_type") != "official_advanced_player_stats":
        raise RuntimeError("Player advanced component returned wrong frozen contract type.")
    if team_dataset.get("data_type") != "official_advanced_team_stats":
        raise RuntimeError("Team advanced component returned wrong frozen contract type.")
    if opponent_dataset.get("data_type") != "official_advanced_team_stats":
        raise RuntimeError("Opponent advanced component returned wrong frozen contract type.")
    if player_row.get("player_id") != player_id:
        raise RuntimeError("Player advanced component returned conflicting player ID.")
    if player_row.get("team_key") != team_key:
        raise RuntimeError(
            f"Player advanced latest team {player_row.get('team_key')!r} does not match selected pregame team {team_key!r}."
        )
    if team_row.get("team_key") != team_key:
        raise RuntimeError("Team advanced component returned conflicting focal team key.")
    if opponent_row.get("team_key") != opponent_key:
        raise RuntimeError("Opponent advanced component returned conflicting opponent team key.")

    for label, dataset in (
        ("player", player_dataset),
        ("team", team_dataset),
        ("opponent", opponent_dataset),
    ):
        if dataset.get("season") != SEASON:
            raise RuntimeError(f"{label} advanced component returned wrong season.")
        if dataset.get("season_type") != "Regular Season":
            raise RuntimeError(f"{label} advanced component returned wrong season type.")
        if dataset.get("per_mode") != "PerGame":
            raise RuntimeError(f"{label} advanced component returned wrong per_mode.")
        if dataset.get("last_n_games") != LAST_N_GAMES:
            raise RuntimeError(f"{label} advanced component returned wrong recent window.")
        if dataset.get("window_scope") != "last_5_games":
            raise RuntimeError(f"{label} advanced component broke frozen window_scope.")
        verification = dataset.get("verification") or {}
        for key in (
            "reproducible_advanced_core_present",
            "estimated_fields_not_mislabeled_as_official",
            "frozen_step4f_percentage_units_verified",
            "frozen_window_scope_spelling_verified",
        ):
            if verification.get(key) is not True:
                raise RuntimeError(f"{label} advanced verification flag {key} is not true.")
        if verification.get("third_party_sources_used") is not False:
            raise RuntimeError(f"{label} advanced component used a non-first-party source.")
        _assert_regular_ids(dataset, label)

    _assert_fraction_units(player_advanced, include_usage=True, label="player")
    _assert_fraction_units(team_advanced, include_usage=False, label="team")
    _assert_fraction_units(opponent_advanced, include_usage=False, label="opponent")
    if player_advanced.get("estimated_usage_percentage") is None:
        raise RuntimeError("Player advanced component lacks reproducible estimated usage.")
    if player_advanced.get("usage_percentage") is not None:
        raise RuntimeError("Player advanced component incorrectly claimed official on-court usage.")
    if player_advanced.get("offensive_rating") is not None or player_advanced.get("defensive_rating") is not None:
        raise RuntimeError("Player advanced component incorrectly claimed official on-court ratings.")
    for label, advanced in (("team", team_advanced), ("opponent", opponent_advanced)):
        for field in (
            "estimated_offensive_rating",
            "estimated_defensive_rating",
            "estimated_net_rating",
            "estimated_pace",
        ):
            if advanced.get(field) is None:
                raise RuntimeError(f"{label} advanced component is missing {field}.")
        if advanced.get("offensive_rating") is not None or advanced.get("defensive_rating") is not None:
            raise RuntimeError(f"{label} advanced component incorrectly claimed official on-court ratings.")
        if advanced.get("pace") is not None:
            raise RuntimeError(f"{label} advanced component incorrectly claimed official pace.")

    # Import the app only after direct first-party validation so the default-OFF
    # integration installs certified Step-4F seams before router binding.
    from sports_api.main import app
    import sports_api.wnba_step7g_first_party_integration as integration

    status = integration.get_step7g_first_party_status()
    if not status.get("all_core_seams_installed"):
        raise RuntimeError("Step 7G integration seams were not fully installed.")
    seams = status.get("seams") or {}
    if seams.get("projection_player_advanced_context") is not True:
        raise RuntimeError("Step 4W player-advanced seam is not installed.")
    if seams.get("projection_team_advanced_context") is not True:
        raise RuntimeError("Step 4W team-advanced seam is not installed.")
    if status.get("model_version") != EXPECTED_INTEGRATION_VERSION:
        raise RuntimeError(
            f"Step 4F integration version is not the promoted certified version: {status.get('model_version')!r}."
        )
    if status.get("certified_scope", {}).get("advanced_context") is not True:
        raise RuntimeError("Step 4F is not formally marked certified after the live promotion.")
    if status.get("candidate_scope", {}).get("advanced_context") is not None:
        raise RuntimeError("Step 4F still appears in candidate scope after certification.")
    if status.get("certified_scope", {}).get("current_availability_coordinate_parser") is not True:
        raise RuntimeError("Current coordinate-safe Step 4I parser is not marked certified.")

    game_id = str(selected_game["game_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(path)
    try:
        body = response.json()
    except Exception:
        body = {"raw_body_prefix": response.text[:1000]}

    if response.status_code != 200:
        raise RuntimeError(f"Real Step 4X default endpoint returned HTTP {response.status_code}.")
    if not isinstance(body, dict):
        raise RuntimeError("Real Step 4X default endpoint returned a non-object payload.")
    advanced_check = _check_by_id(body, "advanced_context_coverage")
    shot_check = _check_by_id(body, "shot_context_coverage")
    availability_check = _check_by_id(body, "current_availability_available")
    if not isinstance(advanced_check, dict) or advanced_check.get("severity") != "pass":
        raise RuntimeError(f"advanced_context_coverage did not pass: {advanced_check!r}")
    requested = (advanced_check.get("observed") or {}).get("requested")
    if requested != ["player_advanced", "team_advanced", "opponent_advanced"]:
        raise RuntimeError(f"Advanced coverage request set changed unexpectedly: {requested!r}")
    if not isinstance(shot_check, dict) or shot_check.get("severity") != "pass":
        raise RuntimeError(f"Previously certified shot_context_coverage regressed: {shot_check!r}")
    if not isinstance(availability_check, dict) or availability_check.get("severity") != "pass":
        raise RuntimeError(f"Previously certified current availability regressed: {availability_check!r}")

    summary = body.get("summary") or {}
    if summary.get("blocker_count") != 0:
        raise RuntimeError(f"Step 4X still has blockers: {summary!r}")
    if body.get("can_start_projection") is not True:
        raise RuntimeError("Step 4X did not allow projection start after Step 4F certification.")
    warning_ids = summary.get("warning_ids") or []
    if "advanced_context_coverage" in warning_ids:
        raise RuntimeError("Advanced context still appears in warning IDs after pass.")

    report = {
        "data_type": "wnba_step7g_step4f_first_party_advanced_context_cert_v2",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": selected_game,
        "selected_player": selected_player,
        "opponent_team_key": opponent_key,
        "direct_components": {
            "player": _component_summary(player_dataset, player_advanced),
            "team": _component_summary(team_dataset, team_advanced),
            "opponent": _component_summary(opponent_dataset, opponent_advanced),
        },
        "fastapi": {
            "endpoint": path,
            "request_query_overrides": {},
            "http_status": response.status_code,
            "readiness": body.get("readiness"),
            "can_start_projection": body.get("can_start_projection"),
            "summary": summary,
            "advanced_context_check": advanced_check,
            "shot_context_check": shot_check,
            "current_availability_check": availability_check,
            "warning_ids": warning_ids,
        },
        "integration_status": status,
        "certification_result": "STEP4F_FIRST_PARTY_ADVANCED_CONTEXT_PROMOTED_AND_LIVE_CERTIFIED",
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "step7g_first_party_enabled_for_ci_process_only": True,
            "frozen_step4f_modified": False,
            "frozen_step4w_modified": False,
            "frozen_step4x_modified": False,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
