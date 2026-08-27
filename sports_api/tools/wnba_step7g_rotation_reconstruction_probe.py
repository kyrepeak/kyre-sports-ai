"""Certify exact WNBA rotation boundaries from already-certified page data.

The historical liveData box-score URL is not reliably JSON-reachable from our
runner, so this proof intentionally uses the first-party WNBA.com page bridge
that Step 7G has already certified:

- official traditional box score -> starter flags + exact final minutes
- official play-by-play -> every substitution + exact period/clock timestamp

Starting from the five official starters, each substitution is replayed in
source order. The proof fails closed unless the lineup remains exactly five,
every in/out transition is legal, and every reconstructed player second agrees
with the official box score. No production provider is changed here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from sports_api.wnba_step7g_first_party_history import (
    get_first_party_game_box_score_dataset,
    get_first_party_play_by_play_dataset,
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
TOLERANCE_SECONDS = 0.11


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_name(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    return re.sub(r"\s+", " ", text)


def _period_length(period: int) -> float:
    return 600.0 if period <= 4 else 300.0


def _game_end(actions: list[dict[str, Any]]) -> float:
    periods = [int(action["period"]) for action in actions if action.get("period")]
    final_period = max(periods or [4])
    if final_period < 4:
        final_period = 4
    return sum(_period_length(period) for period in range(1, final_period + 1))


def _player_lookup(players: list[dict[str, Any]]) -> dict[str, list[int]]:
    lookup: dict[str, list[int]] = {}
    for player in players:
        player_id = player.get("player_id")
        if not isinstance(player_id, int):
            continue
        forms = {
            _norm_name(player.get("last_name")),
            _norm_name(player.get("full_name")),
            _norm_name(player.get("name_initial")),
            _norm_name(
                " ".join(
                    value for value in (
                        str(player.get("first_name") or "").strip(),
                        str(player.get("last_name") or "").strip(),
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


def _roster_name(player_id: int, players: list[dict[str, Any]]) -> str:
    player = next((item for item in players if item.get("player_id") == player_id), None)
    return str(player.get("full_name") or player.get("name_initial") or player_id) if player else str(player_id)


def _outgoing_label_matches(
    outgoing_label: str,
    outgoing_id: int,
    players: list[dict[str, Any]],
) -> bool:
    player = next((item for item in players if item.get("player_id") == outgoing_id), None)
    if player is None:
        return False
    label = _norm_name(outgoing_label)
    return label in {
        _norm_name(player.get("last_name")),
        _norm_name(player.get("full_name")),
        _norm_name(player.get("name_initial")),
    }


def _simulate_side(
    side: str,
    team: dict[str, Any],
    actions: list[dict[str, Any]],
    game_end: float,
) -> dict[str, Any]:
    players = [player for player in team.get("players", []) if isinstance(player, dict)]
    starters = [
        player["player_id"]
        for player in players
        if player.get("is_starter") is True and isinstance(player.get("player_id"), int)
    ]
    lookup = _player_lookup(players)
    official_seconds = {
        player["player_id"]: (
            round(float(player.get("stats", {}).get("minutes")) * 60.0, 3)
            if player.get("stats", {}).get("minutes") is not None else None
        )
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
    substitutions: list[dict[str, Any]] = []
    errors: list[str] = []
    stint_boundaries: dict[int, list[tuple[float, float]]] = {
        player_id: [] for player_id in official_seconds
    }
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
        if outgoing_id not in official_seconds:
            errors.append(f"outgoing_not_on_roster:{description}:{outgoing_id}")
            continue
        if incoming_id is None:
            errors.append(f"unresolved_incoming:{description}")
            continue
        if incoming_id not in official_seconds:
            errors.append(f"incoming_not_on_roster:{description}:{incoming_id}")
            continue
        if not _outgoing_label_matches(outgoing_label, outgoing_id, players):
            errors.append(f"outgoing_name_id_mismatch:{description}:{outgoing_id}")
        if len(current) != 5:
            errors.append(f"pre_sub_lineup_count:{len(current)}:{description}")
        if outgoing_id not in current:
            errors.append(f"outgoing_not_on_court:{description}:{outgoing_id}")
        if incoming_id in current:
            errors.append(f"incoming_already_on_court:{description}:{incoming_id}")

        if outgoing_id in current:
            current.remove(outgoing_id)
            start = open_since.pop(outgoing_id, None)
            if start is not None:
                stint_boundaries.setdefault(outgoing_id, []).append((start, elapsed))
        current.add(incoming_id)
        if incoming_id not in open_since:
            open_since[incoming_id] = elapsed

        if len(current) != 5:
            errors.append(f"post_sub_lineup_count:{len(current)}:{description}")
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
            "outgoing_name_id_match": _outgoing_label_matches(outgoing_label, outgoing_id, players),
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

    comparisons: list[dict[str, Any]] = []
    max_abs_delta = 0.0
    unmatched: list[int] = []
    for player in players:
        player_id = player.get("player_id")
        if not isinstance(player_id, int):
            continue
        official = official_seconds.get(player_id)
        reconstructed = round(tracked.get(player_id, 0.0), 3)
        delta = None if official is None else round(reconstructed - official, 3)
        if delta is not None:
            max_abs_delta = max(max_abs_delta, abs(delta))
            if abs(delta) > TOLERANCE_SECONDS:
                unmatched.append(player_id)
        comparisons.append({
            "player_id": player_id,
            "player_name": _roster_name(player_id, players),
            "is_starter": player.get("is_starter"),
            "start_position": player.get("start_position"),
            "official_minutes_raw": player.get("stats", {}).get("minutes_raw"),
            "official_seconds": official,
            "reconstructed_seconds": reconstructed,
            "delta_seconds": delta,
            "stints": [
                {
                    "in_elapsed_seconds": start,
                    "out_elapsed_seconds": end,
                    "duration_seconds": round(end - start, 3),
                }
                for start, end in stint_boundaries.get(player_id, [])
            ],
        })

    official_total = sum(value for value in official_seconds.values() if value is not None)
    reconstructed_total = sum(tracked.values())
    final_count = len(current)
    return {
        "side": side,
        "team_key": team_key,
        "starter_ids": starters,
        "starter_names": [_roster_name(player_id, players) for player_id in starters],
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
        "official_total_matches_five_player_invariant": (
            abs(official_total - 5 * game_end) <= TOLERANCE_SECONDS
        ),
        "reconstructed_total_matches_five_player_invariant": (
            abs(reconstructed_total - 5 * game_end) <= TOLERANCE_SECONDS
        ),
        "reconstructed_final_lineup_count": final_count,
        "passed": (
            len(starters) == 5
            and final_count == 5
            and not errors
            and not unmatched
            and abs(official_total - 5 * game_end) <= TOLERANCE_SECONDS
            and abs(reconstructed_total - 5 * game_end) <= TOLERANCE_SECONDS
        ),
    }


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("Rotation reconstruction probe refused because production is not fully OFF.")

    box = get_first_party_game_box_score_dataset(GAME_ID, SEASON)
    pbp = get_first_party_play_by_play_dataset(GAME_ID, SEASON)
    actions = pbp["actions"]
    game_end = _game_end(actions)

    away = _simulate_side("away", box["away"], actions, game_end)
    home = _simulate_side("home", box["home"], actions, game_end)
    passed = (
        box["verification"]["requested_game_id_matches_source"]
        and box["verification"]["player_ids_unique"]
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
        "source": "WNBA.com First-Party Page Data",
        "source_urls": {
            "box_score": box["source_url"],
            "play_by_play": pbp["source_url"],
        },
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
        "away_starters": away["starter_count"],
        "home_starters": home["starter_count"],
        "away_max_delta_seconds": away["max_abs_player_minute_delta_seconds"],
        "home_max_delta_seconds": home["max_abs_player_minute_delta_seconds"],
        "away_substitutions": away["substitution_count"],
        "home_substitutions": home["substitution_count"],
        "production_activation_allowed": False,
    }, sort_keys=True))

    if not passed:
        raise RuntimeError(
            "Certified WNBA.com box/PBP did not reconcile to exact player minutes for the target game."
        )


if __name__ == "__main__":
    main()
