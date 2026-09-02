"""OFF-only live certification of Step 7G first-party Step-4O officiating context.

The cert selects a real future 2026 WNBA pregame player, directly validates the
first-party current-game official assignment plus exact paired-box team whistle
environment, then calls the real public FastAPI Step-4X readiness endpoint with
no query overrides. Candidate success requires officiating, shot, advanced, and
current-availability coverage to pass, zero blockers, and projection-start
permission. The integration certification flag intentionally remains false until
a later promotion/seal commit.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step7g_first_party_officiating import (
    SOURCE_VARIANT,
    get_first_party_game_whistle_context,
)

REPORT_PATH = Path("step7g-step4o-officiating-context-cert.json")
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


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError(
            "Step 4O cert refuses to run with production switches enabled: "
            + ", ".join(bad)
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 4O cert requires Step 7G first-party mode ON in CI.")


def _check_by_id(body: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = body.get("checks")
    if not isinstance(checks, list):
        return None
    for row in checks:
        if isinstance(row, dict) and row.get("check_id") == check_id:
            return row
    return None


def _numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Step 4O {label} is not numeric: {value!r}.")
    return float(value)


def _assert_regular_ids(context: dict[str, Any], label: str) -> list[str]:
    ids = context.get("selected_game_ids")
    if not isinstance(ids, list) or len(ids) != LAST_N_GAMES:
        raise RuntimeError(f"{label} whistle context did not expose exactly five history IDs.")
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{label} whistle context contains duplicate history game IDs.")
    if not all(
        isinstance(game_id, str)
        and len(game_id) == 10
        and game_id.isdigit()
        and game_id.startswith("10226")
        for game_id in ids
    ):
        raise RuntimeError(f"{label} whistle context admitted a non-certified game ID.")
    return ids


def _assert_team_context(
    context: dict[str, Any],
    *,
    expected_team_key: str,
    label: str,
) -> dict[str, Any]:
    if context.get("data_type") != "observed_team_foul_free_throw_context":
        raise RuntimeError(f"{label} returned wrong team context data type.")
    team = context.get("team")
    profile = context.get("profile")
    league_context = context.get("league_context")
    verification = context.get("verification")
    if not isinstance(team, dict) or team.get("team_key") != expected_team_key:
        raise RuntimeError(f"{label} team identity disagrees with selected game.")
    if not isinstance(profile, dict):
        raise RuntimeError(f"{label} profile is missing.")
    if not isinstance(league_context, dict):
        raise RuntimeError(f"{label} league context is missing.")
    if not isinstance(verification, dict):
        raise RuntimeError(f"{label} verification is missing.")

    for field in (
        "minutes",
        "field_goals_attempted",
        "free_throws_made",
        "free_throws_attempted",
        "personal_fouls",
        "personal_fouls_drawn",
        "points",
    ):
        _numeric(profile.get(field), f"{label}.profile.{field}")
    ft_pct = profile.get("free_throw_percentage")
    if ft_pct is not None and not 0.0 <= _numeric(ft_pct, f"{label}.profile.free_throw_percentage") <= 1.0:
        raise RuntimeError(f"{label} free-throw percentage is outside fraction units.")
    if abs(_numeric(profile.get("minutes"), f"{label}.minutes") - 40.0) > 5.01:
        raise RuntimeError(f"{label} team-clock minutes are implausible for recent WNBA games.")

    for key in (
        "personal_fouls_drawn_equals_paired_opponent_personal_fouls",
        "team_clock_minutes_normalized_from_five_player_box_total",
    ):
        if verification.get(key) is not True:
            raise RuntimeError(f"{label} verification flag {key} is not true.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError(f"{label} whistle context used a third-party source.")

    for metric in (
        "free_throws_attempted_per_game",
        "personal_fouls_per_game",
        "personal_fouls_drawn_per_game",
    ):
        row = league_context.get(metric)
        if not isinstance(row, dict):
            raise RuntimeError(f"{label}.{metric} league measure is missing.")
        _numeric(row.get("value"), f"{label}.{metric}.value")
        _numeric(row.get("league_average"), f"{label}.{metric}.league_average")
        rank = row.get("higher_value_rank")
        count = row.get("league_team_count")
        if not isinstance(rank, int) or not 1 <= rank <= 15:
            raise RuntimeError(f"{label}.{metric} rank is invalid: {rank!r}.")
        if count != 15:
            raise RuntimeError(f"{label}.{metric} league count is not 15: {count!r}.")

    _assert_regular_ids(context, label)
    return profile


def _assert_official_assignment(
    assignment: dict[str, Any],
    *,
    game_id: str,
    away_key: str,
    home_key: str,
) -> None:
    if assignment.get("data_type") != "official_game_official_assignment":
        raise RuntimeError("Step 4O official assignment returned wrong data type.")
    if assignment.get("game_id") != game_id:
        raise RuntimeError("Step 4O official assignment returned wrong game ID.")
    if (assignment.get("away") or {}).get("team_key") != away_key:
        raise RuntimeError("Step 4O official assignment returned wrong away team.")
    if (assignment.get("home") or {}).get("team_key") != home_key:
        raise RuntimeError("Step 4O official assignment returned wrong home team.")
    officials = assignment.get("officials")
    if not isinstance(officials, list) or not officials:
        raise RuntimeError("Step 4O pregame official assignment is not published.")
    if assignment.get("official_count") != len(officials):
        raise RuntimeError("Step 4O official_count disagrees with official rows.")
    person_ids: list[int] = []
    for row in officials:
        if not isinstance(row, dict):
            raise RuntimeError("Step 4O official row is malformed.")
        person_id = row.get("person_id")
        name = str(row.get("name") or "").strip()
        if not isinstance(person_id, int) or isinstance(person_id, bool) or person_id <= 0:
            raise RuntimeError(f"Step 4O official person ID is invalid: {person_id!r}.")
        if not name:
            raise RuntimeError("Step 4O official name is blank.")
        person_ids.append(person_id)
    if len(person_ids) != len(set(person_ids)):
        raise RuntimeError("Step 4O official person IDs are not unique.")
    verification = assignment.get("verification") or {}
    if verification.get("current_page_teams_match_certified_schedule") is not True:
        raise RuntimeError("Step 4O current page did not verify against certified schedule.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError("Step 4O official assignment used a third-party source.")
    if verification.get("referee_tendencies_or_bias_inferred") is not False:
        raise RuntimeError("Step 4O improperly inferred referee tendencies or bias.")


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    # Use the nearest valid future pregame case. No minimum buffer is imposed for
    # this isolated context cert because official assignments are a near-tip source.
    selector.MIN_TIP_BUFFER_HOURS = 0.0
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    away_key = str(selected_game["away_team_key"])
    home_key = str(selected_game["home_team_key"])

    whistle = get_first_party_game_whistle_context(
        game_id,
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
    )
    if whistle.get("data_type") != "observed_game_whistle_environment_context":
        raise RuntimeError("Step 4O direct component returned wrong frozen contract type.")
    if whistle.get("game_id") != game_id:
        raise RuntimeError("Step 4O direct component returned wrong game ID.")
    if whistle.get("season") != SEASON or whistle.get("season_type") != "Regular Season":
        raise RuntimeError("Step 4O direct component returned wrong season scope.")
    if whistle.get("last_n_games") != LAST_N_GAMES:
        raise RuntimeError("Step 4O direct component returned wrong recent window.")

    assignment = whistle.get("official_assignment")
    away = whistle.get("away_team_context")
    home = whistle.get("home_team_context")
    combined = whistle.get("combined_observed_team_rates")
    verification = whistle.get("verification")
    adapter = whistle.get("step7g_adapter")
    if not isinstance(assignment, dict):
        raise RuntimeError("Step 4O direct component is missing official assignment.")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise RuntimeError("Step 4O direct component is missing away/home contexts.")
    if not isinstance(combined, dict) or not isinstance(verification, dict):
        raise RuntimeError("Step 4O direct component is missing combined/verification context.")
    if not isinstance(adapter, dict) or adapter.get("source_variant") != SOURCE_VARIANT:
        raise RuntimeError("Step 4O direct component returned unexpected adapter variant.")

    _assert_official_assignment(
        assignment,
        game_id=game_id,
        away_key=away_key,
        home_key=home_key,
    )
    away_profile = _assert_team_context(
        away,
        expected_team_key=away_key,
        label="away",
    )
    home_profile = _assert_team_context(
        home,
        expected_team_key=home_key,
        label="home",
    )

    expected_sum_fta = round(
        _numeric(away_profile["free_throws_attempted"], "away FTA")
        + _numeric(home_profile["free_throws_attempted"], "home FTA"),
        4,
    )
    expected_sum_pf = round(
        _numeric(away_profile["personal_fouls"], "away PF")
        + _numeric(home_profile["personal_fouls"], "home PF"),
        4,
    )
    expected_sum_pfd = round(
        _numeric(away_profile["personal_fouls_drawn"], "away PFD")
        + _numeric(home_profile["personal_fouls_drawn"], "home PFD"),
        4,
    )
    expected_fta_diff = round(
        _numeric(away_profile["free_throws_attempted"], "away FTA")
        - _numeric(home_profile["free_throws_attempted"], "home FTA"),
        4,
    )
    expected = {
        "sum_free_throw_attempts_per_game": expected_sum_fta,
        "sum_personal_fouls_per_game": expected_sum_pf,
        "sum_personal_fouls_drawn_per_game": expected_sum_pfd,
        "away_minus_home_free_throw_attempts_per_game": expected_fta_diff,
    }
    for key, value in expected.items():
        if combined.get(key) != value:
            raise RuntimeError(
                f"Step 4O combined metric {key} disagrees with team profiles: "
                f"{combined.get(key)!r} vs {value!r}."
            )

    for key in (
        "both_team_contexts_match_game",
        "current_game_page_matches_certified_schedule",
        "officials_are_current_game_assignment_only",
        "team_environment_from_completed_games_before_requested_tip",
        "personal_fouls_drawn_derived_only_from_paired_opponent_personal_fouls",
        "combined_rates_are_not_expected_game_totals",
        "no_whistle_probability_created",
    ):
        if verification.get(key) is not True:
            raise RuntimeError(f"Step 4O verification flag {key} is not true.")
    if verification.get("historical_referee_tendencies_included") is not False:
        raise RuntimeError("Step 4O included historical referee tendencies.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError("Step 4O used a third-party source.")

    # Import the app only after direct component validation so the candidate seam
    # is installed before WNBA router functions bind.
    from sports_api.main import app
    import sports_api.wnba_step7g_first_party_integration as integration

    status = integration.get_step7g_first_party_status()
    if not status.get("all_core_seams_installed"):
        raise RuntimeError("Step 7G integration seams were not fully installed.")
    seams = status.get("seams") or {}
    if seams.get("projection_game_whistle_context") is not True:
        raise RuntimeError("Step 4W game-whistle candidate seam is not installed.")
    if integration.projection_snapshot.get_game_whistle_context is not integration.get_first_party_game_whistle_context:
        raise RuntimeError("Step 4W game-whistle provider is not the candidate first-party adapter.")
    if status.get("model_version") != EXPECTED_INTEGRATION_VERSION:
        raise RuntimeError(f"Unexpected integration version: {status.get('model_version')!r}.")
    if status.get("certified_scope", {}).get("officiating_context") is not False:
        raise RuntimeError("Step 4O candidate was prematurely marked certified.")
    candidate = status.get("candidate_scope", {}).get("officiating_context")
    if not isinstance(candidate, str) or not candidate.startswith("candidate_first_party_"):
        raise RuntimeError("Step 4O candidate scope is not explicitly recorded.")
    if status.get("certified_scope", {}).get("advanced_context") is not True:
        raise RuntimeError("Previously certified Step 4F advanced context regressed.")
    if status.get("certified_scope", {}).get("shot_context") is not True:
        raise RuntimeError("Previously certified shot context regressed.")
    if status.get("certified_scope", {}).get("current_availability") is not True:
        raise RuntimeError("Previously certified current availability regressed.")

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

    officiating_check = _check_by_id(body, "officiating_context_coverage")
    advanced_check = _check_by_id(body, "advanced_context_coverage")
    shot_check = _check_by_id(body, "shot_context_coverage")
    availability_check = _check_by_id(body, "current_availability_available")
    for label, check in (
        ("officiating", officiating_check),
        ("advanced", advanced_check),
        ("shot", shot_check),
        ("availability", availability_check),
    ):
        if not isinstance(check, dict) or check.get("severity") != "pass":
            raise RuntimeError(f"{label} readiness check did not pass: {check!r}")
    if (officiating_check.get("observed") or {}).get("requested") != ["game_whistle_context"]:
        raise RuntimeError(f"Officiating coverage request set changed: {officiating_check!r}")

    summary = body.get("summary") or {}
    if summary.get("blocker_count") != 0:
        raise RuntimeError(f"Step 4X has blockers after candidate Step 4O: {summary!r}")
    if body.get("can_start_projection") is not True:
        raise RuntimeError("Step 4X did not allow projection start after candidate Step 4O.")
    warning_ids = summary.get("warning_ids") or []
    if "officiating_context_coverage" in warning_ids:
        raise RuntimeError("Officiating still appears in warning IDs after pass.")

    report = {
        "data_type": "wnba_step7g_step4o_first_party_officiating_candidate_cert_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": selected_game,
        "selected_player": selected_player,
        "direct_component": {
            "game_id": whistle.get("game_id"),
            "source_variant": adapter.get("source_variant"),
            "official_count": assignment.get("official_count"),
            "official_person_ids": [row.get("person_id") for row in assignment.get("officials", [])],
            "official_names": [row.get("name") for row in assignment.get("officials", [])],
            "away_team_key": (away.get("team") or {}).get("team_key"),
            "home_team_key": (home.get("team") or {}).get("team_key"),
            "away_selected_game_ids": away.get("selected_game_ids"),
            "home_selected_game_ids": home.get("selected_game_ids"),
            "away_profile": away_profile,
            "home_profile": home_profile,
            "combined_observed_team_rates": combined,
            "verification": verification,
        },
        "fastapi": {
            "endpoint": path,
            "request_query_overrides": {},
            "http_status": response.status_code,
            "readiness": body.get("readiness"),
            "can_start_projection": body.get("can_start_projection"),
            "summary": summary,
            "officiating_context_check": officiating_check,
            "advanced_context_check": advanced_check,
            "shot_context_check": shot_check,
            "current_availability_check": availability_check,
            "warning_ids": warning_ids,
        },
        "integration_status": status,
        "certification_result": "STEP4O_FIRST_PARTY_OFFICIATING_CANDIDATE_LIVE_CERTIFIED",
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "frozen_step4o_modified": False,
            "frozen_step4w_modified": False,
            "frozen_step4x_modified": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP4O_FIRST_PARTY_OFFICIATING_CANDIDATE_LIVE_CERTIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
