"""NFL Passing Yards Step 5 V2 — exact-ID weapons + injury usage recovery.

Additive successor to Step 5 V1. V2 keeps ESPN injury/depth as the availability
authority and recovers recent receiving target usage only from exact verified ESPN
event box scores. Current depth-chart athlete IDs remain authoritative, explicit
targets are required, and matching team pass attempts come from the same games.

Current-season completed games are used first. During the opening regular-season
window, the immediately prior regular season may fill the existing five-game
recent window. No fuzzy/name identity authority, synthetic IDs, fabricated targets,
sportsbook input, projection adjustment, market math, or stake sizing is added.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re
from typing import Any

import nfl_passing_yards_defense_v1 as defense_v1
import nfl_passing_yards_defense_v3 as defense_v3
import nfl_passing_yards_early_season_v1 as early
import nfl_passing_yards_personnel_v1 as base

MODEL_VERSION = "NFL PASSING YARDS STEP 5 • WEAPONS + INJURIES V2 • EXACT-ID RECENT TARGET USAGE"
FROZEN_PRIOR = "nfl_passing_yards_personnel_v1"
RECENT_USAGE_WINDOW = 5


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _safe(value).lower())


def _stat_index(category: dict, aliases: tuple[str, ...]) -> int | None:
    """Resolve one ESPN stat column without short-token substring collisions."""
    alias_keys = {_norm(alias) for alias in aliases if _norm(alias)}
    fields = category.get("labels") or category.get("keys") or category.get("descriptions") or []
    normalized = [_norm(value) for value in fields]
    for index, key in enumerate(normalized):
        if key in alias_keys:
            return index
    for index, key in enumerate(normalized):
        if len(key) < 4:
            continue
        for alias in alias_keys:
            if len(alias) >= 4 and (alias in key or key in alias):
                return index
    return None


def _parse_comp_att(value: Any):
    text = _safe(value)
    for token in ("/", "-"):
        if token in text:
            left, right = text.split(token, 1)
            completions, attempts = _num(left), _num(right)
            if _finite(attempts):
                return completions, attempts
    return math.nan, math.nan


def _team_player_block(summary: dict, team_id: str) -> dict:
    for row in ((summary or {}).get("boxscore") or {}).get("players") or []:
        if isinstance(row, dict) and _safe((row.get("team") or {}).get("id")) == _safe(team_id):
            return row
    return {}


def _team_box_row(summary: dict, team_id: str) -> dict:
    for row in ((summary or {}).get("boxscore") or {}).get("teams") or []:
        if isinstance(row, dict) and _safe((row.get("team") or {}).get("id")) == _safe(team_id):
            return row
    return {}


def parse_team_receiving_game(summary: dict, team_id: str) -> dict:
    team_id = _safe(team_id)
    if not team_id.isdigit():
        return {"ready": False, "reason": "verified ESPN team id required", "players": []}

    block = _team_player_block(summary, team_id)
    if not block:
        return {"ready": False, "reason": "exact ESPN team player block missing", "players": []}

    receiving = {}
    passing = {}
    for category in block.get("statistics") or []:
        if not isinstance(category, dict):
            continue
        name = _norm(category.get("name") or category.get("displayName") or category.get("abbreviation"))
        if "receiv" in name:
            receiving = category
        elif "pass" in name:
            passing = category

    target_i = _stat_index(receiving, ("targets", "target", "tgt", "tgts")) if receiving else None
    rec_i = _stat_index(receiving, ("receptions", "rec")) if receiving else None
    yards_i = _stat_index(receiving, ("receivingYards", "yards", "yds")) if receiving else None
    if target_i is None:
        return {"ready": False, "reason": "explicit ESPN receiving targets missing", "players": []}

    attempts = math.nan
    team_row = _team_box_row(summary, team_id)
    if team_row:
        raw = defense_v3._box_stat_v3(team_row, ("completionAttempts", "completionsAttempts", "C/ATT", "Comp-Att", "Comp/Att"))
        _, attempts = _parse_comp_att(raw)

    if not (_finite(attempts) and attempts > 0) and passing:
        comp_i = _stat_index(passing, ("C/ATT", "completionAttempts", "completionsAttempts", "compatt"))
        total_attempts = 0.0
        found = False
        if comp_i is not None:
            for athlete_row in passing.get("athletes") or []:
                stats = athlete_row.get("stats") or []
                if comp_i >= len(stats):
                    continue
                _, value = _parse_comp_att(stats[comp_i])
                if _finite(value):
                    total_attempts += value
                    found = True
        if found and total_attempts > 0:
            attempts = total_attempts

    if not (_finite(attempts) and attempts > 0):
        return {"ready": False, "reason": "matching ESPN team pass attempts missing", "players": []}

    players = []
    for athlete_row in receiving.get("athletes") or []:
        if not isinstance(athlete_row, dict):
            continue
        athlete = athlete_row.get("athlete") or {}
        athlete_id = _safe(athlete.get("id"))
        stats = athlete_row.get("stats") or []
        if not athlete_id.isdigit() or target_i >= len(stats):
            continue
        targets = _num(stats[target_i])
        if not _finite(targets):
            continue
        players.append({
            "athlete_id": athlete_id,
            "name": _safe(athlete.get("displayName") or athlete.get("fullName"), "Unknown player"),
            "targets": targets,
            "receptions": _num(stats[rec_i]) if rec_i is not None and rec_i < len(stats) else math.nan,
            "receiving_yards": _num(stats[yards_i]) if yards_i is not None and yards_i < len(stats) else math.nan,
        })

    return {"ready": True, "reason": "", "team_id": team_id, "team_pass_attempts": attempts, "players": players}


def _completed_events(year: int, season_type: int, team_id: str, cutoff_date: str, limit: int) -> list[dict]:
    payload, diag = defense_v1._team_schedule_payload(int(year), int(season_type), _safe(team_id))
    if not diag.get("ok"):
        return []
    return defense_v3._completed_event_rows_utc(payload, cutoff_date, max_games=max(0, int(limit)))


def _recent_event_window(team_id: str, year: int, season_type: int, cutoff_date: str) -> tuple[list[dict], bool]:
    current = _completed_events(year, season_type, team_id, cutoff_date, RECENT_USAGE_WINDOW)
    if len(current) >= RECENT_USAGE_WINDOW or not early.allow_prior_regular_fallback(season_type):
        return current[:RECENT_USAGE_WINDOW], False
    prior = _completed_events(early.prior_regular_year(year), 2, team_id, cutoff_date, RECENT_USAGE_WINDOW)
    merged = early.merge_recent_rows(current, prior, limit=RECENT_USAGE_WINDOW)
    return merged, len(merged) > len(current)


def recent_weapon_usage(team_id: str, year: int, season_type: int, cutoff_date: str) -> dict:
    events, prior_used = _recent_event_window(team_id, year, season_type, cutoff_date)
    if not events:
        return {"ready": False, "reason": "no completed exact ESPN events available for target usage", "usage_games": 0, "team_pass_attempts": math.nan, "players": {}, "early_season_fallback": False}

    parsed_by_event: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(5, len(events))) as pool:
        futures = {
            pool.submit(defense_v1._summary_payload, _safe(row.get("event_id"))): _safe(row.get("event_id"))
            for row in events if _safe(row.get("event_id")).isdigit()
        }
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                payload, diag = future.result()
            except Exception:
                continue
            if diag.get("ok"):
                parsed = parse_team_receiving_game(payload, team_id)
                if parsed.get("ready"):
                    parsed_by_event[event_id] = parsed

    attempts = 0.0
    usage_games = 0
    aggregate: dict[str, dict] = {}
    used_event_ids: list[str] = []
    for event in events:
        event_id = _safe(event.get("event_id"))
        parsed = parsed_by_event.get(event_id)
        if not parsed:
            continue
        game_attempts = _num(parsed.get("team_pass_attempts"))
        if not (_finite(game_attempts) and game_attempts > 0):
            continue
        attempts += game_attempts
        usage_games += 1
        used_event_ids.append(event_id)
        for player in parsed.get("players") or []:
            athlete_id = _safe(player.get("athlete_id"))
            if not athlete_id.isdigit():
                continue
            row = aggregate.setdefault(athlete_id, {
                "athlete_id": athlete_id,
                "name": _safe(player.get("name"), "Unknown player"),
                "targets": 0.0,
                "receptions": 0.0,
                "receiving_yards": 0.0,
                "games_with_targets": 0,
            })
            row["targets"] += _num(player.get("targets")) if _finite(player.get("targets")) else 0.0
            row["receptions"] += _num(player.get("receptions")) if _finite(player.get("receptions")) else 0.0
            row["receiving_yards"] += _num(player.get("receiving_yards")) if _finite(player.get("receiving_yards")) else 0.0
            row["games_with_targets"] += 1

    if usage_games <= 0 or attempts <= 0:
        return {"ready": False, "reason": "explicit ESPN target columns were unavailable in recent verified events", "usage_games": 0, "team_pass_attempts": math.nan, "players": {}, "early_season_fallback": prior_used}

    for row in aggregate.values():
        row["target_share"] = 100.0 * _num(row.get("targets")) / attempts
        row["target_share_verified"] = True

    current_exists = bool(_completed_events(year, season_type, team_id, cutoff_date, 1))
    return {
        "ready": True,
        "reason": "",
        "usage_games": usage_games,
        "team_pass_attempts": attempts,
        "players": aggregate,
        "event_ids": used_event_ids,
        "early_season_fallback": prior_used,
        "source_year": int(year) - 1 if prior_used and not current_exists else int(year),
    }


def _current_weapon_rows(depth_rows: list[dict], usage: dict, limit: int = 6) -> list[dict]:
    usage_by_id = usage.get("players") or {}
    seen: set[str] = set()
    rows: list[dict] = []
    for raw in depth_rows or []:
        if base._position(raw.get("position")) not in base.SKILL_POSITIONS:
            continue
        athlete_id = _safe(raw.get("athlete_id"))
        if not athlete_id.isdigit() or athlete_id in seen:
            continue
        seen.add(athlete_id)
        row = dict(raw)
        hit = usage_by_id.get(athlete_id) or {}
        row.update({
            "targets": hit.get("targets"),
            "receptions": hit.get("receptions"),
            "receiving_yards": hit.get("receiving_yards"),
            "target_share": hit.get("target_share"),
            "target_share_verified": bool(hit.get("target_share_verified")),
            "usage_games": usage.get("usage_games", 0),
        })
        rows.append(row)
    rows.sort(key=lambda row: (
        0 if _finite(row.get("target_share")) else 1,
        -_num(row.get("target_share")) if _finite(row.get("target_share")) else 0,
        int(row.get("rank", 99)),
        _safe(row.get("name")),
    ))
    return rows[: max(0, int(limit))]


def _enrich_injury_usage(rows: list[dict], usage: dict) -> list[dict]:
    usage_by_id = usage.get("players") or {}
    out = []
    for raw in rows or []:
        row = dict(raw)
        hit = usage_by_id.get(_safe(row.get("athlete_id"))) or {}
        if hit.get("target_share_verified"):
            row.update({
                "targets": hit.get("targets"),
                "receptions": hit.get("receptions"),
                "receiving_yards": hit.get("receiving_yards"),
                "target_share": hit.get("target_share"),
                "target_share_verified": True,
                "usage_source": "EXACT ESPN RECENT BOXSCORE TARGETS",
            })
        out.append(row)
    return out


def _share_for_tier(rows: list[dict], tier: str):
    matching = [row for row in rows or [] if row.get("tier") == tier]
    if not matching:
        return 0.0
    shares = [_num(row.get("target_share")) for row in matching if _finite(row.get("target_share"))]
    return sum(shares) if len(shares) == len(matching) else math.nan


def build_personnel_matchup(offense_ctx: dict, defense_ctx: dict, year: int, season_type: int, team_pass_attempts: Any, cutoff_date: str | None = None) -> dict:
    row = dict(base.build_personnel_matchup(offense_ctx, defense_ctx, year, season_type, team_pass_attempts) or {})
    offense_id = _safe(row.get("offense_team_id") or offense_ctx.get("team_id"))
    if not offense_id.isdigit():
        row["projection_adjustment"] = 0.0
        row["sportsbook_influence"] = 0.0
        return row

    cutoff = _safe(cutoff_date)
    if not cutoff:
        row["weapon_usage_ready"] = False
        row["weapon_usage_state"] = "CHECK — verified slate cutoff unavailable"
        row["top_weapons"] = _current_weapon_rows(row.get("offense_depth_rows") or [], {"players": {}})
        if not row.get("skill_injuries"):
            row["hard_target_share"] = 0.0
            row["watch_target_share"] = 0.0
        row["projection_adjustment"] = 0.0
        row["sportsbook_influence"] = 0.0
        return row

    usage = recent_weapon_usage(offense_id, int(year), int(season_type), cutoff)
    skill = _enrich_injury_usage(list(row.get("skill_injuries") or []), usage)
    row["skill_injuries"] = skill
    row["hard_target_share"] = _share_for_tier(skill, "HARD")
    row["watch_target_share"] = _share_for_tier(skill, "WATCH")
    row["top_weapons"] = _current_weapon_rows(row.get("offense_depth_rows") or [], usage)
    row["weapon_usage_ready"] = bool(usage.get("ready"))
    row["weapon_usage_games"] = int(usage.get("usage_games") or 0)
    row["weapon_usage_event_ids"] = list(usage.get("event_ids") or [])
    row["weapon_usage_early_season_fallback"] = bool(usage.get("early_season_fallback"))
    row["weapon_usage_state"] = (
        f"VERIFIED RECENT {row['weapon_usage_games']} ESPN BOXSCORES"
        + (" • PRIOR REGULAR-SEASON BRIDGE" if row["weapon_usage_early_season_fallback"] else "")
        if usage.get("ready") else "UNAVAILABLE — explicit ESPN box-score targets not returned"
    )
    row["target_share_state"] = row["weapon_usage_state"]

    feed_ok = bool(offense_ctx.get("injury_feed_ok") and defense_ctx.get("injury_feed_ok"))
    label, basis = base.personnel_label(
        _safe(row.get("qb_status")), skill, list(row.get("ol_injuries") or []),
        list(row.get("secondary_injuries") or []), row.get("hard_target_share"), feed_ok,
    )
    row["personnel_label"] = label
    row["personnel_basis"] = basis
    row["projection_adjustment"] = 0.0
    row["sportsbook_influence"] = 0.0
    return row


parse_depth_positions = base.parse_depth_positions
parse_receiving_usage = base.parse_receiving_usage
personnel_label = base.personnel_label
status_tier = base.status_tier

__all__ = [
    "FROZEN_PRIOR", "MODEL_VERSION", "RECENT_USAGE_WINDOW", "build_personnel_matchup",
    "parse_team_receiving_game", "recent_weapon_usage", "parse_depth_positions",
    "parse_receiving_usage", "personnel_label", "status_tier",
]
