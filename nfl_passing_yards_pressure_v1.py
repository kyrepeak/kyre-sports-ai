"""NFL Passing Yards Step 4 — pass protection + defensive pressure context.

Descriptive evidence only. This module does not create or alter a passing-yards
projection, fair line, probability, EV, Monte Carlo result, ranking, or pick.

Sources reuse the verified ESPN team IDs from Step 1 and the cached ESPN team
statistics / schedule / game-summary feeds introduced in Step 3. ESPN box-score
`sacksYardsLost` is treated as sacks TAKEN by that offense; the opponent row is
therefore used for recent defensive sacks made. No fuzzy team matching is used.

A stable verified blitz-rate field is not available in this ESPN path, so blitz
rate is deliberately reported as unavailable instead of being inferred.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import math
import re
from typing import Any

import pandas as pd

import nfl_passing_yards_defense_v1 as defense

MODEL_VERSION = "NFL PASSING YARDS STEP 4 • PROTECTION + PRESSURE V1"


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


def _categories(payload: dict) -> list[dict]:
    splits = (payload or {}).get("splits") or {}
    cats = splits.get("categories") if isinstance(splits, dict) else None
    if isinstance(cats, list):
        return [x for x in cats if isinstance(x, dict)]
    raw = (payload or {}).get("categories") or []
    return [x for x in raw if isinstance(x, dict)]


def _category_stat_map(payload: dict, category_tokens: tuple[str, ...]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    wanted = tuple(_norm(x) for x in category_tokens)
    for cat in _categories(payload):
        cat_name = _norm(cat.get("name") or cat.get("displayName") or cat.get("abbreviation"))
        if wanted and not any(token in cat_name for token in wanted):
            continue
        for stat in cat.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            for key in (
                _norm(stat.get("name")),
                _norm(stat.get("displayName")),
                _norm(stat.get("shortDisplayName")),
                _norm(stat.get("abbreviation")),
            ):
                if key:
                    out[key] = dict(stat)
    return out


def _global_stat_map(payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for cat in _categories(payload):
        for stat in cat.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            for key in (
                _norm(stat.get("name")),
                _norm(stat.get("displayName")),
                _norm(stat.get("shortDisplayName")),
                _norm(stat.get("abbreviation")),
            ):
                if key and key not in out:
                    out[key] = dict(stat)
    return out


def _pick_row(stats: dict[str, dict], aliases: tuple[str, ...]) -> dict:
    for alias in aliases:
        row = stats.get(_norm(alias))
        if row:
            return row
    return {}


def _row_value(row: dict):
    for field in ("value", "perGameValue", "displayValue"):
        value = _num((row or {}).get(field))
        if _finite(value):
            return value
    return math.nan


def _row_rank(row: dict):
    value = _num((row or {}).get("rank"))
    return int(value) if _finite(value) and value > 0 else None


def parse_offense_protection(payload: dict) -> dict:
    """Parse offensive sacks taken without confusing them with defensive sacks."""
    passing = _category_stat_map(payload, ("passing", "pass"))
    all_stats = _global_stat_map(payload)

    def pick(primary: tuple[str, ...], fallback: tuple[str, ...] = ()) -> dict:
        row = _pick_row(passing, primary)
        return row or _pick_row(all_stats, fallback)

    games_row = _pick_row(all_stats, ("gamesPlayed", "games", "GP"))
    attempts_row = pick(
        ("passingAttempts", "passAttempts", "attempts", "ATT"),
        ("passingAttempts", "passAttempts", "teamPassingAttempts"),
    )
    # In ESPN passing categories, `sacks`/`sacksYardsLost` describe sacks taken.
    sacks_row = pick(
        ("sacks", "timesSacked", "sacksTaken", "sacksAllowed"),
        ("timesSacked", "sacksTaken", "sacksAllowed"),
    )
    sack_yards_row = pick(
        ("sackYardsLost", "sacksYardsLost", "timesSackedYards"),
        ("timesSackedYards", "sackYardsLost"),
    )

    games = _row_value(games_row)
    attempts = _row_value(attempts_row)
    sacks_allowed = _row_value(sacks_row)
    sack_yards = _row_value(sack_yards_row)
    dropbacks = attempts + sacks_allowed if _finite(attempts) and _finite(sacks_allowed) else math.nan
    sack_rate = 100.0 * sacks_allowed / dropbacks if _finite(dropbacks) and dropbacks > 0 else math.nan
    sacks_pg = sacks_allowed / games if _finite(sacks_allowed) and _finite(games) and games > 0 else math.nan

    ready = _finite(attempts) and attempts > 0 and _finite(sacks_allowed)
    return {
        "ready": bool(ready),
        "games": games,
        "passing_attempts": attempts,
        "sacks_allowed": sacks_allowed,
        "sacks_allowed_per_game": sacks_pg,
        "sack_yards_lost": sack_yards,
        "dropbacks": dropbacks,
        "sack_rate_allowed": sack_rate,
        "sacks_allowed_rank": _row_rank(sacks_row),
    }


def parse_defensive_pressure(payload: dict) -> dict:
    """Use verified season defensive sacks as a transparent pressure proxy."""
    season = defense.parse_season_pass_defense(payload)
    games = season.get("games")
    sacks = season.get("sacks")
    opp_attempts = season.get("passing_attempts_allowed")
    pressure_dropbacks = opp_attempts + sacks if _finite(opp_attempts) and _finite(sacks) else math.nan
    sack_rate = 100.0 * sacks / pressure_dropbacks if _finite(pressure_dropbacks) and pressure_dropbacks > 0 else math.nan
    sacks_pg = sacks / games if _finite(sacks) and _finite(games) and games > 0 else math.nan
    return {
        "ready": bool(_finite(sacks) and _finite(opp_attempts) and opp_attempts > 0),
        "games": games,
        "sacks_made": sacks,
        "sacks_per_game": sacks_pg,
        "opponent_pass_attempts": opp_attempts,
        "pressure_dropbacks": pressure_dropbacks,
        "sack_rate_generated": sack_rate,
        "blitz_rate": math.nan,
        "blitz_state": "UNAVAILABLE — not synthesized from ESPN sack data",
    }


def _parse_sack_count(value: Any):
    text = _safe(value)
    if not text:
        return math.nan
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[-/]", text)
    if match:
        return _num(match.group(1))
    return _num(text)


def _parse_attempts(value: Any):
    text = _safe(value)
    if not text:
        return math.nan
    for sep in ("/", "-"):
        if sep in text:
            left, right = text.split(sep, 1)
            attempts = _num(right)
            return attempts if _finite(attempts) else math.nan
    return math.nan


def parse_recent_sacks_taken(summary: dict, offense_team_id: str) -> dict:
    row = defense._team_boxscore_row(summary, offense_team_id)
    if not row:
        return {}
    sacks = _parse_sack_count(defense._box_stat(row, ("sacksYardsLost", "Sacks-Yards Lost", "sacks")))
    attempts = _parse_attempts(defense._box_stat(row, ("completionAttempts", "C/ATT", "Comp-Att")))
    if not _finite(sacks):
        return {}
    dropbacks = attempts + sacks if _finite(attempts) else math.nan
    return {
        "sacks_taken": sacks,
        "pass_attempts": attempts,
        "dropbacks": dropbacks,
        "sack_rate": 100.0 * sacks / dropbacks if _finite(dropbacks) and dropbacks > 0 else math.nan,
    }


def parse_recent_sacks_made(summary: dict, defense_team_id: str) -> dict:
    teams = ((summary or {}).get("boxscore") or {}).get("teams") or []
    opponent_id = ""
    for row in teams:
        if not isinstance(row, dict):
            continue
        ident = _safe((row.get("team") or {}).get("id"))
        if ident and ident != _safe(defense_team_id):
            opponent_id = ident
            break
    if not opponent_id:
        return {}
    taken = parse_recent_sacks_taken(summary, opponent_id)
    if not taken:
        return {}
    return {
        "sacks_made": taken.get("sacks_taken"),
        "opponent_pass_attempts": taken.get("pass_attempts"),
        "pressure_dropbacks": taken.get("dropbacks"),
        "sack_rate_generated": taken.get("sack_rate"),
    }


def _recent_rows(team_id: str, year: int, season_type: int, cutoff_date: str, side: str) -> list[dict]:
    schedule, diag = defense._team_schedule_payload(year, season_type, team_id)
    if not diag.get("ok"):
        return []
    events = defense._completed_event_rows(schedule, cutoff_date, max_games=5)
    rows: list[dict] = []
    for meta in events:
        summary, sdiag = defense._summary_payload(meta["event_id"])
        if not sdiag.get("ok"):
            continue
        parsed = parse_recent_sacks_taken(summary, team_id) if side == "offense" else parse_recent_sacks_made(summary, team_id)
        if parsed:
            parsed["event_id"] = meta["event_id"]
            parsed["date"] = meta["date"].strftime("%Y-%m-%d")
            rows.append(parsed)
    return rows


def _avg(rows: list[dict], key: str):
    values = [_num(row.get(key)) for row in rows]
    values = [x for x in values if _finite(x)]
    return sum(values) / len(values) if values else math.nan


def pressure_label(offense: dict, defense_pressure: dict) -> tuple[str, str]:
    """Transparent descriptive label; never used as a projection adjustment here."""
    allowed = _num(offense.get("sack_rate_allowed"))
    generated = _num(defense_pressure.get("sack_rate_generated"))
    if not (_finite(allowed) and _finite(generated)):
        return "CHECK", "season sack-rate evidence incomplete"
    combined = (allowed + generated) / 2.0
    if combined >= 8.0:
        return "HIGH PRESSURE", f"mean sack-rate context {combined:.1f}%"
    if combined <= 4.5:
        return "LOW PRESSURE", f"mean sack-rate context {combined:.1f}%"
    return "MODERATE", f"mean sack-rate context {combined:.1f}%"


def build_pressure_matchup(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    offense_team_id = _safe(offense_team_id)
    defense_team_id = _safe(defense_team_id)
    if not offense_team_id.isdigit() or not defense_team_id.isdigit():
        return {
            "ready": False,
            "reason": "verified ESPN offense and defense team IDs are required",
            "offense_team_id": offense_team_id,
            "defense_team_id": defense_team_id,
        }

    with ThreadPoolExecutor(max_workers=2) as pool:
        off_future = pool.submit(defense._team_stats_payload, year, season_type, offense_team_id)
        def_future = pool.submit(defense._team_stats_payload, year, season_type, defense_team_id)
        off_payload, off_diag = off_future.result()
        def_payload, def_diag = def_future.result()

    offense = parse_offense_protection(off_payload) if off_diag.get("ok") else {"ready": False}
    pressure = parse_defensive_pressure(def_payload) if def_diag.get("ok") else {"ready": False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        off_recent_future = pool.submit(_recent_rows, offense_team_id, year, season_type, cutoff_date, "offense")
        def_recent_future = pool.submit(_recent_rows, defense_team_id, year, season_type, cutoff_date, "defense")
        offense_recent = off_recent_future.result()
        defense_recent = def_recent_future.result()

    label, basis = pressure_label(offense, pressure)
    ready = bool(offense.get("ready") and pressure.get("ready"))
    return {
        "ready": ready,
        "reason": "" if ready else "verified season pass-protection or defensive sack evidence is incomplete",
        "offense_team_id": offense_team_id,
        "offense_team_name": _safe(offense_team_name, "Offense"),
        "defense_team_id": defense_team_id,
        "defense_team_name": _safe(defense_team_name, "Defense"),
        "offense": offense,
        "defense": pressure,
        "pressure_label": label,
        "pressure_basis": basis,
        "recent_offense": offense_recent,
        "recent_defense": defense_recent,
        "recent3_sacks_allowed": _avg(offense_recent[:3], "sacks_taken"),
        "recent5_sacks_allowed": _avg(offense_recent[:5], "sacks_taken"),
        "recent3_sack_rate_allowed": _avg(offense_recent[:3], "sack_rate"),
        "recent3_sacks_made": _avg(defense_recent[:3], "sacks_made"),
        "recent5_sacks_made": _avg(defense_recent[:5], "sacks_made"),
        "recent3_sack_rate_generated": _avg(defense_recent[:3], "sack_rate_generated"),
        "offense_stats_http": off_diag.get("http"),
        "defense_stats_http": def_diag.get("http"),
        "blitz_state": pressure.get("blitz_state") or "UNAVAILABLE — not synthesized",
        "projection_adjustment": 0.0,
    }


__all__ = [
    "MODEL_VERSION",
    "build_pressure_matchup",
    "parse_defensive_pressure",
    "parse_offense_protection",
    "parse_recent_sacks_made",
    "parse_recent_sacks_taken",
    "pressure_label",
]
