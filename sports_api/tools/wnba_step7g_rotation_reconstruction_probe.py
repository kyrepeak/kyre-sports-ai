"""Certify whether official WNBA liveData can reconstruct exact rotation stints.

This diagnostic uses only first-party WNBA liveData:
- completed-game box score for official starter flags and final player minutes
- completed-game play-by-play for official substitution timestamps/descriptions

It replays each team's substitutions from the five official starters, measures
tracked seconds for every player, and rejects any inconsistency. No production
provider is changed and no betting/model state is touched.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from sports_api.wnba_live_game import (
    get_live_game_state_dataset,
    get_play_by_play_dataset,
)

GAME_ID = "1022600288"
SEASON = 2026
REPORT_PATH = Path("step7g-rotation-reconstruction-probe.json")
OFF_ENV = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)
SUB_RE = re.compile(r"^SUB:\s*(.+?)\s+FOR\s+(.+?)\s*$", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _starter(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y"}


def _minutes_seconds(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.fullmatch(
        r"PT(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?",
        text,
        re.I,
    )
    if not match:
        return None
    return round(
        float(match.group("h") or 0) * 3600
        + float(match.group("m") or 0) * 60
        + float(match.group("s") or 0),
        3,
    )


def _norm_name(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    return re.sub(r"\s+", " ", text)


def _period_length(period: int) -> float:
    return 600.0 if period <= 4 else 300.0


def _game_end(actions: list[dict[str, Any]], state: dict[str, Any]) -> float:
    periods = [int(action["period"]) for action in actions if action.get("period")]
    state_period = state.get("period")
    if isinstance(state_period, int) and state_period > 0:
        periods.append(state_period)
    final_period = max(periods or [4])
    return sum(_period_length(period) for period in range(1, final_period + 1))


def _player_lookup(players: list[dict[str, Any]]) -> dict[str, list[int]]:
    lookup: dict[str, list[int]] = {}
    for player in players:
        player_id = player.get("player_id")
        if not isinstance(player_id, int):
            continue
        forms = {
            _norm_name(player.get("family_name")),
            _norm_name(player.get("name")),
            _norm_name(
                " ".join(
                    value for value in (
                        str(player.get("first_name") or "").strip(),
                        str(player.get("family_name") or "").strip(),
                    ) if value
                )
            ),
        }
        for form in forms:
            if form:
                lookup.setdefault(form, []).append(player_id)
    return lookup


def _resolve_incoming(label: str, lookup: dict[str, list[int]]) -> tuple[int | None, str]:
    key = _norm_name(label)
    direct = sorted(set(lookup.get(key, [])))
    if len(direct) == 1:
        return direct[0], "exact_name"
    suffix = sorted({
        player_id
        for name, ids in lookup.items()
        if name.endswith(" " + key) or name == key
        for player_id in ids
    })
    if len(suffix) == 1:
        return suffix[0], "unique_family_suffix"
    return None, "unresolved_or_ambiguous"


def _simulate_side(
    side: str,
    team: dict[str, Any],
    actions: list[dict[str, Any]],
    game_end: float,
) -> dict[str, Any]:
    players = [player for player in team.get("players", []) if isinstance(player, dict)]
    starters = [player["player_id"] for player in players if _starter(player.get("starter"))]
    lookup = _player_lookup(players)
    official_seconds = {
        player["player_id"]: _minutes_seconds(player.get("statistics", {}).get("minutes"))
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    active_player_ids = {
        player_id for player_id, seconds in official_seconds.items()
        if seconds is not None and seconds > 0
    }
    tracked = {player_id: 0.0 for player_id in official_seconds}
    current = set(starters)
    last_elapsed = 0.0
    substitutions = []
    errors = []
    stint_boundaries: dict[int, list[tuple[float, float]]] = {player_id: [] for player_id in official_seconds}
    open_since = {player_id: 0.0 for player_id in current}

    team_key = team.get("team_key")
    side_actions = [
        action for action in actions
        if action.get("event_category") == "substitution"
        and action.get("team_key") == team_key
    ]

    for action in side_actions:
        elapsed = action.get("elapsed_game_seconds")
        if not isinstance(elapsed, (int, float)):
            errors.append("substitution_missing_elapsed_time")
            continue
        elapsed = float(elapsed)
        if elapsed < last_elapsed - 1e-6:
            errors.append("substitution_time_moved_backward")
            continue
        duration = elapsed - last_elapsed
        for player_id in current:
            tracked[player_id] = tracked.get(player_id, 0.0) + duration
        last_elapsed = elapsed

        description = str(action.get("description") or "").strip()
        match = SUB_RE.match(description)
        if not match:
            errors.append(f"unparsed_substitution:{description}")
            continue
        incoming_label, outgoing_label = match.group(1), match.group(2)
        outgoing_id = action.get("person_id")
        incoming_id, incoming_resolution = _resolve_incoming(incoming_label, lookup)
        if not isinstance(outgoing_id, int):
            errors.append(f"missing_outgoing_id:{description}")
            continue
        if incoming_id is None:
            errors.append(f"unresolved_incoming:{description}")
            continue
        outgoing_name_matches = _norm_name(outgoing_label) in {
            _norm_name(next((p.get("family_name") for p in players if p.get("player_id") == outgoing_id), "")),
            _norm_name(next((p.get("name") for p in players if p.get("player_id") == outgoing_id), "")),
        }
        if outgoing_id not in current:
            errors.append(f"outgoing_not_on_court:{description}:{outgoing_id}")
        if incoming_id in current:
            errors.append(f"incoming_already_on_court:{description}:{incoming_id}")
        if len(current) != 5:
            errors.append(f"pre_sub_lineup_count:{len(current)}")

        if outgoing_id in current:
            current.remove(outgoing_id)
            start = open_since.pop(outgoing_id, None)
            if start is not None:
                stint_boundaries.setdefault(outgoing_id, []).append((start, elapsed))
        current.add(incoming_id)
        open_since[incoming_id] = elapsed

        if len(current) != 5:
            errors.append(f"post_sub_lineup_count:{len(current)}")
        substitutions.append({
            "action_number": action.get("action_number"),
            "elapsed_game_seconds": elapsed,
            "period": action.get("period"),
            "clock": action.get("clock"),
            "description": description,
            "incoming_label": incoming_label,
            "incoming_player_id": incoming_id,
            "incoming_resolution": incoming_resolution,
            "outgoing_label": outgoing_label,
            "outgoing_player_id": outgoing_id,
            "outgoing_name_matches_roster": outgoing_name_matches,
            "lineup_count_after": len(current),
        })

    if game_end < last_elapsed:
        errors.append("game_end_precedes_last_substitution")
    else:
        duration = game_end - last_elapsed
        for player_id in current:
            tracked[player_id] = tracked.get(player_id, 0.0) + duration
        for player_id in list(current):
            start = open_since.pop(player_id, None)
            if start is not None:
                stint_boundaries.setdefault(player_id, []).append((start, game_end))

    comparisons = []
    max_abs_delta = 0.0
    unmatched = []
    for player in players:
        player_id = player.get("player_id")
        if not isinstance(player_id, int):
            continue
        official = official_seconds.get(player_id)
        reconstructed = round(tracked.get(player_id, 0.0), 3)
        delta = None if official is None else round(reconstructed - official, 3)
        if delta is not None:
            max_abs_delta = max(max_abs_delta, abs(delta))
            if abs(delta) > 0.11:
                unmatched.append(player_id)
        comparisons.append({
            "player_id": player_id,
            "player_name": player.get("name") or " ".join(
                value for value in (player.get("first_name"), player.get("family_name")) if value
            ),
            "starter": _starter(player.get("starter")),
            "official_minutes_raw": player.get("statistics", {}).get("minutes"),
            "official_seconds": official,
            "reconstructed_seconds": reconstructed,
            "delta_seconds": delta,
            "stints": [
                {"in_elapsed_seconds": start, "out_elapsed_seconds": end, "duration_seconds": round(end-start, 3)}
                for start, end in stint_boundaries.get(player_id, [])
            ],
        })

    official_total = sum(value for value in official_seconds.values() if value is not None)
    reconstructed_total = sum(tracked.values())
    final_on_court_ids = set(team.get("on_court_player_ids") or [])
    final_on_court_verified = (
        team.get("on_court_exactly_five") is True
        and final_on_court_ids == current
    )

    return {
        "side": side,
        "team_key": team_key,
        "starter_ids": starters,
        "starter_count": len(starters),
        "official_active_player_ids": sorted(active_player_ids),
        "substitution_count": len(side_actions),
        "resolved_substitution_count": len(substitutions),
        "errors": errors,
        "comparisons": comparisons,
        "unmatched_player_ids": unmatched,
        "max_abs_player_minute_delta_seconds": round(max_abs_delta, 3),
        "official_total_player_seconds": round(official_total, 3),
        "reconstructed_total_player_seconds": round(reconstructed_total, 3),
        "expected_five_player_seconds": round(5 * game_end, 3),
        "official_total_matches_five_player_invariant": abs(official_total - 5 * game_end) <= 0.11,
        "reconstructed_total_matches_five_player_invariant": abs(reconstructed_total - 5 * game_end) <= 0.11,
        "final_on_court_player_ids": sorted(final_on_court_ids),
        "reconstructed_final_on_court_player_ids": sorted(current),
        "final_on_court_verified": final_on_court_verified,
        "passed": (
            len(starters) == 5
            and not errors
            and not unmatched
            and abs(official_total - 5 * game_end) <= 0.11
            and abs(reconstructed_total - 5 * game_end) <= 0.11
            and (final_on_court_verified or team.get("on_court_exactly_five") is not True)
        ),
    }


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("Rotation reconstruction probe refused because production is not fully OFF.")

    state_dataset = get_live_game_state_dataset(GAME_ID, SEASON)
    pbp = get_play_by_play_dataset(GAME_ID, SEASON)
    state = state_dataset["state"]
    actions = pbp["actions"]
    game_end = _game_end(actions, state)

    away = _simulate_side("away", state["away"], actions, game_end)
    home = _simulate_side("home", state["home"], actions, game_end)
    passed = (
        state["status"]["category"] == "final"
        and pbp["verification"]["action_ids_unique_when_present"]
        and pbp["verification"]["all_team_events_mapped_to_registry"]
        and away["passed"]
        and home["passed"]
    )

    report = {
        "data_type": "wnba_step7g_rotation_reconstruction_probe",
        "created_at_utc": _now(),
        "read_only": True,
        "game_id": GAME_ID,
        "season": SEASON,
        "production_flags_off": off_state,
        "source": "WNBA Official Live Data",
        "source_urls": {
            "box_score": state_dataset["source_url"],
            "play_by_play": pbp["source_url"],
        },
        "status": state["status"],
        "game_end_elapsed_seconds": game_end,
        "play_by_play_action_count": pbp["source_action_count"],
        "away": away,
        "home": home,
        "decision": {
            "single_game_exact_minute_reconciliation_passed": passed,
            "rotation_boundaries_deterministic_from_official_starters_and_substitutions": passed,
            "stats_gamerotation_endpoint_required_for_boundaries": False if passed else None,
            "multi_game_certification_required_before_provider_integration": True,
            "production_activation_allowed": False,
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "passed": passed,
        "away_passed": away["passed"],
        "home_passed": home["passed"],
        "away_max_delta_seconds": away["max_abs_player_minute_delta_seconds"],
        "home_max_delta_seconds": home["max_abs_player_minute_delta_seconds"],
        "away_substitutions": away["substitution_count"],
        "home_substitutions": home["substitution_count"],
        "production_activation_allowed": False,
    }, sort_keys=True))

    if not passed:
        raise RuntimeError("Official WNBA liveData did not reconcile to exact player minutes for the target game.")


if __name__ == "__main__":
    main()
