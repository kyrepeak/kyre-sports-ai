"""MONSTER CFB Game Total Page 2 — unified verified-data repair.

Presentation-only bridge between the frozen Page-2 display schema and already-
owned CFB evidence.  This module never changes model/projection/probability math,
never uses sportsbook values as sports inputs, and never invents missing data.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from math import isfinite
from statistics import fmean
from threading import RLock
from typing import Any
import re

import cfb_game_total_page2_step8_final_runtime_v1 as page2_runtime
import cfb_game_total_step3_form_v1 as step3_owner
import cfb_game_total_step5_pace_v1 as pace_owner
import cfb_game_total_step6_scoring_v1 as scoring_owner

MODEL_VERSION = "MONSTER CFB PAGE2 VERIFIED DATA ADAPTER V1"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_LIVE_DATA_UNIFIED_REPAIR_V1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_LIVE_DATA_UNIFIED_REPAIR_V1_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0
GITHUB_ACTIONS_FALLBACK = 0

_LOCK = RLock()
_MISSING = (None, "", "—")
_SCORE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*[-–—:]\s*(\d{1,3}(?:\.\d+)?)(?!\d)")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _missing(value: Any) -> bool:
    return value in _MISSING


def _history_score_pair(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    points_for = _number(row.get("points_for"))
    points_against = _number(row.get("points_against"))
    if points_for is not None and points_against is not None:
        return points_for, points_against
    match = _SCORE_RE.search(_clean(row.get("score")))
    if not match:
        return points_for, points_against
    return float(match.group(1)), float(match.group(2))


def normalize_profile_history(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize already-owned completed-game rows without fabricating history."""
    result = deepcopy(_mapping(profile))
    completed = result.get("completed_games")
    rows: list[dict[str, Any]] = []
    if isinstance(completed, Sequence) and not isinstance(completed, (str, bytes)):
        for raw in completed:
            if not isinstance(raw, Mapping):
                continue
            row = deepcopy(dict(raw))
            points_for, points_against = _history_score_pair(row)
            if points_for is not None and _number(row.get("points_for")) is None:
                row["points_for"] = points_for
            if points_against is not None and _number(row.get("points_against")) is None:
                row["points_against"] = points_against
            rows.append(row)
    result["completed_games"] = rows

    valid = []
    for row in rows:
        points_for = _number(row.get("points_for"))
        points_against = _number(row.get("points_against"))
        if points_for is not None and points_against is not None:
            valid.append((points_for, points_against))
    recent = valid[-5:]
    if recent:
        if _number(result.get("recent_ppg")) is None:
            result["recent_ppg"] = float(fmean(pair[0] for pair in recent))
        if _number(result.get("recent_points_allowed_pg")) is None:
            result["recent_points_allowed_pg"] = float(fmean(pair[1] for pair in recent))
        if _number(result.get("points_allowed_pg")) is None:
            result["points_allowed_pg"] = float(fmean(pair[1] for pair in recent))
    return result


def _history_quality(profile: Mapping[str, Any]) -> int:
    score = 0
    for raw in profile.get("completed_games") or []:
        if not isinstance(raw, Mapping):
            continue
        points_for, points_against = _history_score_pair(raw)
        if points_for is not None and points_against is not None:
            score += 2
        if _clean(raw.get("event_id") or raw.get("espn_event_id") or raw.get("game_id")):
            score += 1
    return score


def _overlay_profile(current: Mapping[str, Any], owned: Mapping[str, Any]) -> dict[str, Any]:
    """Fill gaps from certified evidence while preserving already-owned values."""
    result = deepcopy(dict(current))
    source = deepcopy(dict(owned))
    for key, value in source.items():
        if key == "completed_games":
            continue
        if key not in result or _missing(result.get(key)):
            result[key] = value
    current_norm = normalize_profile_history(result)
    owned_norm = normalize_profile_history(source)
    if _history_quality(owned_norm) > _history_quality(current_norm):
        current_norm["completed_games"] = deepcopy(owned_norm.get("completed_games") or [])
        for key in ("recent_ppg", "recent_points_allowed_pg", "points_allowed_pg"):
            if _number(current_norm.get(key)) is None and _number(owned_norm.get(key)) is not None:
                current_norm[key] = owned_norm[key]
    return normalize_profile_history(current_norm)


def _fill_number(target: dict[str, Any], key: str, value: Any) -> None:
    if _number(target.get(key)) is None:
        number = _number(value)
        if number is not None:
            target[key] = number


def _mean_numbers(*values: Any) -> float | None:
    known = [number for value in values if (number := _number(value)) is not None]
    return float(fmean(known)) if known else None


def _favorable_side(away_value: Any, home_value: Any, *, lower_is_better: bool = False) -> str | None:
    away = _number(away_value)
    home = _number(home_value)
    if away is None or home is None:
        return None
    if abs(away - home) <= 1e-9:
        return "even"
    if lower_is_better:
        return "away" if away < home else "home"
    return "away" if away > home else "home"


def _apply_favorable(raw: dict[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    existing = raw.get("favorable_for") if isinstance(raw.get("favorable_for"), Mapping) else {}
    favorable = dict(existing)
    pairs = {
        "pace": (_number(away.get("plays_per_game")), _number(home.get("plays_per_game")), False),
        "explosive": (_number(away.get("explosive_rate")), _number(home.get("explosive_rate")), False),
        "red_zone": (_number(away.get("red_zone_td_rate")), _number(home.get("red_zone_td_rate")), False),
        "defense": (_number(away.get("points_allowed_pg")), _number(home.get("points_allowed_pg")), True),
    }
    for key, (away_value, home_value, lower_is_better) in pairs.items():
        if favorable.get(key) in {"away", "home", "even"}:
            continue
        side = _favorable_side(away_value, home_value, lower_is_better=lower_is_better)
        if side:
            favorable[key] = side
    if favorable:
        raw["favorable_for"] = favorable


def enrich_page2_payload(
    payload: Mapping[str, Any],
    *,
    step3_bundle: Mapping[str, Any] | None = None,
    pace_contract: Mapping[str, Any] | None = None,
    scoring_contract: Mapping[str, Any] | None = None,
    scoring_breakdown: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure display-payload adapter. Existing verified fields always win."""
    enriched = deepcopy(dict(payload))
    away = normalize_profile_history(_mapping(enriched.get("away")))
    home = normalize_profile_history(_mapping(enriched.get("home")))
    raw = deepcopy(_mapping(enriched.get("raw")))

    step3 = _mapping(step3_bundle)
    if isinstance(step3.get("away"), Mapping):
        away = _overlay_profile(away, step3["away"])
    if isinstance(step3.get("home"), Mapping):
        home = _overlay_profile(home, step3["home"])

    pace = _mapping(pace_contract)
    pace_away = _mapping(pace.get("away"))
    pace_home = _mapping(pace.get("home"))
    _fill_number(away, "plays_per_game", pace_away.get("plays_per_game"))
    _fill_number(home, "plays_per_game", pace_home.get("plays_per_game"))

    scoring = _mapping(scoring_contract)
    evidence = _mapping(scoring.get("evidence"))
    away_offense = _mapping(evidence.get("away_offense"))
    home_offense = _mapping(evidence.get("home_offense"))
    away_defense = _mapping(evidence.get("away_defense"))
    home_defense = _mapping(evidence.get("home_defense"))

    _fill_number(away, "explosive_rate", away_offense.get("overall_explosive_rate"))
    _fill_number(home, "explosive_rate", home_offense.get("overall_explosive_rate"))
    _fill_number(away, "red_zone_td_rate", away_offense.get("red_zone_td_rate"))
    _fill_number(home, "red_zone_td_rate", home_offense.get("red_zone_td_rate"))
    _fill_number(away, "points_allowed_pg", away.get("recent_points_allowed_pg"))
    _fill_number(home, "points_allowed_pg", home.get("recent_points_allowed_pg"))

    if _number(raw.get("scoring_opportunities")) is None:
        expected = _number(scoring.get("expected_scoring_chances"))
        if expected is not None:
            raw["scoring_opportunities"] = expected

    if _missing(raw.get("explosive_scoring")):
        explosive_mean = _mean_numbers(
            away_offense.get("overall_explosive_rate"),
            home_offense.get("overall_explosive_rate"),
            away_defense.get("overall_explosive_rate"),
            home_defense.get("overall_explosive_rate"),
        )
        if explosive_mean is not None:
            raw["explosive_scoring"] = f"{100.0 * explosive_mean:.1f}%"

    if _number(raw.get("red_zone_finishing")) is None:
        red_zone_mean = _mean_numbers(
            away_offense.get("red_zone_td_rate"),
            home_offense.get("red_zone_td_rate"),
        )
        if red_zone_mean is not None:
            raw["red_zone_finishing"] = red_zone_mean

    if not isinstance(raw.get("scoring_breakdown"), Mapping) or not raw.get("scoring_breakdown"):
        if isinstance(scoring_breakdown, Mapping) and scoring_breakdown:
            raw["scoring_breakdown"] = deepcopy(dict(scoring_breakdown))

    _apply_favorable(raw, away, home)
    enriched["away"] = away
    enriched["home"] = home
    enriched["raw"] = raw
    return enriched


def _selected_day(identity: Mapping[str, Any], game: Mapping[str, Any]) -> str:
    for source in (game, identity, _mapping(identity.get("game"))):
        for key in ("game_date", "date", "kickoff_date", "kickoff_iso", "start_date"):
            text = _clean(source.get(key))
            if text:
                return text[:10]
    return ""


def _team_name(identity: Mapping[str, Any], profile: Mapping[str, Any], side: str) -> str:
    row = _mapping(identity.get(side))
    return _clean(row.get("team") or row.get("name") or profile.get("team") or profile.get("team_name"))


def _team_id(identity: Mapping[str, Any], profile: Mapping[str, Any], side: str) -> str:
    for source in (_mapping(identity.get(side)), profile):
        for key in ("team_id", "espn_team_id", "id"):
            value = _clean(source.get(key))
            if value.isdigit():
                return value
    return ""


def _game_for_owners(payload: Mapping[str, Any]) -> dict[str, Any]:
    identity = _mapping(payload.get("identity"))
    away = _mapping(payload.get("away"))
    home = _mapping(payload.get("home"))
    game = deepcopy(_mapping(payload.get("display_game")))
    away_name = _team_name(identity, away, "away")
    home_name = _team_name(identity, home, "home")
    if away_name and _missing(game.get("away_team")):
        game["away_team"] = away_name
    if home_name and _missing(game.get("home_team")):
        game["home_team"] = home_name
    day = _selected_day(identity, game)
    if day and _missing(game.get("game_date")):
        game["game_date"] = day
    return game


def _ensure_identity_ids(identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(identity))
    for side, profile in (("away", away), ("home", home)):
        row = _mapping(result.get(side))
        team_id = _team_id(result, profile, side)
        if team_id and not _clean(row.get("team_id")):
            row["team_id"] = team_id
        if not _clean(row.get("team")):
            name = _team_name(result, profile, side)
            if name:
                row["team"] = name
        result[side] = row
    return result


def _play_score(play: Mapping[str, Any], key: str) -> float | None:
    if key == "home":
        return _number(play.get("homeScore") if play.get("homeScore") is not None else play.get("home_score"))
    return _number(play.get("awayScore") if play.get("awayScore") is not None else play.get("away_score"))


def _period_score_ends(payload: Mapping[str, Any]) -> dict[int, tuple[float, float]]:
    """Return cumulative away/home score at the latest clock state per period."""
    best: dict[int, tuple[float, float, float]] = {}
    for raw in payload.get("plays") or []:
        if not isinstance(raw, Mapping):
            continue
        period = pace_owner._play_period(raw)
        if period is None or period <= 0:
            continue
        away = _play_score(raw, "away")
        home = _play_score(raw, "home")
        if away is None or home is None:
            continue
        clock = pace_owner._play_clock(raw)
        rank = float(clock) if clock is not None else 1e9
        current = best.get(period)
        if current is None or rank <= current[0]:
            best[period] = (rank, away, home)
    return {period: (row[1], row[2]) for period, row in best.items()}


def _payload_team_id(payload: Mapping[str, Any], side: str) -> str:
    prefixes = ("home", "homeTeam", "home_team") if side == "home" else ("away", "awayTeam", "away_team")
    direct_keys = (
        f"{side}_team_id",
        f"{side}TeamId",
        f"{side}.team.id",
        f"{side}.id",
    )
    for key in direct_keys:
        value = _clean(payload.get(key))
        if value.isdigit():
            return value
    for key in prefixes:
        row = payload.get(key)
        if isinstance(row, Mapping):
            value = _clean(row.get("team_id") or row.get("teamId") or row.get("id"))
            if value.isdigit():
                return value
    header = payload.get("header") if isinstance(payload.get("header"), Mapping) else {}
    competitions = header.get("competitions") if isinstance(header.get("competitions"), Sequence) else []
    for competition in competitions:
        if not isinstance(competition, Mapping):
            continue
        for competitor in competition.get("competitors") or []:
            if not isinstance(competitor, Mapping) or _clean(competitor.get("homeAway")).lower() != side:
                continue
            team = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else {}
            value = _clean(competitor.get("id") or team.get("id"))
            if value.isdigit():
                return value
    return ""


def _history_row_by_event(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in normalize_profile_history(profile).get("completed_games") or []:
        if not isinstance(row, Mapping):
            continue
        event_id = _clean(row.get("event_id") or row.get("espn_event_id") or row.get("game_id") or row.get("id"))
        if event_id:
            out[event_id] = dict(row)
    return out


def _infer_historical_side(payload: Mapping[str, Any], team_id: str, history_row: Mapping[str, Any], ends: Mapping[int, tuple[float, float]]) -> str | None:
    if team_id:
        if team_id == _payload_team_id(payload, "away"):
            return "away"
        if team_id == _payload_team_id(payload, "home"):
            return "home"
    if not ends:
        return None
    last_period = max(ends)
    away_final, home_final = ends[last_period]
    points_for, points_against = _history_score_pair(history_row)
    if points_for is None or points_against is None:
        return None
    if abs(away_final - points_for) <= 0.1 and abs(home_final - points_against) <= 0.1:
        return "away"
    if abs(home_final - points_for) <= 0.1 and abs(away_final - points_against) <= 0.1:
        return "home"
    return None


def _recent_pbp_scoring_breakdown(identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> dict[str, Any]:
    """Derive display-only recent regulation splits from verified completed-game PBP."""
    profiles = {"away": away, "home": home}
    histories = {side: _history_row_by_event(profile) for side, profile in profiles.items()}
    side_events = {side: pace_owner._event_ids(profile) for side, profile in profiles.items()}
    unique_events = list(dict.fromkeys(event for values in side_events.values() for event in values if event))
    payloads: dict[str, dict[str, Any]] = {}
    for event_id in unique_events[: 2 * scoring_owner.MAX_PBP_GAMES]:
        payload = pace_owner._fetch_sportsdataverse_game(event_id)
        if isinstance(payload, Mapping) and payload:
            payloads[event_id] = dict(payload)

    half_values: dict[str, list[float]] = {"away_1h": [], "away_2h": [], "home_1h": [], "home_2h": []}
    quarter_values: dict[int, list[float]] = {1: [], 2: [], 3: [], 4: []}
    quarter_seen: set[str] = set()

    for side, profile in profiles.items():
        team_id = _team_id(identity, profile, side)
        for event_id in side_events.get(side, []):
            payload = payloads.get(event_id)
            if not payload:
                continue
            ends = _period_score_ends(payload)
            if 2 not in ends or 4 not in ends:
                continue
            history_row = histories[side].get(event_id, {})
            historical_side = _infer_historical_side(payload, team_id, history_row, ends)
            if historical_side:
                index = 0 if historical_side == "away" else 1
                first_half = ends[2][index]
                second_half = max(0.0, ends[4][index] - first_half)
                half_values[f"{side}_1h"].append(float(first_half))
                half_values[f"{side}_2h"].append(float(second_half))

            if event_id in quarter_seen:
                continue
            quarter_seen.add(event_id)
            previous_total = 0.0
            complete = True
            for period in (1, 2, 3, 4):
                if period not in ends:
                    complete = False
                    break
                total = float(ends[period][0] + ends[period][1])
                quarter_values[period].append(max(0.0, total - previous_total))
                previous_total = total
            if not complete:
                for period in (1, 2, 3, 4):
                    if quarter_values[period] and len(quarter_values[period]) > len(quarter_seen) - 1:
                        quarter_values[period].pop()

    breakdown: dict[str, Any] = {}
    for key, values in half_values.items():
        if values:
            breakdown[key] = round(float(fmean(values)), 1)
    for period, values in quarter_values.items():
        if values:
            breakdown[f"q{period}"] = round(float(fmean(values)), 1)
    return breakdown


def _live_enrich(payload: Mapping[str, Any]) -> dict[str, Any]:
    base = deepcopy(dict(payload))
    identity = _mapping(base.get("identity"))
    game = _game_for_owners(base)
    day = _selected_day(identity, game)

    step3_bundle: dict[str, Any] = {}
    try:
        bundle, _diag = step3_owner._runtime_v2_step3_bundle(game, day)
        if isinstance(bundle, Mapping):
            step3_bundle = dict(bundle)
    except Exception:
        step3_bundle = {}

    enriched = enrich_page2_payload(base, step3_bundle=step3_bundle)
    away = _mapping(enriched.get("away"))
    home = _mapping(enriched.get("home"))
    identity = _ensure_identity_ids(identity, away, home)
    enriched["identity"] = identity
    game = _game_for_owners(enriched)

    pace_contract: dict[str, Any] = {}
    try:
        pace_result = pace_owner.build_step5_contract(identity, away, home, game)
        if isinstance(pace_result, Mapping):
            pace_contract = dict(pace_result)
    except Exception:
        pace_contract = {}

    scoring_contract: dict[str, Any] = {}
    try:
        scoring_result = scoring_owner.build_step6_contract(identity, away, home, game)
        if isinstance(scoring_result, Mapping):
            scoring_contract = dict(scoring_result)
    except Exception:
        scoring_contract = {}

    breakdown: dict[str, Any] = {}
    try:
        breakdown = _recent_pbp_scoring_breakdown(identity, away, home)
    except Exception:
        breakdown = {}

    return enrich_page2_payload(
        enriched,
        pace_contract=pace_contract,
        scoring_contract=scoring_contract,
        scoring_breakdown=breakdown,
    )


def _payload_key(payload: Mapping[str, Any]) -> tuple[str, str, str, str]:
    identity = _mapping(payload.get("identity"))
    game = _mapping(payload.get("display_game"))
    event_id = _clean(game.get("espn_event_id") or game.get("event_id") or game.get("game_id") or game.get("id"))
    return (
        event_id,
        _selected_day(identity, game),
        _team_name(identity, _mapping(payload.get("away")), "away"),
        _team_name(identity, _mapping(payload.get("home")), "home"),
    )


@contextmanager
def install_page2_live_data_repair():
    """Temporarily adapt only the Page-2 body; restore the frozen owner after render."""
    with _LOCK:
        original = page2_runtime.build_page2_body_html
        memo: dict[tuple[str, str, str, str], dict[str, Any]] = {}

        def repaired(payload: Mapping[str, Any]) -> str:
            key = _payload_key(payload)
            if key not in memo:
                memo[key] = _live_enrich(payload)
            return original(deepcopy(memo[key]))

        page2_runtime.build_page2_body_html = repaired
        try:
            yield
        finally:
            page2_runtime.build_page2_body_html = original


__all__ = [
    "ACTIVE_MARKER",
    "FREEZE_TOKEN",
    "GITHUB_ACTIONS_FALLBACK",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_page2_payload",
    "install_page2_live_data_repair",
    "normalize_profile_history",
]
