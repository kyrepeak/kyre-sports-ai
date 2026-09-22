"""Fail-closed first-party WNBA rotation reconstruction.

This module is the runtime-safe form of the Step 7G rotation certification.
It reconstructs observed stint boundaries only when the official WNBA Stats
``gamerotation`` transport is unavailable. It consumes official WNBA.com
box-score starters/final minutes plus official play-by-play substitutions and
player participation evidence.

The reconstruction is accepted only when exactly one period-aware lineup
solution reconciles every player's observed seconds to the official box score
within source-clock precision. Per-stint PLAYER_PTS/PT_DIFF/USG_PCT are not
available from this source and are deliberately left ``None``.
"""
from __future__ import annotations

from itertools import combinations, product
import re
from typing import Any

from sports_api.wnba_step7g_first_party_history import (
    WNBA_FIRST_PARTY_SOURCE,
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_game_box_score_dataset,
    get_first_party_play_by_play_dataset,
)

SUB_RE = re.compile(r"^SUB:\s*(.+?)\s+FOR\s+(.+?)\s*$", re.I)
PARTICIPATION_CATEGORIES = {
    "shot",
    "free_throw",
    "rebound",
    "turnover",
    "jump_ball",
}
PLAYER_TOLERANCE_SECONDS = 1.05
# WNBA.com publishes each player's official box minutes to whole-second
# precision. Across a 12-player active roster, independent half-second rounding
# can accumulate to six seconds even when every individual player reconciles.
TEAM_TOLERANCE_SECONDS = 6.1
MAX_COMBINATIONS = 250_000


class WNBARotationReconstructionError(RuntimeError):
    """Raised when first-party stint boundaries cannot be proven uniquely."""


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


def _player_lookup(players: list[dict[str, Any]]) -> dict[str, list[int]]:
    lookup: dict[str, list[int]] = {}
    for player in players:
        player_id = player.get("player_id")
        if not isinstance(player_id, int):
            continue
        # WNBA.com substitution descriptions normally use surnames, but some
        # official rows use a player's given name (for example ``Xu`` for
        # Xu Han). Keep first names as an additional identity form while
        # preserving fail-closed ambiguity handling in _resolve_incoming.
        for form in {
            _norm_name(player.get("first_name")),
            _norm_name(player.get("last_name")),
            _norm_name(player.get("full_name")),
            _norm_name(player.get("name_initial")),
        }:
            if form:
                lookup.setdefault(form, []).append(player_id)
    return lookup


def _resolve_incoming(label: str, lookup: dict[str, list[int]]) -> int | None:
    key = _norm_name(label)
    direct = sorted(set(lookup.get(key, [])))
    if len(direct) == 1:
        return direct[0]
    suffix = sorted({
        player_id
        for name, ids in lookup.items()
        if name.endswith(" " + key) or name == key
        for player_id in ids
    })
    return suffix[0] if len(suffix) == 1 else None


def _outgoing_label_matches(
    label: str,
    player_id: int,
    players: list[dict[str, Any]],
) -> bool:
    player = next(
        (item for item in players if item.get("player_id") == player_id),
        None,
    )
    if player is None:
        return False
    value = _norm_name(label)
    return value in {
        _norm_name(player.get("first_name")),
        _norm_name(player.get("last_name")),
        _norm_name(player.get("full_name")),
        _norm_name(player.get("name_initial")),
    }


def _parse_substitutions(
    team_key: str,
    players: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> tuple[dict[int, list[dict[str, Any]]], list[str]]:
    lookup = _player_lookup(players)
    roster_ids = {
        player["player_id"]
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    by_period: dict[int, list[dict[str, Any]]] = {}
    errors: list[str] = []
    for action in actions:
        if (
            action.get("event_category") != "substitution"
            or action.get("team_key") != team_key
        ):
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
        incoming_id = _resolve_incoming(incoming_label, lookup)
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
            "outgoing_player_id": outgoing_id,
        })
    return by_period, errors


def _first_period_evidence(
    team_key: str,
    players: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> dict[int, dict[int, dict[str, Any]]]:
    roster_ids = {
        player["player_id"]
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    lookup = _player_lookup(players)
    evidence: dict[int, dict[int, dict[str, Any]]] = {}

    def record(
        period: int,
        player_id: int,
        role: str,
        reason: str,
        action: dict[str, Any],
    ) -> None:
        period_map = evidence.setdefault(period, {})
        if player_id in period_map:
            return
        period_map[player_id] = {
            "role": role,
            "reason": reason,
            "action_number": action.get("action_number"),
            "clock": action.get("clock"),
        }

    for action in actions:
        period = action.get("period")
        if not isinstance(period, int) or period <= 0:
            continue
        category = action.get("event_category")
        if category == "substitution" and action.get("team_key") == team_key:
            match = SUB_RE.match(str(action.get("description") or "").strip())
            if match:
                incoming_id = _resolve_incoming(match.group(1), lookup)
                outgoing_id = action.get("person_id")
                if isinstance(outgoing_id, int) and outgoing_id in roster_ids:
                    record(period, outgoing_id, "on", "first_outgoing_substitution", action)
                if isinstance(incoming_id, int) and incoming_id in roster_ids:
                    record(period, incoming_id, "off", "first_incoming_substitution", action)
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
        for field in ("assist_person_id", "block_person_id"):
            player_id = action.get(field)
            if isinstance(player_id, int) and player_id in roster_ids:
                participant_ids.add(player_id)
        for player_id in sorted(participant_ids):
            record(period, player_id, "on", f"first_participation_{category}", action)
    return evidence


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
    if len(current) != 5:
        return None
    for sub in subs:
        elapsed = float(sub["elapsed_game_seconds"])
        if not period_start - 1e-6 <= elapsed <= period_end + 1e-6:
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
    duration = period_end - last_elapsed
    for player_id in current:
        tracked[player_id] += duration
    for player_id in current:
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
        player["player_id"]
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    required_on = {
        player_id
        for player_id, item in first_evidence.items()
        if item.get("role") == "on"
    }
    required_off = {
        player_id
        for player_id, item in first_evidence.items()
        if item.get("role") == "off"
    }
    if required_on & required_off or len(required_on) > 5:
        return [], {
            "required_on": sorted(required_on),
            "required_off": sorted(required_off),
            "first_evidence": first_evidence,
            "candidate_count": 0,
        }
    if period == 1:
        lineups = [official_starters] if (
            len(official_starters) == 5
            and required_on.issubset(official_starters)
            and official_starters.isdisjoint(required_off)
        ) else []
    else:
        eligible = sorted(active_ids - required_on - required_off)
        needed = 5 - len(required_on)
        lineups = (
            [required_on | set(extra) for extra in combinations(eligible, needed)]
            if 0 <= needed <= len(eligible)
            else []
        )
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
    }


def _merge_stints(
    period_solutions: tuple[dict[str, Any], ...],
    roster_ids: set[int],
) -> dict[int, list[tuple[float, float]]]:
    raw = {player_id: [] for player_id in roster_ids}
    for solution in period_solutions:
        for player_id, intervals in solution["stints"].items():
            raw[player_id].extend(intervals)
    merged = {player_id: [] for player_id in roster_ids}
    for player_id, intervals in raw.items():
        for start, end in sorted(intervals):
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
        player["player_id"]
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    official_starters = {
        player["player_id"]
        for player in players
        if player.get("is_starter") is True
        and isinstance(player.get("player_id"), int)
    }
    official_seconds = {
        player["player_id"]: (
            round(float(player.get("stats", {}).get("minutes")) * 60.0, 3)
            if player.get("stats", {}).get("minutes") is not None
            else None
        )
        for player in players
        if isinstance(player.get("player_id"), int)
    }
    active_ids = {
        player_id
        for player_id, seconds in official_seconds.items()
        if seconds is not None and seconds > 0
    }
    by_period, parse_errors = _parse_substitutions(
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
        candidate_lists.append(candidates)
        period_evidence[period] = evidence
    if parse_errors:
        raise WNBARotationReconstructionError(
            f"{side} substitution parsing failed: " + "; ".join(parse_errors)
        )
    if any(not candidates for candidates in candidate_lists):
        raise WNBARotationReconstructionError(
            f"{side} has one or more periods without a legal opening lineup."
        )
    combination_count = 1
    for candidates in candidate_lists:
        combination_count *= len(candidates)
    if combination_count > MAX_COMBINATIONS:
        raise WNBARotationReconstructionError(
            f"{side} period-lineup search exceeded the fail-closed combination cap."
        )

    accepted: list[dict[str, Any]] = []
    for selected in product(*candidate_lists):
        tracked = {player_id: 0.0 for player_id in roster_ids}
        for period_solution in selected:
            for player_id, seconds in period_solution["tracked"].items():
                tracked[player_id] += seconds
        deltas = {
            player_id: (
                None
                if official_seconds.get(player_id) is None
                else round(tracked[player_id] - float(official_seconds[player_id]), 3)
            )
            for player_id in roster_ids
        }
        comparable = [abs(delta) for delta in deltas.values() if delta is not None]
        max_abs = max(comparable or [0.0])
        if max_abs <= PLAYER_TOLERANCE_SECONDS:
            accepted.append({
                "selected": selected,
                "tracked": tracked,
                "deltas": deltas,
                "max_abs_delta": max_abs,
                "sum_abs_delta": sum(comparable),
            })
    if len(accepted) != 1:
        raise WNBARotationReconstructionError(
            f"{side} produced {len(accepted)} minute-reconciled rotation solutions; exactly one is required."
        )
    chosen = accepted[0]
    game_end = sum(_period_length(period) for period in range(1, final_period + 1))
    official_total = sum(
        value for value in official_seconds.values() if value is not None
    )
    if abs(official_total - 5 * game_end) > TEAM_TOLERANCE_SECONDS:
        raise WNBARotationReconstructionError(
            f"{side} official player-minute total does not reconcile to five-player game time."
        )
    merged = _merge_stints(tuple(chosen["selected"]), roster_ids)
    return {
        "side": side,
        "team_key": team.get("team_key"),
        "combination_count": combination_count,
        "unique_solution": True,
        "max_abs_player_delta_seconds": round(chosen["max_abs_delta"], 3),
        "sum_abs_player_delta_seconds": round(chosen["sum_abs_delta"], 3),
        "period_evidence": period_evidence,
        "stints": merged,
    }


def _raw_rows(
    game_id: str,
    team: dict[str, Any],
    solution: dict[str, Any],
) -> list[dict[str, Any]]:
    players = {
        player["player_id"]: player
        for player in team.get("players", [])
        if isinstance(player, dict) and isinstance(player.get("player_id"), int)
    }
    rows: list[dict[str, Any]] = []
    for player_id, intervals in solution["stints"].items():
        player = players.get(player_id)
        if player is None:
            raise WNBARotationReconstructionError(
                f"Reconstructed player {player_id} is missing from the official box roster."
            )
        for start, end in intervals:
            if end <= start:
                continue
            rows.append({
                "GAME_ID": game_id,
                "TEAM_ID": team.get("official_team_id"),
                "TEAM_CITY": team.get("team_city"),
                "TEAM_NAME": team.get("team_name"),
                "PERSON_ID": player_id,
                "PLAYER_FIRST": player.get("first_name"),
                "PLAYER_LAST": player.get("last_name"),
                "IN_TIME_REAL": int(round(float(start) * 10.0)),
                "OUT_TIME_REAL": int(round(float(end) * 10.0)),
                "PLAYER_PTS": None,
                "PT_DIFF": None,
                "USG_PCT": None,
            })
    rows.sort(key=lambda item: (item["IN_TIME_REAL"], item["OUT_TIME_REAL"], item["PERSON_ID"]))
    if not rows:
        raise WNBARotationReconstructionError("Reconstruction produced no stint rows.")
    return rows


def reconstruct_game_rotation_rows(game_id: str, season: int) -> dict[str, Any]:
    """Return exact observed stint rows compatible with Step 4R normalization."""
    try:
        box = get_first_party_game_box_score_dataset(game_id, season)
        pbp = get_first_party_play_by_play_dataset(game_id, season)
    except (WNBAStep7GFirstPartyNotFoundError, WNBAStep7GFirstPartyUpstreamError) as exc:
        raise WNBARotationReconstructionError(str(exc)) from exc

    if not box.get("verification", {}).get("requested_game_id_matches_source"):
        raise WNBARotationReconstructionError("First-party box-score game identity was not verified.")
    if not box.get("verification", {}).get("player_ids_unique"):
        raise WNBARotationReconstructionError("First-party box score contains duplicate player IDs.")
    if not pbp.get("verification", {}).get("action_ids_unique_when_present"):
        raise WNBARotationReconstructionError("First-party PBP contains duplicate action IDs.")
    if not pbp.get("verification", {}).get("all_team_events_mapped_to_registry"):
        raise WNBARotationReconstructionError("First-party PBP contains unmapped team events.")

    actions = pbp.get("actions")
    if not isinstance(actions, list) or not actions:
        raise WNBARotationReconstructionError("First-party PBP actions are unavailable.")
    final_period = _final_period(actions)
    away_solution = _solve_side("away", box["away"], actions, final_period)
    home_solution = _solve_side("home", box["home"], actions, final_period)
    away_rows = _raw_rows(game_id, box["away"], away_solution)
    home_rows = _raw_rows(game_id, box["home"], home_solution)

    return {
        "source": WNBA_FIRST_PARTY_SOURCE,
        "source_urls": {
            "box_score": box.get("source_url"),
            "play_by_play": pbp.get("source_url"),
        },
        "source_endpoint": "period-aware WNBA.com box-score + play-by-play reconstruction",
        "season": season,
        "game_id": game_id,
        "retrieved_at_utc": max(
            str(box.get("retrieved_at_utc") or ""),
            str(pbp.get("retrieved_at_utc") or ""),
        ),
        "cache_hit": bool(box.get("cache_hit") and pbp.get("cache_hit")),
        "cache_ttl_seconds": min(
            int(box.get("cache_ttl_seconds") or 0),
            int(pbp.get("cache_ttl_seconds") or 0),
        ),
        "final_period": final_period,
        "away_rows": away_rows,
        "home_rows": home_rows,
        "diagnostics": {
            "away": {
                "combination_count": away_solution["combination_count"],
                "unique_solution": away_solution["unique_solution"],
                "max_abs_player_delta_seconds": away_solution["max_abs_player_delta_seconds"],
            },
            "home": {
                "combination_count": home_solution["combination_count"],
                "unique_solution": home_solution["unique_solution"],
                "max_abs_player_delta_seconds": home_solution["max_abs_player_delta_seconds"],
            },
        },
        "verification": {
            "period_aware_reconstruction": True,
            "first_participation_evidence_used": True,
            "unique_solution_required": True,
            "official_minutes_reconciled": True,
            "stint_boundaries_observed_not_projected": True,
            "per_stint_player_points_available": False,
            "per_stint_point_differential_available": False,
            "per_stint_usage_percentage_available": False,
            "fabricated_stint_metrics": False,
        },
    }