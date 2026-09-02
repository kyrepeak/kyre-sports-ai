"""Certify period-aware WNBA rotation boundaries from first-party page data.

WNBA play-by-play does not always emit between-period lineup changes as normal
substitution events. Treating the entire game as one uninterrupted lineup state
therefore creates false mismatches of roughly one full quarter.

This proof solves each period independently. It uses the first reliable PBP
evidence for each player in a period to constrain the opening five:
- an outgoing substitution means the player began the period ON;
- an incoming substitution means the player began the period OFF;
- a shot, free throw, rebound, turnover, jump ball, assist, or block before any
  substitution evidence means the player was already ON the court.

Period 1 is additionally pinned to the official box-score starters. Candidate
period-start lineups for later periods are combined and accepted only if exactly
one complete-game solution reconciles every player's reconstructed seconds to
the official box-score minutes within source clock precision. Ambiguity or
mismatch fails closed. Production remains untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations, product
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
PARTICIPATION_CATEGORIES = {
    "shot",
    "free_throw",
    "rebound",
    "turnover",
    "jump_ball",
}
# PBP clocks are exposed at hundredths/whole-second resolution while official
# player minutes can retain fractional-second accounting. The reconstruction
# must land within roughly one source clock tick, never a loose window.
PLAYER_TOLERANCE_SECONDS = 1.05
TEAM_TOLERANCE_SECONDS = 2.1
MAX_COMBINATIONS = 250_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_name(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    return re.sub(r"\s+", " ", text)


def _period_length(period: int) -> float:
    return 600.0 if period <= 4 else 300.0


def _period_start_elapsed(period: int) -> float:
    return sum(_period_length(value) for value in range(1, period))


def _final_period(actions: list[dict[str, Any]]) -> int:
    periods = [int(action["period"]) for action in actions if action.get("period")]
    return max(max(periods or [4]), 4)


def _game_end(actions: list[dict[str, Any]]) -> float:
    return sum(_period_length(period) for period in range(1, _final_period(actions) + 1))


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
    if player is None:
        return str(player_id)
    return str(player.get("full_name") or player.get("name_initial") or player_id)


def _outgoing_label_matches(label: str, player_id: int, players: list[dict[str, Any]]) -> bool:
    player = next((item for item in players if item.get("player_id") == player_id), None)
    if player is None:
        return False
    value = _norm_name(label)
    return value in {
        _norm_name(player.get("last_name")),
        _norm_name(player.get("full_name")),
        _norm_name(player.get("name_initial")),
    }


def _parse_team_substitutions(
    team_key: str,
    players: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> tuple[dict[int, list[dict[str, Any]]], list[str]]:
    lookup = _player_lookup(players)
    by_period: dict[int, list[dict[str, Any]]] = {}
    errors: list[str] = []
    roster_ids = {
        player["player_id"] for player in players if isinstance(player.get("player_id"), int)
    }
    for action in actions:
        if action.get("event_category") != "substitution" or action.get("team_key") != team_key:
            continue
        period = action.get("period")
        elapsed = action.get("elapsed_game_seconds")
        description = str(action.get("description") or "").strip()
        match = SUB_RE.match(description)
        if not isinstance(period, int) or period <= 0:
            errors.append(f"substitution_missing_period:{description}")
            continue
        if not isinstance(elapsed, (int, float)):
            errors.append(f"substitution_missing_elapsed:{description}")
            continue
        if not match:
            errors.append(f"unparsed_substitution:{description}")
            continue
        incoming_label, outgoing_label = match.group(1), match.group(2)
        outgoing_id = action.get("person_id")
        incoming_id, resolution = _resolve_incoming(incoming_label, lookup)
        if not isinstance(outgoing_id, int) or outgoing_id not in roster_ids:
            errors.append(f"invalid_outgoing:{description}:{outgoing_id}")
            continue
        if incoming_id is None or incoming_id not in roster_ids:
            errors.append(f"invalid_incoming:{description}:{incoming_id}")
            continue
        if not _outgoing_label_matches(outgoing_label, outgoing_id, players):
            errors.append(f"outgoing_name_id_mismatch:{description}:{outgoing_id}")
            continue
        by_period.setdefault(period, []).append({
            "action_number": action.get("action_number"),
            "period": period,
            "clock": action.get("clock"),
            "elapsed_game_seconds": float(elapsed),
            "description": description,
            "incoming_player_id": incoming_id,
            "incoming_resolution": resolution,
            "outgoing_player_id": outgoing_id,
        })
    return by_period, errors


def _first_period_evidence(
    team_key: str,
    players: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> dict[int, dict[int, dict[str, Any]]]:
    """Return each player's first reliable ON/OFF evidence in each period.

    Source order is authoritative. Once a player's first evidence is recorded,
    later events cannot rewrite whether they must have begun that period ON or
    OFF. Secondary assist/block IDs are used only when they belong to this
    team's verified roster.
    """
    roster_ids = {
        player["player_id"] for player in players if isinstance(player.get("player_id"), int)
    }
    lookup = _player_lookup(players)
    evidence: dict[int, dict[int, dict[str, Any]]] = {}

    def record(period: int, player_id: int, role: str, reason: str, action: dict[str, Any]) -> None:
        period_map = evidence.setdefault(period, {})
        if player_id in period_map:
            return
        period_map[player_id] = {
            "role": role,
            "reason": reason,
            "action_number": action.get("action_number"),
            "clock": action.get("clock"),
            "elapsed_game_seconds": action.get("elapsed_game_seconds"),
        }

    for action in actions:
        period = action.get("period")
        if not isinstance(period, int) or period <= 0:
            continue
        category = action.get("event_category")

        if category == "substitution" and action.get("team_key") == team_key:
            description = str(action.get("description") or "").strip()
            match = SUB_RE.match(description)
            if match:
                incoming_id, _ = _resolve_incoming(match.group(1), lookup)
                outgoing_id = action.get("person_id")
                if isinstance(outgoing_id, int) and outgoing_id in roster_ids:
                    record(
                        period,
                        outgoing_id,
                        "on",
                        "first_outgoing_substitution",
                        action,
                    )
                if isinstance(incoming_id, int) and incoming_id in roster_ids:
                    record(
                        period,
                        incoming_id,
                        "off",
                        "first_incoming_substitution",
                        action,
                    )
            continue

        participant_ids: set[int] = set()
        person_id = action.get("person_id")
        if (
            action.get("team_key") == team_key
            and category in PARTICIPATION_CATEGORIES
            and isinstance(person_id, int)
            and person_id in roster_ids
        ):
            participant_ids.add(person_id)

        # Assister and blocker must physically be on court for the recorded play.
        # A block belongs to the defending team, so roster membership—not the
        # action's offense team—is the safe ownership test.
        for field in ("assist_person_id", "block_person_id"):
            player_id = action.get(field)
            if isinstance(player_id, int) and player_id in roster_ids:
                participant_ids.add(player_id)

        for player_id in sorted(participant_ids):
            record(
                period,
                player_id,
                "on",
                f"first_participation_{category}",
                action,
            )

    return evidence


def _period_start_requirements(
    first_evidence: dict[int, dict[str, Any]],
) -> tuple[set[int], set[int], list[str]]:
    required_on = {
        player_id for player_id, item in first_evidence.items() if item.get("role") == "on"
    }
    required_off = {
        player_id for player_id, item in first_evidence.items() if item.get("role") == "off"
    }
    errors: list[str] = []
    overlap = required_on & required_off
    if overlap:
        errors.append(
            "period_start_requirement_overlap:" + ",".join(map(str, sorted(overlap)))
        )
    if len(required_on) > 5:
        errors.append(
            "period_start_required_on_exceeds_five:" + ",".join(map(str, sorted(required_on)))
        )
    return required_on, required_off, errors


def _simulate_period(
    period: int,
    start_lineup: set[int],
    subs: list[dict[str, Any]],
    roster_ids: set[int],
) -> dict[str, Any] | None:
    period_start = _period_start_elapsed(period)
    period_end = period_start + _period_length(period)
    current = set(start_lineup)
    tracked = {player_id: 0.0 for player_id in roster_ids}
    open_since = {player_id: period_start for player_id in current}
    stints: dict[int, list[tuple[float, float]]] = {
        player_id: [] for player_id in roster_ids
    }
    last_elapsed = period_start
    transitions: list[dict[str, Any]] = []

    if len(current) != 5:
        return None
    for sub in subs:
        elapsed = float(sub["elapsed_game_seconds"])
        if elapsed < period_start - 1e-6 or elapsed > period_end + 1e-6:
            return None
        if elapsed < last_elapsed - 1e-6:
            return None
        duration = elapsed - last_elapsed
        for player_id in current:
            tracked[player_id] += duration
        last_elapsed = elapsed
        outgoing = sub["outgoing_player_id"]
        incoming = sub["incoming_player_id"]
        if outgoing not in current or incoming in current:
            return None
        current.remove(outgoing)
        start = open_since.pop(outgoing, None)
        if start is None:
            return None
        stints[outgoing].append((start, elapsed))
        current.add(incoming)
        open_since[incoming] = elapsed
        if len(current) != 5:
            return None
        transitions.append({**sub, "lineup_after": sorted(current)})

    duration = period_end - last_elapsed
    for player_id in current:
        tracked[player_id] += duration
    for player_id in list(current):
        start = open_since.get(player_id)
        if start is not None:
            stints[player_id].append((start, period_end))
    if abs(sum(tracked.values()) - 5 * _period_length(period)) > 1e-6:
        return None
    return {
        "period": period,
        "start_lineup": sorted(start_lineup),
        "end_lineup": sorted(current),
        "tracked": tracked,
        "stints": stints,
        "transitions": transitions,
    }


def _period_candidates(
    period: int,
    players: list[dict[str, Any]],
    subs: list[dict[str, Any]],
    first_evidence: dict[int, dict[str, Any]],
    official_starters: set[int],
    active_ids: set[int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    roster_ids = {
        player["player_id"] for player in players if isinstance(player.get("player_id"), int)
    }
    required_on, required_off, requirement_errors = _period_start_requirements(first_evidence)
    if requirement_errors or required_on & required_off or len(required_on) > 5:
        return [], {
            "required_on": sorted(required_on),
            "required_off": sorted(required_off),
            "first_evidence": first_evidence,
            "requirement_errors": requirement_errors,
        }

    if period == 1:
        lineups = [official_starters] if (
            len(official_starters) == 5
            and required_on.issubset(official_starters)
            and official_starters.isdisjoint(required_off)
        ) else []
    else:
        eligible_unknown = sorted(active_ids - required_on - required_off)
        needed = 5 - len(required_on)
        if needed < 0 or needed > len(eligible_unknown):
            lineups = []
        else:
            lineups = [
                required_on | set(extra)
                for extra in combinations(eligible_unknown, needed)
            ]

    candidates = []
    for lineup in lineups:
        simulated = _simulate_period(period, set(lineup), subs, roster_ids)
        if simulated is not None:
            candidates.append(simulated)
    return candidates, {
        "required_on": sorted(required_on),
        "required_off": sorted(required_off),
        "first_evidence": first_evidence,
        "candidate_count": len(candidates),
        "requirement_errors": requirement_errors,
    }


def _merge_stints(
    period_solutions: tuple[dict[str, Any], ...],
    roster_ids: set[int],
) -> dict[int, list[tuple[float, float]]]:
    raw: dict[int, list[tuple[float, float]]] = {
        player_id: [] for player_id in roster_ids
    }
    for solution in period_solutions:
        for player_id, intervals in solution["stints"].items():
            raw[player_id].extend(intervals)
    merged: dict[int, list[tuple[float, float]]] = {
        player_id: [] for player_id in roster_ids
    }
    for player_id, intervals in raw.items():
        ordered = sorted(intervals)
        for start, end in ordered:
            if merged[player_id] and abs(merged[player_id][-1][1] - start) <= 1e-9:
                merged[player_id][-1] = (merged[player_id][-1][0], end)
            else:
                merged[player_id].append((start, end))
    return merged


def _solve_side(
    side: str,
    team: dict[str, Any],
    actions: list[dict[str, Any]],
    final_period: int,
) -> dict[str, Any]:
    players = [player for player in team.get("players", []) if isinstance(player, dict)]
    roster_ids = {
        player["player_id"] for player in players if isinstance(player.get("player_id"), int)
    }
    official_starters = {
        player["player_id"]
        for player in players
        if player.get("is_starter") is True and isinstance(player.get("player_id"), int)
    }
    official_seconds = {
        player["player_id"]: (
            round(float(player.get("stats", {}).get("minutes")) * 60.0, 3)
            if player.get("stats", {}).get("minutes") is not None else None
        )
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    active_ids = {
        player_id for player_id, seconds in official_seconds.items()
        if seconds is not None and seconds > 0
    }
    by_period, parse_errors = _parse_team_substitutions(
        str(team.get("team_key")), players, actions
    )
    evidence_by_period = _first_period_evidence(
        str(team.get("team_key")), players, actions
    )

    candidate_lists: list[list[dict[str, Any]]] = []
    period_evidence: dict[int, Any] = {}
    for period in range(1, final_period + 1):
        candidates, evidence = _period_candidates(
            period,
            players,
            by_period.get(period, []),
            evidence_by_period.get(period, {}),
            official_starters,
            active_ids,
        )
        period_evidence[period] = evidence
        candidate_lists.append(candidates)

    combination_count = 1
    for candidates in candidate_lists:
        combination_count *= max(len(candidates), 1)
    if any(not candidates for candidates in candidate_lists):
        return {
            "side": side,
            "team_key": team.get("team_key"),
            "passed": False,
            "parse_errors": parse_errors,
            "period_evidence": period_evidence,
            "combination_count": 0,
            "failure_reason": "one_or_more_periods_have_no_legal_start_lineup",
        }
    if combination_count > MAX_COMBINATIONS:
        return {
            "side": side,
            "team_key": team.get("team_key"),
            "passed": False,
            "parse_errors": parse_errors,
            "period_evidence": period_evidence,
            "combination_count": combination_count,
            "failure_reason": "candidate_combination_cap_exceeded",
        }

    accepted: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for selected in product(*candidate_lists):
        tracked = {player_id: 0.0 for player_id in roster_ids}
        for period_solution in selected:
            for player_id, seconds in period_solution["tracked"].items():
                tracked[player_id] += seconds
        deltas = {
            player_id: (
                None if official_seconds.get(player_id) is None
                else round(tracked[player_id] - float(official_seconds[player_id]), 3)
            )
            for player_id in roster_ids
        }
        comparable = [abs(delta) for delta in deltas.values() if delta is not None]
        max_abs = max(comparable or [0.0])
        sum_abs = sum(comparable)
        score = (round(max_abs, 6), round(sum_abs, 6))
        record = {
            "selected": selected,
            "tracked": tracked,
            "deltas": deltas,
            "max_abs_delta": max_abs,
            "sum_abs_delta": sum_abs,
            "score": score,
        }
        if best is None or score < best["score"]:
            best = record
        if max_abs <= PLAYER_TOLERANCE_SECONDS:
            accepted.append(record)

    if best is None:
        raise RuntimeError("Internal Step 7G solver error: no combinations were evaluated.")

    unique = len(accepted) == 1
    chosen = accepted[0] if unique else best
    merged_stints = _merge_stints(tuple(chosen["selected"]), roster_ids)
    comparisons = []
    for player in players:
        player_id = player.get("player_id")
        if not isinstance(player_id, int):
            continue
        official = official_seconds.get(player_id)
        reconstructed = round(chosen["tracked"][player_id], 3)
        delta = chosen["deltas"][player_id]
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
                for start, end in merged_stints[player_id]
            ],
        })

    official_total = sum(value for value in official_seconds.values() if value is not None)
    reconstructed_total = sum(chosen["tracked"].values())
    game_end = sum(_period_length(period) for period in range(1, final_period + 1))
    team_total_ok = abs(official_total - 5 * game_end) <= TEAM_TOLERANCE_SECONDS
    period_lineups = [
        {
            "period": solution["period"],
            "start_lineup_ids": solution["start_lineup"],
            "start_lineup_names": [
                _roster_name(player_id, players) for player_id in solution["start_lineup"]
            ],
            "end_lineup_ids": solution["end_lineup"],
            "substitution_count": len(solution["transitions"]),
        }
        for solution in chosen["selected"]
    ]
    return {
        "side": side,
        "team_key": team.get("team_key"),
        "official_starter_ids": sorted(official_starters),
        "official_starter_names": [
            _roster_name(player_id, players) for player_id in sorted(official_starters)
        ],
        "official_starter_count": len(official_starters),
        "parse_errors": parse_errors,
        "period_evidence": period_evidence,
        "combination_count": combination_count,
        "accepted_solution_count": len(accepted),
        "unique_solution": unique,
        "best_max_abs_player_delta_seconds": round(chosen["max_abs_delta"], 3),
        "best_sum_abs_player_delta_seconds": round(chosen["sum_abs_delta"], 3),
        "official_total_player_seconds": round(official_total, 3),
        "reconstructed_total_player_seconds": round(reconstructed_total, 3),
        "expected_five_player_seconds": round(5 * game_end, 3),
        "official_team_total_within_source_precision": team_total_ok,
        "period_lineups": period_lineups,
        "comparisons": comparisons,
        "passed": (
            len(official_starters) == 5
            and not parse_errors
            and unique
            and chosen["max_abs_delta"] <= PLAYER_TOLERANCE_SECONDS
            and team_total_ok
            and abs(reconstructed_total - 5 * game_end) <= 1e-6
        ),
    }


def main() -> None:
    off_state = {
        key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV
    }
    if not all(off_state.values()):
        raise RuntimeError(
            "Rotation reconstruction probe refused because production is not fully OFF."
        )

    box = get_first_party_game_box_score_dataset(GAME_ID, SEASON)
    pbp = get_first_party_play_by_play_dataset(GAME_ID, SEASON)
    actions = pbp["actions"]
    final_period = _final_period(actions)
    game_end = _game_end(actions)
    away = _solve_side("away", box["away"], actions, final_period)
    home = _solve_side("home", box["home"], actions, final_period)
    passed = (
        box["verification"]["requested_game_id_matches_source"]
        and box["verification"]["player_ids_unique"]
        and pbp["verification"]["action_ids_unique_when_present"]
        and pbp["verification"]["all_team_events_mapped_to_registry"]
        and away["passed"]
        and home["passed"]
    )

    report = {
        "data_type": "wnba_step7g_period_aware_rotation_reconstruction_probe",
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
        "final_period": final_period,
        "game_end_elapsed_seconds": game_end,
        "player_tolerance_seconds": PLAYER_TOLERANCE_SECONDS,
        "team_tolerance_seconds": TEAM_TOLERANCE_SECONDS,
        "play_by_play_action_count": pbp["source_action_count"],
        "away": away,
        "home": home,
        "decision": {
            "single_game_period_aware_reconciliation_passed": passed,
            "first_participation_evidence_used": True,
            "unique_period_start_lineups_required": True,
            "rotation_boundaries_deterministic_from_first_party_data": passed,
            "multi_game_certification_required_before_provider_integration": True,
            "production_activation_allowed": False,
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "passed": passed,
        "away_passed": away["passed"],
        "home_passed": home["passed"],
        "away_unique_solution": away.get("unique_solution"),
        "home_unique_solution": home.get("unique_solution"),
        "away_best_max_delta_seconds": away.get("best_max_abs_player_delta_seconds"),
        "home_best_max_delta_seconds": home.get("best_max_abs_player_delta_seconds"),
        "away_combination_count": away.get("combination_count"),
        "home_combination_count": home.get("combination_count"),
        "production_activation_allowed": False,
    }, sort_keys=True))

    if not passed:
        raise RuntimeError(
            "Period-aware first-party WNBA rotation reconstruction did not produce one unique exact solution."
        )


if __name__ == "__main__":
    main()
