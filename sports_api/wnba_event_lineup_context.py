"""Step 4T: official WNBA event-lineup and conservative possession context.

This module joins Step 4K official liveData play-by-play to Step 4R official
GameRotation stints. It reconstructs who was on the court at each event time.
Ten-player court context is never labeled as an individual defender assignment.
Derived possession segments are deterministic features, not an official
possession feed and not player-vs-defender possessions.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any, Iterable

from sports_api.wnba_live_game import (
    ALLOWED_EVENT_CATEGORIES,
    WNBALiveNotFoundError,
    WNBALiveUpstreamError,
    get_play_by_play_dataset,
)
from sports_api.wnba_rotation_context import (
    WNBARotationNotFoundError,
    WNBARotationUpstreamError,
    get_game_rotation,
)

EVENT_LINEUP_SOURCE = "WNBA Official Live Data + WNBA Stats API GameRotation"
MAX_EVENT_LIMIT = 1000
_CONTROL = {"shot", "free_throw", "rebound", "turnover"}
_TERMINALS = {
    "turnover", "made_field_goal", "defensive_rebound",
    "made_final_free_throw", "period_end",
}
_FT_RE = re.compile(r"\b(\d+)\s*(?:of|/|-of-)\s*(\d+)\b", re.I)


class WNBAEventLineupUpstreamError(RuntimeError):
    pass


class WNBAEventLineupNotFoundError(LookupError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        text = _clean(value)
        return int(float(text)) if text is not None else None
    except (TypeError, ValueError):
        return None


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _choice(value: str, allowed: Iterable[str], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed) + "."
        )
    return result


def _limit(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_EVENT_LIMIT:
        raise ValueError("WNBA event limit must be an integer from 0 through 1000.")
    return value


def _tenths(value: Any, label: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAEventLineupUpstreamError(f"WNBA source contains invalid {label}.") from exc
    rounded = int(round(number))
    if number < 0 or abs(number - rounded) > .001:
        raise WNBAEventLineupUpstreamError(f"WNBA source contains invalid {label}.")
    return rounded


def _event_tenths(action: dict[str, Any]) -> int | None:
    value = action.get("elapsed_game_seconds")
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAEventLineupUpstreamError("WNBA event has invalid elapsed_game_seconds.") from exc
    if value < 0:
        raise WNBAEventLineupUpstreamError("WNBA event has negative elapsed_game_seconds.")
    return int(round(value * 10.0))


def _player_map(side: dict[str, Any]) -> dict[int, dict[str, Any]]:
    raw = side.get("players")
    if not isinstance(raw, list):
        raise WNBAEventLineupUpstreamError("WNBA rotation side has malformed players.")
    result = {}
    for player in raw:
        if not isinstance(player, dict):
            raise WNBAEventLineupUpstreamError("WNBA rotation side has malformed player.")
        player_id = _int(player.get("player_id"))
        if player_id is None or player_id <= 0 or player_id in result:
            raise WNBAEventLineupUpstreamError("WNBA rotation side has invalid/duplicate player ID.")
        result[player_id] = player
    return result


def _side_snapshot(side: dict[str, Any], t: int, phase: str) -> dict[str, Any]:
    players = _player_map(side)
    stints = side.get("stints")
    if not isinstance(stints, list):
        raise WNBAEventLineupUpstreamError("WNBA rotation side has malformed stints.")
    counts: Counter[int] = Counter()
    for stint in stints:
        if not isinstance(stint, dict):
            raise WNBAEventLineupUpstreamError("WNBA rotation side has malformed stint.")
        player_id = _int(stint.get("player_id"))
        if player_id not in players:
            raise WNBAEventLineupUpstreamError("WNBA rotation stint references unknown player.")
        start = _tenths(stint.get("in_time_real"), "IN_TIME_REAL")
        end = _tenths(stint.get("out_time_real"), "OUT_TIME_REAL")
        if end < start:
            raise WNBAEventLineupUpstreamError("WNBA rotation stint has invalid interval.")
        active = start < t <= end if phase == "pre" else start <= t < end
        if active and end > start:
            counts[player_id] += 1
    ids = sorted(counts)
    duplicates = sorted(pid for pid, count in counts.items() if count > 1)
    active = [
        {
            "player_id": pid,
            "player_name": players[pid].get("player_name"),
            "official_team_id": players[pid].get("official_team_id"),
            "team_key": players[pid].get("team_key"),
            "team_full_name": players[pid].get("team_full_name"),
        }
        for pid in ids
    ]
    return {
        "side": side.get("side"),
        "official_team_id": side.get("official_team_id"),
        "team_key": side.get("team_key"),
        "team_full_name": side.get("team_full_name"),
        "phase": phase,
        "event_time_real": t,
        "event_elapsed_seconds": round(t / 10.0, 1),
        "player_count": len(active),
        "player_ids": ids,
        "players": active,
        "exactly_five": len(active) == 5,
        "duplicate_active_interval_player_ids": duplicates,
        "no_duplicate_active_intervals": not duplicates,
    }


def _snapshot(rotation: dict[str, Any], t: int, phase: str) -> dict[str, Any]:
    away, home = rotation.get("away"), rotation.get("home")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise WNBAEventLineupUpstreamError("WNBA rotation is missing away/home sides.")
    a = _side_snapshot(away, t, phase)
    h = _side_snapshot(home, t, phase)
    cross = sorted(set(a["player_ids"]) & set(h["player_ids"]))
    if cross:
        raise WNBAEventLineupUpstreamError("WNBA court snapshot has player IDs on both teams.")
    ids = a["player_ids"] + h["player_ids"]
    return {
        "phase": phase,
        "event_time_real": t,
        "event_elapsed_seconds": round(t / 10.0, 1),
        "away": a,
        "home": h,
        "all_player_ids": ids,
        "player_count": len(ids),
        "exact_5v5": a["exactly_five"] and h["exactly_five"],
        "exact_ten_players": len(ids) == 10 and len(set(ids)) == 10,
        "duplicate_active_interval_player_ids": sorted(
            set(a["duplicate_active_interval_player_ids"])
            | set(h["duplicate_active_interval_player_ids"])
        ),
    }


def _signature(snapshot: dict[str, Any] | None):
    if not isinstance(snapshot, dict):
        return None
    return (
        tuple(snapshot["away"].get("player_ids") or []),
        tuple(snapshot["home"].get("player_ids") or []),
    )


def _participants(action: dict[str, Any]) -> list[int]:
    result = []
    for key in ("person_id", "assist_person_id", "block_person_id"):
        value = _int(action.get(key))
        if value is not None and value > 0 and value not in result:
            result.append(value)
    return result


def _period_boundary(action: dict[str, Any]) -> str | None:
    if action.get("event_category") != "period":
        return None
    text = " ".join(
        value for value in (
            _clean(action.get("action_type")), _clean(action.get("sub_type")),
            _clean(action.get("description")),
        ) if value
    ).casefold()
    if "end" in text:
        return "end"
    if "start" in text:
        return "start"
    try:
        if float(action.get("clock_seconds_remaining")) == 0:
            return "end"
    except (TypeError, ValueError):
        pass
    return None


def _groups(actions: list[dict[str, Any]]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for index, action in enumerate(actions):
        t = _event_tenths(action)
        if t is not None:
            result.setdefault(t, []).append(index)
    return result


def _select(action, index, actions, groups, rotation):
    t = _event_tenths(action)
    participants = _participants(action)
    if t is None:
        return {
            "available": False, "reason": "event_elapsed_time_unavailable",
            "event_time_real": None, "event_elapsed_seconds": None,
            "selection_basis": "no_reconstructable_event_time", "lineup_phase": "unavailable",
            "selected": None, "pre_event": None, "post_event": None,
            "known_participant_ids": participants,
            "known_participants_on_selected_court": None,
            "missing_known_participant_ids": participants,
            "eligible_for_player_event_features": False,
        }
    pre, post = _snapshot(rotation, t, "pre"), _snapshot(rotation, t, "post")
    changed = _signature(pre) != _signature(post)
    selected, basis, phase = post, "stable_observed_rotation_interval", "stable"
    if changed:
        selected = None
        boundary = _period_boundary(action)
        subs = [i for i in groups.get(t, [index]) if actions[i].get("event_category") == "substitution"]
        if boundary == "end":
            selected, basis, phase = pre, "period_end_uses_pre_boundary_lineup", "pre_boundary"
        elif boundary == "start":
            selected, basis, phase = post, "period_start_uses_post_boundary_lineup", "post_boundary"
        elif subs:
            if action.get("event_category") == "substitution":
                selected, basis, phase = post, "substitution_event_reports_post_boundary_lineup", "transition"
            elif index < min(subs):
                selected, basis, phase = pre, "same_clock_event_precedes_substitution_group", "pre_boundary"
            elif index > max(subs):
                selected, basis, phase = post, "same_clock_event_follows_substitution_group", "post_boundary"
            else:
                basis, phase = "non_substitution_event_inside_multi_substitution_boundary_is_ambiguous", "ambiguous_boundary"
        else:
            pre_has = bool(participants) and set(participants).issubset(pre["all_player_ids"])
            post_has = bool(participants) and set(participants).issubset(post["all_player_ids"])
            if pre_has and not post_has:
                selected, basis, phase = pre, "known_event_participants_resolve_pre_boundary_lineup", "pre_boundary"
            elif post_has and not pre_has:
                selected, basis, phase = post, "known_event_participants_resolve_post_boundary_lineup", "post_boundary"
            else:
                basis, phase = "rotation_boundary_without_ordering_evidence", "ambiguous_boundary"
    selected_ids = set(selected["all_player_ids"]) if selected else set()
    missing = [pid for pid in participants if pid not in selected_ids]
    on_court = None if selected is None else not missing
    duplicates = selected.get("duplicate_active_interval_player_ids", []) if selected else []
    exact = bool(selected and selected["exact_5v5"] and selected["exact_ten_players"])
    return {
        "available": selected is not None,
        "reason": None if selected is not None else "boundary_lineup_ambiguous",
        "event_time_real": t,
        "event_elapsed_seconds": round(t / 10.0, 1),
        "lineup_boundary_changed_at_event_time": changed,
        "selection_basis": basis,
        "lineup_phase": phase,
        "selected": selected,
        "pre_event": pre if changed else None,
        "post_event": post if changed else None,
        "known_participant_ids": participants,
        "known_participants_on_selected_court": on_court,
        "missing_known_participant_ids": missing,
        "exact_5v5": exact,
        "duplicate_active_interval_player_ids": duplicates,
        "eligible_for_player_event_features": bool(
            selected and exact and on_court is not False and not duplicates and phase != "ambiguous_boundary"
        ),
        "guardrails": {
            "event_lineup_is_court_context_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_player_vs_defender_possession_inferred": True,
        },
    }


def _teams(rotation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for side_name in ("away", "home"):
        side = rotation.get(side_name)
        if not isinstance(side, dict):
            raise WNBAEventLineupUpstreamError("WNBA rotation is missing away/home side.")
        team_id, team_key = _int(side.get("official_team_id")), _clean(side.get("team_key"))
        if team_id is None or team_id <= 0 or team_key is None:
            raise WNBAEventLineupUpstreamError("WNBA rotation has incomplete team identity.")
        result[side_name] = {
            "side": side_name, "official_team_id": team_id, "team_key": team_key,
            "team_full_name": side.get("team_full_name"),
        }
    if result["away"]["official_team_id"] == result["home"]["official_team_id"] or result["away"]["team_key"] == result["home"]["team_key"]:
        raise WNBAEventLineupUpstreamError("WNBA rotation has identical away/home teams.")
    return result


def _event_side(action: dict[str, Any], teams: dict[str, dict[str, Any]]) -> str | None:
    team_id = _int(action.get("team_id"))
    if team_id is not None and team_id <= 0:
        team_id = None
    team_key = _clean(action.get("team_key"))
    id_side = next((side for side, team in teams.items() if team_id == team["official_team_id"]), None) if team_id is not None else None
    key_side = next((side for side, team in teams.items() if team_key == team["team_key"]), None) if team_key is not None else None
    if team_id is not None and id_side is None:
        raise WNBAEventLineupUpstreamError("WNBA play-by-play event has team ID outside rotation matchup.")
    if team_key is not None and key_side is None:
        raise WNBAEventLineupUpstreamError("WNBA play-by-play event has team key outside rotation matchup.")
    if id_side and key_side and id_side != key_side:
        raise WNBAEventLineupUpstreamError("WNBA event team ID/team key disagree.")
    return id_side or key_side


def _join(pbp: dict[str, Any], rotation: dict[str, Any]):
    game_id = _clean(pbp.get("game_id"))
    if game_id is None or _clean(rotation.get("game_id")) != game_id:
        raise WNBAEventLineupUpstreamError("WNBA play-by-play/rotation game IDs do not agree.")
    actions = pbp.get("actions")
    if not isinstance(actions, list):
        raise WNBAEventLineupUpstreamError("WNBA play-by-play has malformed actions.")
    teams = _teams(rotation)
    groups = _groups(actions)
    rows = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise WNBAEventLineupUpstreamError("WNBA play-by-play has malformed action.")
        try:
            side = _event_side(action, teams)
        except WNBAEventLineupUpstreamError as exc:
            raise WNBAEventLineupUpstreamError(
                "WNBA play-by-play contains team events outside the rotation matchup."
            ) from exc
        rows.append({
            "source_index": index,
            "event_side": side,
            "event": deepcopy(action),
            "lineup_context": _select(action, index, actions, groups, rotation),
        })
    return rows, teams


def _reconstruct_all_events(pbp: dict[str, Any], rotation: dict[str, Any]):
    return _join(pbp, rotation)


def _summary(rows):
    count = len(rows)
    exact = sum(bool(r["lineup_context"].get("exact_5v5")) for r in rows)
    eligible = sum(bool(r["lineup_context"].get("eligible_for_player_event_features")) for r in rows)
    return {
        "event_count": count,
        "exact_5v5_event_count": exact,
        "exact_5v5_event_share": round(exact / count, 6) if count else None,
        "ambiguous_boundary_event_count": sum(r["lineup_context"].get("lineup_phase") == "ambiguous_boundary" for r in rows),
        "unavailable_lineup_event_count": sum(not r["lineup_context"].get("available") for r in rows),
        "known_participant_mismatch_event_count": sum(r["lineup_context"].get("known_participants_on_selected_court") is False for r in rows),
        "feature_eligible_event_count": eligible,
        "feature_eligible_event_share": round(eligible / count, 6) if count else None,
    }


def _sources(game_id: str, season: int):
    try:
        pbp = get_play_by_play_dataset(game_id, season, event_category="All", limit=0)
    except WNBALiveNotFoundError as exc:
        raise WNBAEventLineupNotFoundError(str(exc)) from exc
    except WNBALiveUpstreamError as exc:
        raise WNBAEventLineupUpstreamError(str(exc)) from exc
    try:
        rotation = get_game_rotation(game_id, season)
    except WNBARotationNotFoundError as exc:
        raise WNBAEventLineupNotFoundError(str(exc)) from exc
    except WNBARotationUpstreamError as exc:
        raise WNBAEventLineupUpstreamError(str(exc)) from exc
    return pbp, rotation


def get_game_event_lineups(game_id: str, season: int, *, event_category: str = "All", limit: int = 0) -> dict[str, Any]:
    game_id = _game_id(game_id)
    category = _choice(event_category, ALLOWED_EVENT_CATEGORIES, "event_category")
    limit = _limit(limit)
    pbp, rotation = _sources(game_id, season)
    if _clean(pbp.get("game_id")) != game_id or _clean(rotation.get("game_id")) != game_id:
        raise WNBAEventLineupUpstreamError("WNBA source game ID does not match requested game ID.")
    rows, teams = _join(pbp, rotation)
    filtered = rows if category == "All" else [r for r in rows if r["event"].get("event_category") == category]
    if limit:
        filtered = filtered[-limit:]
    return {
        "source": EVENT_LINEUP_SOURCE,
        "data_type": "official_pbp_with_observed_rotation_event_lineups",
        "season": season, "game_id": game_id,
        "source_feeds": {
            "play_by_play": {k: pbp.get(k) for k in ("source", "source_url", "data_type", "retrieved_at_utc", "cache_hit")},
            "rotation": {k: rotation.get(k) for k in ("source", "source_url", "source_endpoint", "retrieved_at_utc", "cache_hit")},
        },
        "time_join": {
            "play_by_play_time": "elapsed_game_seconds derived from official period + clock",
            "rotation_time": "IN_TIME_REAL/OUT_TIME_REAL tenths elapsed from game start",
            "post_boundary_interval_rule": "IN_TIME_REAL <= t < OUT_TIME_REAL",
            "pre_boundary_interval_rule": "IN_TIME_REAL < t <= OUT_TIME_REAL",
            "same_clock_substitution_rule": "source order selects pre/substitution-transition/post boundary state",
        },
        "teams": teams,
        "filters": {"event_category": category, "limit": limit},
        "source_action_count": len(rows),
        **_summary(filtered),
        "events": filtered,
        "verification": {
            "requested_game_id_matches_both_sources": True,
            "play_by_play_and_rotation_team_identity_agree": True,
            "source_event_order_preserved_before_filtering": True,
            "event_filter_applied_after_full_boundary_reconstruction": True,
            "event_lineups_derived_only_from_observed_rotation_stints": True,
            "ambiguous_boundaries_fail_closed_instead_of_guessing": True,
            "event_lineup_is_court_context_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_player_vs_defender_possession_inferred": True,
            "no_causal_defensive_effect_created": True,
            "no_matchup_grade_created": True,
            "no_projection_created": True,
            "no_betting_probability_created": True,
        },
    }


def _opposite(side):
    return "home" if side == "away" else "away" if side == "home" else None


def _made(action):
    return (_clean(action.get("shot_result")) or "").casefold().startswith(("made", "make"))


def _rebound_kind(action):
    text = (_clean(action.get("sub_type")) or "").casefold().replace("_", " ")
    if "offensive" in text or text.strip() in {"off", "off rebound"}:
        return "offensive"
    if "defensive" in text or text.strip() in {"def", "def rebound"}:
        return "defensive"
    return None


def _implied_offense(row):
    category, side = row["event"].get("event_category"), row.get("event_side")
    if category in {"shot", "free_throw", "turnover"}:
        return side
    if category == "rebound":
        kind = _rebound_kind(row["event"])
        return side if kind == "offensive" else _opposite(side) if kind == "defensive" else None
    return None


def _same_time_ft(rows, index):
    row, action = rows[index], rows[index]["event"]
    t, side = _event_tenths(action), row.get("event_side")
    if t is None or side is None:
        return False
    for other in rows[index + 1:]:
        if _event_tenths(other["event"]) != t:
            return False
        category = other["event"].get("event_category")
        if category == "free_throw" and other.get("event_side") == side:
            return True
        if category in _CONTROL:
            return False
    return False


def _terminal(rows, index, offense):
    row, action = rows[index], rows[index]["event"]
    category, side = action.get("event_category"), row.get("event_side")
    if category == "turnover" and side:
        return "turnover"
    if category == "shot" and side and _made(action) and not _same_time_ft(rows, index):
        return "made_field_goal"
    if category == "rebound" and side and _rebound_kind(action) == "defensive":
        return "defensive_rebound"
    if category == "free_throw" and side and _made(action):
        text = " ".join(v for v in (_clean(action.get("sub_type")), _clean(action.get("description"))) if v)
        match = _FT_RE.search(text)
        if match and int(match.group(1)) < int(match.group(2)):
            return None
        if not _same_time_ft(rows, index) and offense == side:
            return "made_final_free_throw"
    if category == "period" and _period_boundary(action) == "end":
        return "period_end"
    return None


def _ref(row):
    action = row["event"]
    return {
        "source_index": row.get("source_index"), "action_number": action.get("action_number"),
        "action_id": action.get("action_id"), "period": action.get("period"),
        "clock": action.get("clock"), "elapsed_game_seconds": action.get("elapsed_game_seconds"),
        "event_category": action.get("event_category"), "event_side": row.get("event_side"),
        "description": action.get("description"),
    }


def _possession(number, buffer, offense, teams, reason, complete, confidence):
    categories = Counter(row["event"].get("event_category") or "unknown" for row in buffer)
    signatures = [_signature(row["lineup_context"].get("selected")) for row in buffer]
    signatures = [item for item in signatures if item is not None]
    points = sum(
        max(0, _int(row["event"].get("points_scored_on_action")) or 0)
        for row in buffer if row["event"].get("scoring_side") == offense
    ) if offense else 0
    first, last = buffer[0], buffer[-1]
    start, end = first["event"].get("elapsed_game_seconds"), last["event"].get("elapsed_game_seconds")
    try:
        span = round(max(0.0, float(end) - float(start)), 3) if start is not None and end is not None else None
    except (TypeError, ValueError):
        span = None
    defense = _opposite(offense)
    return {
        "possession_number": number,
        "classification": "derived_play_by_play_possession_segment",
        "offense_side": offense, "defense_side": defense,
        "offense_team": teams.get(offense) if offense else None,
        "defense_team": teams.get(defense) if defense else None,
        "complete": complete, "end_reason": reason, "boundary_confidence": confidence,
        "start_event": _ref(first), "end_event": _ref(last),
        "start_elapsed_game_seconds": start, "end_elapsed_game_seconds": end,
        "observed_event_span_seconds": span,
        "event_count": len(buffer), "event_category_counts": dict(sorted(categories.items())),
        "points_scored_by_offense": points,
        "lineup_change_count": sum(signatures[i] != signatures[i-1] for i in range(1, len(signatures))),
        "all_events_exact_5v5": all(bool(row["lineup_context"].get("exact_5v5")) for row in buffer),
        "all_events_feature_eligible": all(bool(row["lineup_context"].get("eligible_for_player_event_features")) for row in buffer),
        "has_ambiguous_lineup_event": any(row["lineup_context"].get("lineup_phase") == "ambiguous_boundary" for row in buffer),
        "event_refs": [_ref(row) for row in buffer],
        "guardrails": {
            "derived_possession_segment_is_not_official_possession_feed": True,
            "possession_lineups_are_court_context_not_defender_assignments": True,
            "no_player_vs_defender_possession_inferred": True,
        },
    }


def _reconstruct_possessions(rows, teams):
    possessions, buffer, offense = [], [], None
    def flush(reason, complete, confidence):
        nonlocal buffer, offense
        if buffer:
            possessions.append(_possession(len(possessions)+1, buffer, offense, teams, reason, complete, confidence))
            buffer, offense = [], None
    for index, row in enumerate(rows):
        implied = _implied_offense(row)
        if buffer and offense and implied and implied != offense:
            flush("implicit_offense_change_before_control_event", False, "low")
        buffer.append(row)
        if offense is None and implied:
            offense = implied
        terminal = _terminal(rows, index, offense)
        if terminal:
            flush(terminal, True, "high" if terminal in {"turnover", "made_field_goal", "defensive_rebound", "period_end"} else "medium")
    if buffer:
        flush("open_at_feed_end", False, "low")
    return possessions


def get_game_possession_event_context(game_id: str, season: int, *, limit: int = 0) -> dict[str, Any]:
    game_id, limit = _game_id(game_id), _limit(limit)
    pbp, rotation = _sources(game_id, season)
    if _clean(pbp.get("game_id")) != game_id or _clean(rotation.get("game_id")) != game_id:
        raise WNBAEventLineupUpstreamError("WNBA source game ID does not match requested game ID.")
    rows, teams = _join(pbp, rotation)
    possessions = _reconstruct_possessions(rows, teams)
    if limit:
        possessions = possessions[-limit:]
    return {
        "source": EVENT_LINEUP_SOURCE,
        "data_type": "derived_possession_segments_with_observed_event_lineups",
        "season": season, "game_id": game_id, "teams": teams,
        "filters": {"limit": limit}, "source_action_count": len(rows),
        "possession_count": len(possessions),
        "complete_possession_count": sum(item["complete"] for item in possessions),
        "high_confidence_boundary_count": sum(item["boundary_confidence"] == "high" for item in possessions),
        "all_events_feature_eligible_possession_count": sum(item["all_events_feature_eligible"] for item in possessions),
        "possessions": possessions,
        "possession_rules": {
            "terminal_events": sorted(_TERMINALS),
            "made_field_goal": "ends unless a same-clock same-team free throw follows",
            "turnover": "ends the turnover-team segment",
            "defensive_rebound": "ends only when rebound subtype identifies defensive",
            "made_final_free_throw": "ends when sequence/order evidence identifies the final same-team free throw",
            "period_end": "ends any open segment",
            "offense_conflict": "closes prior segment incomplete/low-confidence instead of guessing",
        },
        "verification": {
            "requested_game_id_matches_both_sources": True,
            "source_event_order_preserved": True,
            "possession_segments_are_deterministic_derived_features": True,
            "possession_count_is_not_claimed_as_official": True,
            "ambiguous_offense_changes_fail_closed_as_low_confidence": True,
            "event_lineup_is_court_context_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_player_vs_defender_possession_inferred": True,
            "no_causal_defensive_effect_created": True,
            "no_matchup_grade_created": True,
            "no_projection_created": True,
            "no_betting_probability_created": True,
        },
    }
