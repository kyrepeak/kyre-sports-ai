"""OFF-only live certification for the Step-8B neutral deterministic projection core."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step8_core_projection import (
    MODEL_VERSION,
    SCHEMA_VERSION,
    get_player_game_step8_core_projection,
    step8_core_projection_enabled,
)

REPORT_PATH = Path("step8b-core-projection-cert.json")
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
        raise RuntimeError("Step 8B core cert refuses production switches: " + ", ".join(bad))
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 8B core cert requires Step 7G first-party mode in isolated CI.")
    if not _truthy(os.getenv("WNBA_STEP8_PROJECTION_HANDOFF_ENABLED")):
        raise RuntimeError("Step 8B core cert requires Step 8A handoff mode in isolated CI.")
    if not step8_core_projection_enabled():
        raise RuntimeError("Step 8B core cert requires the isolated core-projection flag.")


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Step 8B core cert expected numeric {label}.")
    return float(value)


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])

    result = get_player_game_step8_core_projection(player_id, game_id)
    if result.get("data_type") != "neutral_deterministic_player_projection":
        raise RuntimeError("Step 8B core returned wrong data type.")
    if result.get("schema_version") != SCHEMA_VERSION or result.get("model_version") != MODEL_VERSION:
        raise RuntimeError("Step 8B core returned wrong contract/model identity.")
    if result.get("game_id") != game_id or result.get("player_id") != player_id:
        raise RuntimeError("Step 8B core returned wrong requested identity.")

    minutes = _number(result.get("neutral_regulation_minutes_anchor"), "neutral minutes anchor")
    if not 0.0 < minutes <= 40.0:
        raise RuntimeError("Step 8B neutral regulation minutes are out of bounds.")
    rates = result.get("official_per_minute_rates")
    projection = result.get("projection")
    dispersion = result.get("historical_dispersion")
    if not isinstance(rates, dict) or not isinstance(projection, dict) or not isinstance(dispersion, dict):
        raise RuntimeError("Step 8B core output is missing rates/projection/dispersion.")

    for stat in ("points", "rebounds", "assists"):
        rate = _number(rates.get(stat), f"{stat} rate")
        projected = _number(projection.get(stat), f"projected {stat}")
        expected = rate * minutes
        if abs(projected - expected) > 2e-6:
            raise RuntimeError(f"Step 8B {stat} projection does not equal official rate x neutral minutes.")
    component_pra = sum(_number(projection.get(stat), stat) for stat in ("points", "rebounds", "assists"))
    projected_pra = _number(projection.get("points_rebounds_assists"), "projected PRA")
    if abs(component_pra - projected_pra) > 2e-6:
        raise RuntimeError("Step 8B projected PRA does not equal P+R+A.")

    cap_applied = result.get("regulation_cap_applied") is True
    official_mean_minutes = _number(result.get("official_recent_mean_minutes"), "official recent mean minutes")
    if cap_applied:
        if official_mean_minutes <= 40.0 or minutes != 40.0:
            raise RuntimeError("Step 8B regulation cap metadata is inconsistent.")
    else:
        if abs(minutes - official_mean_minutes) > 1e-6:
            raise RuntimeError("Step 8B neutral minutes do not equal official recent mean when uncapped.")
        for stat in ("points", "rebounds", "assists", "points_rebounds_assists"):
            recent_mean = _number((dispersion.get(stat) or {}).get("recent_mean"), f"recent {stat} mean")
            projected = _number(projection.get(stat), f"projected {stat}")
            if abs(projected - recent_mean) > 2e-5:
                raise RuntimeError(f"Step 8B uncapped neutral {stat} projection should reproduce official recent mean.")

    availability = result.get("current_availability") or {}
    rotation = result.get("rotation_alignment") or {}
    provenance = result.get("provenance") or {}
    semantics = result.get("semantics") or {}
    guardrails = result.get("guardrails") or {}
    verification = result.get("verification") or {}
    if availability.get("current_roster_match") is not True or availability.get("availability_blocking") is not False:
        raise RuntimeError("Step 8B current availability guard did not pass.")
    if abs(_number(rotation.get("box_rotation_mean_minutes_difference"), "box/rotation minute difference")) > 0.02:
        raise RuntimeError("Step 8B box/rotation minute reconciliation exceeded tolerance.")
    if provenance.get("official_box_baseline_hash_recomputed") is not True:
        raise RuntimeError("Step 8B did not independently re-hash its official baseline.")
    for key in (
        "projection_is_neutral_recent_form_anchor",
        "minutes_anchor_is_recent_official_box_mean",
        "points_rebounds_assists_use_complete_official_box_rates",
        "pbp_feature_counts_are_not_used_as_box_stat_baseline",
    ):
        if semantics.get(key) is not True:
            raise RuntimeError(f"Step 8B core semantic guard {key!r} is not true.")
    for key in (
        "current_matchup_adjustment_applied",
        "current_role_adjustment_applied",
        "current_injury_minutes_adjustment_applied",
        "teammate_opportunity_redistribution_applied",
    ):
        if semantics.get(key) is not False:
            raise RuntimeError(f"Step 8B core applied forbidden early adjustment {key!r}.")
    for key in (
        "no_matchup_adjustment_created",
        "no_role_redistribution_created",
        "no_projected_starter_created",
        "no_monte_carlo_created",
        "no_sportsbook_data_created",
        "no_betting_probability_created",
        "no_persistence_created",
    ):
        if guardrails.get(key) is not True:
            raise RuntimeError(f"Step 8B core guardrail {key!r} is not true.")
    for key in (
        "step8a_handoff_projection_authorized",
        "step8b_official_baseline_hash_verified",
        "step8b_official_baseline_identity_verified",
        "official_box_rotation_minutes_aligned",
        "current_roster_identity_verified",
        "current_availability_not_blocking",
        "component_pra_rate_consistency_verified",
    ):
        if verification.get(key) is not True:
            raise RuntimeError(f"Step 8B core verification {key!r} is not true.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError("Step 8B core unexpectedly used third-party sources.")

    report = {
        "data_type": "wnba_step8b_core_projection_cert_v1",
        "certification_result": "STEP8B_NEUTRAL_DETERMINISTIC_CORE_LIVE_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "projection": {
            "projection_id": result.get("projection_id"),
            "projection_content_sha256": result.get("projection_content_sha256"),
            "model_version": result.get("model_version"),
            "neutral_regulation_minutes_anchor": minutes,
            "official_recent_mean_minutes": official_mean_minutes,
            "regulation_cap_applied": cap_applied,
            "points": projection.get("points"),
            "rebounds": projection.get("rebounds"),
            "assists": projection.get("assists"),
            "points_rebounds_assists": projection.get("points_rebounds_assists"),
        },
        "provenance": {
            "step8a_handoff_id": provenance.get("step8a_handoff_id"),
            "step8b_baseline_id": provenance.get("step8b_baseline_id"),
            "step8b_baseline_content_sha256": provenance.get("step8b_baseline_content_sha256"),
            "official_box_baseline_hash_recomputed": True,
        },
        "rotation_alignment": rotation,
        "current_availability": availability,
        "safety": {
            "deterministic_projection_created": True,
            "matchup_adjustment_created": False,
            "role_redistribution_created": False,
            "monte_carlo_created": False,
            "sportsbook_called": False,
            "betting_probability_created": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8B_NEUTRAL_DETERMINISTIC_CORE_LIVE_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
